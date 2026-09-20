"""The tool's own RSA keys.

Canvas verifies anything this tool signs — a Deep Linking response (task 1.14),
a client assertion for a Names and Roles token (task 1.13) — against the public
keys published at ``/lti/jwks/``. This module owns both halves of that: it
generates keypairs, and it builds the JWKS document from the public halves.

Keys are files in ``LTI_TOOL_KEY_DIR``, one PEM per key, named by its ``kid`` —
which is the key's own RFC 7638 thumbprint, so the name is derived from the key
material rather than assigned to it (DECISIONS.md D-027).
Deliberately not rows in the database: a database dump is copied, shared and
restored far more casually than a key file, and a private key that leaks lets
anyone impersonate this tool to Canvas. ``LtiPlatform.tool_key_id`` holds a
reference to a key here, never the key itself.

Every key in the directory is published, not just the one in use. During a
rotation Canvas may still hold a token signed by the previous key, and removing
it from the JWKS the moment a new key is generated would reject that token.
Retiring a key is therefore deleting its file, deliberately and later.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.conf import settings

logger = logging.getLogger(__name__)

__all__ = [
    "KeyStoreError",
    "ToolKey",
    "generate_key",
    "key_directory",
    "private_key_pem",
    "public_jwks",
    "public_key_pem",
]

# RSA 2048 with RS256, which is what LTI 1.3 requires and Canvas accepts. Not
# configurable: a key size chosen by an operator is a key size that can be set
# too low, and nothing here needs to vary between environments.
KEY_SIZE = 2048
PUBLIC_EXPONENT = 65537

# Only the owner may read a private key, and only the owner may list the
# directory holding them.
PRIVATE_KEY_MODE = 0o600
KEY_DIRECTORY_MODE = 0o700


class KeyStoreError(Exception):
    """The key directory or one of its keys cannot be used."""


@dataclass(frozen=True)
class ToolKey:
    kid: str
    path: Path


def key_directory() -> Path:
    """Where the keys live. Reads only — never creates, never changes a mode.

    Separate from :func:`_writable_key_directory` on purpose: serving the JWKS
    is an unauthenticated public GET, and it must not have a filesystem side
    effect, nor silently reset a directory mode an operator set deliberately.
    """
    return Path(settings.LTI_TOOL_KEY_DIR)


def _writable_key_directory() -> Path:
    """The key directory, created with restrictive permissions if absent."""
    directory = key_directory()
    try:
        directory.mkdir(parents=True, exist_ok=True)
        directory.chmod(KEY_DIRECTORY_MODE)
    except OSError as exc:
        raise KeyStoreError(f"Cannot use the LTI key directory {directory}: {exc}") from exc
    return directory


def generate_key() -> ToolKey:
    """Generate a keypair and write the private half, returning its ``kid``.

    Only the private key is stored; the public half is derived from it on
    demand, so the two can never drift apart.
    """
    private_key = rsa.generate_private_key(public_exponent=PUBLIC_EXPONENT, key_size=KEY_SIZE)
    kid = _thumbprint(private_key)
    path = _writable_key_directory() / f"{kid}.pem"

    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        # Unencrypted, because Gunicorn and the Celery worker must read it at
        # start with no operator present. Its protection is the file mode below
        # and the volume it sits on, not a passphrase that would have to be
        # stored beside it to be useful. See DECISIONS.md D-026.
        encryption_algorithm=serialization.NoEncryption(),
    )

    try:
        # O_EXCL rather than a plain open: writing over an existing private key
        # would silently destroy it, and every token signed with it.
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, PRIVATE_KEY_MODE)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(pem)
    except OSError as exc:
        raise KeyStoreError(f"Cannot write the private key to {path}: {exc}") from exc

    return ToolKey(kid=kid, path=path)


def private_key_pem(kid: str) -> str:
    """Return a key's private PEM text, for signing requests to Canvas."""
    path = _key_path(kid)
    _load_private_key(path)  # reject a corrupt file here rather than at signing time
    return path.read_text()


def public_key_pem(kid: str) -> str:
    """Return a key's public PEM text.

    PyLTI1p3 needs this as well as the private half: it derives the ``kid`` it
    stamps on every JWT it signs from the PUBLIC key, and signs without a
    ``kid`` header at all if it was never given one. With several keys
    published, Canvas would then have nothing to select by.
    """
    public_key = _load_private_key(_key_path(kid)).public_key()
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()


def _key_path(kid: str) -> Path:
    path = key_directory() / f"{kid}.pem"
    if not path.is_file():
        raise KeyStoreError(
            f"No tool key {kid!r} in {key_directory()}. Either it was never generated, "
            f"or the key directory is not the one it was generated into."
        )
    return path


def public_jwks() -> dict[str, list[dict[str, str]]]:
    """Build the JWKS document from every key in the directory.

    A key that cannot be read is logged and skipped rather than raising. This
    endpoint is on Canvas's path to verifying the tool: one corrupt file must
    not take the working keys down with it.
    """
    directory = key_directory()
    try:
        paths = sorted(directory.glob("*.pem"))
    except OSError:
        # A read-only mount, a directory owned by another uid, or none at all.
        # Canvas fetches this on its way to trusting the tool; failing the
        # request can break installation, so serve an empty — still valid — set.
        logger.exception("Cannot list the LTI key directory %s", directory)
        return {"keys": []}

    keys: list[dict[str, str]] = []
    for path in paths:
        try:
            keys.append(_jwk(_load_private_key(path)))
        except KeyStoreError:
            logger.exception("Skipping unreadable LTI tool key %s", path.name)
    return {"keys": keys}


def _load_private_key(path: Path) -> rsa.RSAPrivateKey:
    try:
        key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    except (OSError, ValueError, TypeError) as exc:
        raise KeyStoreError(f"{path} is not a readable unencrypted PEM private key.") from exc
    if not isinstance(key, rsa.RSAPrivateKey):
        raise KeyStoreError(f"{path} is not an RSA private key; LTI 1.3 requires RS256.")
    return key


def _jwk(private_key: rsa.RSAPrivateKey) -> dict[str, str]:
    """Render the PUBLIC half of a key as a JWK (RFC 7517).

    Built from the public numbers alone, so no private component can reach the
    published document by oversight. The ``kid`` is recomputed from the key
    rather than taken from the file name: a PEM that was copied, restored or
    renamed would otherwise be advertised under an identifier no signer derives.
    """
    numbers = private_key.public_key().public_numbers()
    return {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": _thumbprint(private_key),
        "n": _b64u(numbers.n),
        "e": _b64u(numbers.e),
    }


def _b64u(value: int) -> str:
    """Base64url with no padding, over the minimum big-endian octets (RFC 7518)."""
    octets = (value.bit_length() + 7) // 8
    return base64.urlsafe_b64encode(value.to_bytes(octets, "big")).decode().rstrip("=")


def _thumbprint(private_key: rsa.RSAPrivateKey) -> str:
    """The key's JWK thumbprint (RFC 7638), used as its ``kid``.

    A `kid` must identify the key to whoever verifies a signature. Assigning a
    random one means the identifier lives only in our filename, while the
    library that signs a JWT derives its own from the key material — and Canvas
    then looks up a `kid` our JWKS does not publish. A thumbprint is computed
    from the key itself, so every party independently arrives at the same value.

    SHA-256 over the required members in lexicographic order, no whitespace.
    """
    numbers = private_key.public_key().public_numbers()
    canonical = json.dumps(
        {"e": _b64u(numbers.e), "kty": "RSA", "n": _b64u(numbers.n)},
        separators=(",", ":"),
        sort_keys=True,
    )
    digest = hashlib.sha256(canonical.encode()).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")
