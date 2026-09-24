'use client';

import { useEffect, useRef, useState } from 'react';

import { AppHeader, type Role } from '@/components/shell/AppHeader';
import { Icon } from '@/components/shell/Icon';

/**
 * Reader frame: contents sidebar on wide screens, a drawer on narrow ones.
 *
 * The drawer traps nothing and closes on Escape; focus returns to the button
 * that opened it, so keyboard users are not dropped at the top of the page.
 */
export function ReaderShell({
  course,
  role,
  contents,
  progress,
  children,
  initiallyOpen = false,
  homeHref,
  searchHref,
}: {
  // Plain data rather than a render function: this is a client component, and
  // functions cannot cross the server/client boundary.
  course: { code: string; title: string };
  role: Role;
  contents: React.ReactNode;
  /** 0 to 1: how far through the book the current section is. */
  progress: number;
  children: React.ReactNode;
  initiallyOpen?: boolean;
  homeHref?: string;
  /** Omitted until search exists (task 2.13), which hides the control. */
  searchHref?: string;
}) {
  const [open, setOpen] = useState(initiallyOpen);
  const buttonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
        buttonRef.current?.focus();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  const menuButton = (
    <button
      ref={buttonRef}
      type="button"
      onClick={() => setOpen(true)}
      aria-expanded={open}
      aria-controls="contents-drawer"
      className="-ml-1 grid h-9 w-9 place-items-center text-navy lg:hidden"
    >
      <Icon name="menu" label="Open contents" />
    </button>
  );

  return (
    <div className="min-h-dvh bg-surface">
      <AppHeader
        courseCode={course.code}
        courseTitle={course.title}
        role={role}
        {...(homeHref !== undefined ? { homeHref } : {})}
        {...(searchHref !== undefined ? { searchHref } : {})}
      >
        {menuButton}
      </AppHeader>
      {/* Sticky, directly under the 3.5rem header: a progress indicator that
          scrolls away stops answering the question it exists for, which is
          "how much of this is left" while you are reading. The track is a
          sibling so the filled bar can be a percentage of full width. */}
      <div
        className="sticky top-14 z-20 h-[3px] bg-border"
        role="progressbar"
        aria-label="Progress through the textbook"
        aria-valuenow={Math.round(progress * 100)}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div className="h-full bg-accent" style={{ width: `${Math.round(progress * 100)}%` }} />
      </div>
      <div className="mx-auto flex max-w-[88rem]">
        <aside className="sticky top-14 hidden h-[calc(100dvh-3.5rem)] w-80 shrink-0 overflow-y-auto border-r border-border py-8 pl-3 pr-4 lg:block">
          {contents}
        </aside>
        <main className="min-w-0 flex-1 px-5 pb-24 pt-8 sm:px-10 lg:px-16">{children}</main>
      </div>

      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            type="button"
            aria-label="Close contents"
            className="absolute inset-0 bg-navy/40"
            onClick={() => setOpen(false)}
          />
          <div
            id="contents-drawer"
            role="dialog"
            aria-modal="true"
            aria-label="Contents"
            className="absolute inset-y-0 left-0 flex w-[min(22rem,88vw)] flex-col bg-surface"
          >
            <div className="flex h-14 items-center justify-between border-b border-border px-4">
              <p className="font-semibold text-navy">Contents</p>
              <button
                type="button"
                onClick={() => {
                  setOpen(false);
                  buttonRef.current?.focus();
                }}
                className="grid h-9 w-9 place-items-center text-ink-muted"
              >
                <Icon name="close" label="Close contents" />
              </button>
            </div>
            <div className="overflow-y-auto py-6 pl-2 pr-3">{contents}</div>
          </div>
        </div>
      )}
    </div>
  );
}
