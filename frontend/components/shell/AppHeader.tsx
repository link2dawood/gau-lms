import Link from 'next/link';

import { Icon } from '@/components/shell/Icon';

export type Role = 'Student' | 'Faculty' | 'Content administrator';

/**
 * Top bar shown in every view. Course and role come from the Canvas launch
 * (tasks 1.8, 1.12); the reader never asks who someone is.
 */
export function AppHeader({
  courseCode,
  courseTitle,
  role,
  searchHref,
  homeHref = '/reader',
  children,
}: {
  courseCode: string;
  courseTitle: string;
  role: Role;
  /** Omitted until search exists (task 2.13); the control is hidden without it. */
  searchHref?: string;
  /** Where the wordmark leads. The student home takes this over at task 4.1. */
  homeHref?: string;
  children?: React.ReactNode;
}) {
  return (
    <header className="sticky top-0 z-30 border-b border-border bg-surface">
      <div className="flex h-14 items-center gap-3 px-4 lg:px-6">
        {children}
        <Link href={homeHref} className="flex shrink-0 items-center gap-2.5 text-navy">
          <span className="grid h-7 w-7 place-items-center bg-navy font-serif text-sm font-semibold text-white">G</span>
          <span className="font-semibold tracking-tight">GAU Textbook</span>
        </Link>
        <span className="mx-1 hidden h-5 w-px bg-border md:block" aria-hidden />
        <p className="hidden min-w-0 truncate text-sm text-ink-muted md:block">
          <span className="font-medium text-ink">{courseCode}</span> {courseTitle}
        </p>
        <div className="ml-auto flex items-center gap-3">
          {searchHref !== undefined && (
            <Link
              href={searchHref}
              className="flex h-9 items-center gap-2 border border-border px-3 text-sm text-ink-muted hover:border-accent hover:text-ink"
            >
              <Icon name="search" className="h-4 w-4" />
              <span className="hidden sm:inline">Search the textbook</span>
            </Link>
          )}
          <span className="hidden text-sm text-ink-muted lg:inline">{role}</span>
        </div>
      </div>
    </header>
  );
}
