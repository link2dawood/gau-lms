/**
 * Typed binding for the platform readiness endpoint.
 *
 * This is the first real endpoint (`config/health.py`, task 0.3) and the
 * pattern every later binding follows: a response type, a guard that checks it,
 * and a function returning a typed result.
 */

import { request } from '@/lib/api/client';
import type { ApiResult } from '@/lib/api/errors';

export type CheckStatus = 'ok' | 'error';

export interface HealthResponse {
  readonly status: CheckStatus;
  readonly checks: Readonly<Record<string, CheckStatus>>;
}

function isCheckStatus(value: unknown): value is CheckStatus {
  return value === 'ok' || value === 'error';
}

/** Validates the body rather than asserting it, so a contract change is caught here. */
export function parseHealthResponse(value: unknown): HealthResponse | null {
  if (typeof value !== 'object' || value === null) return null;
  const candidate = value as { status?: unknown; checks?: unknown };

  if (!isCheckStatus(candidate.status)) return null;
  if (typeof candidate.checks !== 'object' || candidate.checks === null) return null;

  const checks: Record<string, CheckStatus> = {};
  for (const [name, status] of Object.entries(candidate.checks as Record<string, unknown>)) {
    if (!isCheckStatus(status)) return null;
    checks[name] = status;
  }

  return { status: candidate.status, checks };
}

/**
 * Fetch platform readiness.
 *
 * Note this returns `ok: false` with a `server` error when the platform reports
 * itself unhealthy, because the endpoint answers 503 in that case — the call
 * succeeded, the platform did not.
 */
export function fetchHealth(signal?: AbortSignal): Promise<ApiResult<HealthResponse>> {
  return request('/api/health/', parseHealthResponse, signal ? { signal } : {});
}
