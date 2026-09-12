'use client';

import { useEffect } from 'react';

/**
 * Route-level error boundary.
 *
 * The digest is shown because it is the only thing that ties what a student
 * saw to a line in the server log — without it, "it broke" is unactionable.
 * The underlying message is not shown: it can carry internals.
 */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="mx-auto max-w-prose px-4 py-16">
      <h1 className="text-2xl font-semibold tracking-tight">Something went wrong</h1>
      <p className="mt-2 text-ink-muted">
        The page could not be displayed. Try again, or reopen the textbook from Canvas.
      </p>
      {error.digest !== undefined && (
        <p className="mt-4 text-sm text-ink-muted">
          Reference: <code className="font-mono">{error.digest}</code>
        </p>
      )}
      <button
        type="button"
        onClick={reset}
        className="mt-6 rounded-md bg-accent px-4 py-2 font-medium text-white"
      >
        Try again
      </button>
    </main>
  );
}
