/**
 * Typed HTTP client for the Django API.
 *
 * Every call returns an {@link ApiResult}: either typed data or a described
 * error. Nothing throws for an expected failure, so a caller cannot forget to
 * handle one — TypeScript will not let it read `.data` without narrowing.
 *
 * Responses are validated by a caller-supplied guard rather than cast. A cast
 * asserts a shape the compiler cannot check; the guard actually checks it, so a
 * backend change surfaces as a `malformed` error at the boundary instead of an
 * `undefined` deep inside a component.
 */

import { apiBaseUrl } from '@/lib/config';
import { apiError, kindForStatus, type ApiResult } from '@/lib/api/errors';

/** Narrows an unknown parsed body to `T`, or returns null if it does not match. */
export type Validator<T> = (value: unknown) => T | null;

export interface RequestOptions {
  readonly method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';
  /** Serialised as JSON. Omit for GET. */
  readonly body?: unknown;
  /** Abort signal, so a component unmount cancels an in-flight request. */
  readonly signal?: AbortSignal;
  /**
   * Next.js caching. Reader content is per-user and course-scoped, so the
   * default is no-store: a cached response could show one student another's
   * view, or serve content from before a publish.
   */
  readonly cache?: RequestCache;
  /** Additional headers. CSRF is added by callers that mutate (task 1.9). */
  readonly headers?: Readonly<Record<string, string>>;
}

const DEFAULT_TIMEOUT_MS = 15_000;

function joinUrl(base: string, path: string): string {
  const normalised = path.startsWith('/') ? path : `/${path}`;
  return `${base}${normalised}`;
}

/**
 * Perform a request and validate the response against `validate`.
 *
 * @param path   Absolute API path, e.g. `/api/health/`.
 * @param validate Guard that narrows the parsed body to `T`.
 */
export async function request<T>(
  path: string,
  validate: Validator<T>,
  options: RequestOptions = {},
): Promise<ApiResult<T>> {
  const { method = 'GET', body, signal, cache = 'no-store', headers = {} } = options;

  // A request with no ceiling can hang a server render indefinitely. The
  // caller's own signal still aborts earlier if it fires first.
  const timeout = new AbortController();
  const timer = setTimeout(() => timeout.abort(), DEFAULT_TIMEOUT_MS);
  const signals: AbortSignal[] = signal ? [signal, timeout.signal] : [timeout.signal];

  let response: Response;
  try {
    response = await fetch(joinUrl(apiBaseUrl(), path), {
      method,
      cache,
      signal: AbortSignal.any(signals),
      credentials: 'include',
      headers: {
        Accept: 'application/json',
        ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...headers,
      },
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    });
  } catch {
    // Includes abort, DNS failure and connection refused. The distinction does
    // not change what the reader is shown, so it is not modelled separately.
    return { ok: false, error: apiError('network') };
  } finally {
    clearTimeout(timer);
  }

  const raw = await response.text().catch(() => '');

  if (!response.ok) {
    return {
      ok: false,
      error: apiError(kindForStatus(response.status), response.status, extractDetail(raw)),
    };
  }

  let parsed: unknown;
  try {
    parsed = raw === '' ? null : JSON.parse(raw);
  } catch {
    return { ok: false, error: apiError('malformed', response.status) };
  }

  const validated = validate(parsed);
  if (validated === null) {
    return { ok: false, error: apiError('malformed', response.status) };
  }
  return { ok: true, data: validated };
}

/**
 * Pull a human-readable message out of an error body without leaking
 * internals. DRF uses `detail`; Django's own error pages are HTML, which is
 * discarded.
 */
function extractDetail(raw: string): string | undefined {
  if (raw === '') return undefined;
  try {
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed === 'object' && parsed !== null && 'detail' in parsed) {
      const { detail } = parsed as { detail: unknown };
      if (typeof detail === 'string') return detail;
    }
  } catch {
    return undefined;
  }
  return undefined;
}
