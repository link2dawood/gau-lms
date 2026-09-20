/**
 * Where each role goes after a Canvas launch.
 *
 * Kept as data and a pure function rather than branching inside a component,
 * so the rule can be read in one place and reused by the student home (task
 * 4.1) and the faculty dashboard (task 4.2) without being restated.
 *
 * A role is what the launch said the person is, in this course. It is not
 * permission to do anything: the CMS is offered to an administrator here, but
 * entry is decided by `is_content_admin` on the server, which no Canvas role
 * confers (DECISIONS.md D-023).
 */

import type { Role } from '@/lib/api/launch';

export interface LaunchAction {
  readonly href: string;
  readonly label: string;
}

export interface Destination {
  readonly headline: string;
  readonly primary: LaunchAction;
  /** Offered, not imposed. Absent for a student, who has one way on. */
  readonly secondary?: LaunchAction;
}

const READER: LaunchAction = { href: '/reader', label: 'Open the textbook' };

const DESTINATIONS: Readonly<Record<Role, Destination>> = {
  STUDENT: {
    headline: 'Your textbook is ready',
    primary: READER,
  },
  FACULTY: {
    headline: 'Your course is ready',
    primary: { href: '/faculty', label: 'Go to your dashboard' },
    secondary: READER,
  },
  ADMIN: {
    headline: 'Your course is ready',
    primary: READER,
    secondary: { href: '/cms', label: 'Open the content manager' },
  },
};

/** The landing for a role. Total over Role, so there is no default to get wrong. */
export function destinationFor(role: Role): Destination {
  return DESTINATIONS[role];
}
