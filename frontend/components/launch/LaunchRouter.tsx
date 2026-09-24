'use client';

/**
 * Resolves a Canvas launch into a session, then shows the reader where to go.
 *
 * Runs in the browser because it needs three things the server cannot see: the
 * launch ticket in the address bar, the session cookie as the browser actually
 * kept it, and the ability to remove the ticket from the URL afterwards.
 */

import Link from 'next/link';
import { useEffect, useState } from 'react';

import { fetchLaunchContext, redeemLaunchTicket, type LaunchContext } from '@/lib/api/launch';
import type { ApiErrorKind } from '@/lib/api/errors';
import { destinationFor } from '@/lib/launch/routing';

const TICKET_PARAM = 'lt';
/** Set when the launch came from a deep link pointing at one part of the book. */
const NODE_PARAM = 'node';

type State =
  | { readonly phase: 'resolving' }
  | { readonly phase: 'ready'; readonly context: LaunchContext }
  | { readonly phase: 'no-session' }
  | { readonly phase: 'error'; readonly message: string };

/** Kinds that mean "not signed in", as opposed to "something broke". */
function meansNoSession(kind: ApiErrorKind): boolean {
  return kind === 'unauthenticated' || kind === 'forbidden';
}

function readTicket(): string | null {
  return new URLSearchParams(window.location.search).get(TICKET_PARAM);
}

function readNode(): string | null {
  return new URLSearchParams(window.location.search).get(NODE_PARAM);
}

/**
 * Carry a deep link's target through to the destination.
 *
 * Kept on the destination URL rather than in component state so that the link
 * a reader copies, or opens in a new tab, still points at the same chapter.
 */
function withNode(href: string, nodeId: string | null): string {
  if (nodeId === null || nodeId === '') return href;
  return `${href}?${new URLSearchParams({ [NODE_PARAM]: nodeId }).toString()}`;
}

/**
 * Take the ticket out of the address bar.
 *
 * It is single-use and short-lived, but leaving it in the URL would put a
 * credential into browser history and into any `Referer` the page later sends
 * (DECISIONS.md D-038).
 *
 * The current `history.state` is passed through rather than replaced with
 * null: the App Router keeps its own routing tree there, and erasing it breaks
 * back and forward navigation away from this page.
 */
function stripTicket(): void {
  const url = new URL(window.location.href);
  url.searchParams.delete(TICKET_PARAM);
  window.history.replaceState(
    window.history.state,
    '',
    `${url.pathname}${url.search}${url.hash}`,
  );
}

export function LaunchRouter(): JSX.Element {
  const [state, setState] = useState<State>({ phase: 'resolving' });

  useEffect(() => {
    const controller = new AbortController();

    async function resolve(): Promise<void> {
      const ticket = readTicket();
      let result = await fetchLaunchContext({ signal: controller.signal });
      if (controller.signal.aborted) return;

      // The cookie did not survive. If the launch handed us a ticket, that is
      // exactly what it is for.
      if (!result.ok && meansNoSession(result.error.kind) && ticket !== null) {
        // The outcome of the redemption is deliberately ignored. A 200 whose
        // body fails validation still carried a Set-Cookie the browser honoured,
        // so the only trustworthy answer is to ask for the context again.
        await redeemLaunchTicket(ticket, controller.signal);
        if (controller.signal.aborted) return;

        result = await fetchLaunchContext({ signal: controller.signal });
        if (controller.signal.aborted) return;
      }

      const next: State = result.ok
        ? { phase: 'ready', context: result.data }
        : meansNoSession(result.error.kind)
          ? { phase: 'no-session' }
          : { phase: 'error', message: result.error.message };

      // Only once the ticket can no longer help. A transient failure keeps it:
      // the ticket may still have life left, and a reload is the one thing that
      // could still recover the session.
      if (ticket !== null && next.phase !== 'error') stripTicket();

      setState(next);
    }

    void resolve();
    return () => controller.abort();
  }, []);

  if (state.phase === 'resolving') {
    return <Shell title="Opening your textbook…" />;
  }

  if (state.phase === 'no-session') {
    return (
      <Shell title="Please open the textbook from Canvas">
        <p className="mt-2 text-ink-muted">
          This page needs to be opened from your Canvas course, so we know which course you
          are in.
        </p>
      </Shell>
    );
  }

  if (state.phase === 'error') {
    return (
      <Shell title="The textbook could not be opened">
        <p className="mt-2 text-danger">{state.message}</p>
        <p className="mt-2 text-ink-muted">
          Please try again in a few minutes, or contact your administrator.
        </p>
      </Shell>
    );
  }

  const { course, role, user } = state.context;
  const destination = destinationFor(role);
  const nodeId = readNode();
  const courseName = course.title !== '' ? course.title : course.label;

  return (
    <Shell title={destination.headline}>
      <p className="mt-2 text-ink-muted">
        {user.name !== '' ? `${user.name} — ` : ''}
        {courseName !== '' ? courseName : 'your course'}
      </p>

      <div className="mt-8 flex flex-wrap gap-3">
        <Link
          href={withNode(destination.primary.href, nodeId)}
          className="rounded-md bg-accent px-4 py-2 font-medium text-white"
        >
          {destination.primary.label}
        </Link>
        {destination.secondary !== undefined && (
          <Link
            href={destination.secondary.href}
            className="rounded-md border border-border px-4 py-2 font-medium"
          >
            {destination.secondary.label}
          </Link>
        )}
      </div>
    </Shell>
  );
}

function Shell({
  title,
  children,
}: {
  readonly title: string;
  readonly children?: React.ReactNode;
}): JSX.Element {
  return (
    <main className="mx-auto max-w-prose px-4 py-16">
      <h1 aria-live="polite" className="text-2xl font-semibold tracking-tight">
        {title}
      </h1>
      {children}
    </main>
  );
}
