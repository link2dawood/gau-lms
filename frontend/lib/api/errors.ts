/**
 * API failure modes, as data rather than thrown exceptions.
 *
 * The reader has to render something sensible for each of these — a launch
 * that has expired is a different screen from a section that does not exist,
 * which is different again from the backend being unreachable. A single
 * `Error` would flatten that distinction and push the decision into a string
 * comparison at the call site.
 */

export type ApiErrorKind =
  /** No response at all: network failure, DNS, connection refused, abort. */
  | 'network'
  /** Response was not valid JSON, or did not match the expected shape. */
  | 'malformed'
  /** 401 — no valid session. The Canvas launch must be repeated. */
  | 'unauthenticated'
  /** 403 — authenticated but not permitted, including cross-course access. */
  | 'forbidden'
  /** 404 — the resource does not exist, or is not published for this reader. */
  | 'not_found'
  /** 4xx other than the above. */
  | 'client'
  /** 5xx. */
  | 'server';

export interface ApiError {
  readonly kind: ApiErrorKind;
  /** Safe to show a user. Never carries backend internals. */
  readonly message: string;
  /** Absent when no response arrived. */
  readonly status?: number;
  /** Parsed error body, when the backend supplied one. */
  readonly detail?: string;
}

/** A call either succeeded with a value, or failed with a described error. */
export type ApiResult<T> =
  | { readonly ok: true; readonly data: T }
  | { readonly ok: false; readonly error: ApiError };

const MESSAGES: Record<ApiErrorKind, string> = {
  network: 'The textbook service could not be reached. Check your connection and try again.',
  malformed: 'The textbook service returned an unexpected response.',
  unauthenticated: 'Your session has expired. Reopen the textbook from Canvas to continue.',
  forbidden: 'You do not have access to this content in this course.',
  not_found: 'That content could not be found.',
  client: 'The request could not be completed.',
  server: 'The textbook service is temporarily unavailable. Please try again shortly.',
};

export function kindForStatus(status: number): ApiErrorKind {
  if (status === 401) return 'unauthenticated';
  if (status === 403) return 'forbidden';
  if (status === 404) return 'not_found';
  if (status >= 500) return 'server';
  return 'client';
}

export function apiError(kind: ApiErrorKind, status?: number, detail?: string): ApiError {
  return {
    kind,
    message: MESSAGES[kind],
    ...(status !== undefined ? { status } : {}),
    ...(detail !== undefined ? { detail } : {}),
  };
}
