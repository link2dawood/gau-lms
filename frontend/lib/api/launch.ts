/**
 * Typed bindings for the Canvas launch context.
 *
 * Two endpoints, both served by `apps/lti` (tasks 1.9 and 1.11):
 *
 *   GET  /lti/context/   who the reader is and which course they are in
 *   POST /lti/session/   exchange a launch ticket for a session
 *
 * The second exists because a browser can discard the session cookie the
 * launch set, since inside a Canvas iframe it is a third-party cookie.
 */

import { request, type RequestOptions } from '@/lib/api/client';
import type { ApiResult } from '@/lib/api/errors';

/** The platform's three roles. Mirrors `courses.Role` on the backend. */
export type Role = 'STUDENT' | 'FACULTY' | 'ADMIN';

export interface LaunchCourse {
  readonly id: string;
  readonly title: string;
  readonly label: string;
}

export interface LaunchUser {
  readonly name: string;
  readonly email: string;
}

export interface LaunchContext {
  readonly course: LaunchCourse;
  readonly role: Role;
  readonly user: LaunchUser;
}

export interface RedeemedSession {
  readonly courseId: string;
  readonly role: Role;
}

function isRole(value: unknown): value is Role {
  return value === 'STUDENT' || value === 'FACULTY' || value === 'ADMIN';
}

function asString(value: unknown): string | null {
  return typeof value === 'string' ? value : null;
}

/** Validates rather than casts, so a backend contract change is caught here. */
export function parseLaunchContext(value: unknown): LaunchContext | null {
  if (typeof value !== 'object' || value === null) return null;
  const candidate = value as { course?: unknown; role?: unknown; user?: unknown };

  if (!isRole(candidate.role)) return null;
  if (typeof candidate.course !== 'object' || candidate.course === null) return null;
  if (typeof candidate.user !== 'object' || candidate.user === null) return null;

  const course = candidate.course as { id?: unknown; title?: unknown; label?: unknown };
  const user = candidate.user as { name?: unknown; email?: unknown };

  const id = asString(course.id);
  const title = asString(course.title);
  const label = asString(course.label);
  const name = asString(user.name);
  const email = asString(user.email);
  if (id === null || title === null || label === null) return null;
  if (name === null || email === null) return null;

  return { course: { id, title, label }, role: candidate.role, user: { name, email } };
}

export function parseRedeemedSession(value: unknown): RedeemedSession | null {
  if (typeof value !== 'object' || value === null) return null;
  const candidate = value as { course_id?: unknown; role?: unknown };
  const courseId = asString(candidate.course_id);
  if (courseId === null || !isRole(candidate.role)) return null;
  return { courseId, role: candidate.role };
}

export function fetchLaunchContext(
  options: RequestOptions = {},
): Promise<ApiResult<LaunchContext>> {
  return request('/lti/context/', parseLaunchContext, options);
}

/**
 * Exchange a launch ticket for a session.
 *
 * The ticket travels in a header, not a body, and that is the endpoint's CSRF
 * defence rather than a convention: a cross-site form can POST here but cannot
 * set a custom header (DECISIONS.md D-038). Sending it any other way will be
 * refused.
 */
export function redeemLaunchTicket(
  ticket: string,
  signal?: AbortSignal,
): Promise<ApiResult<RedeemedSession>> {
  return request('/lti/session/', parseRedeemedSession, {
    method: 'POST',
    headers: { 'X-Launch-Ticket': ticket },
    ...(signal ? { signal } : {}),
  });
}
