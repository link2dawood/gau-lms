import { fetchHealth } from '@/lib/api/health';

/**
 * Platform status page.
 *
 * This route is a genuine operational view, not a placeholder: it renders on
 * the server, calls Django over the internal network, and shows what the
 * platform reports about itself. It is replaced as an entry point by the
 * student home in task 4.1 and the Canvas launch landing in task 1.12.
 */
export default async function StatusPage() {
  const result = await fetchHealth();

  return (
    <main className="mx-auto max-w-prose px-4 py-16">
      <h1 className="text-2xl font-semibold tracking-tight">GAU Interactive Textbook</h1>
      <p className="mt-2 text-ink-muted">
        Platform status. The textbook is opened from a Canvas course.
      </p>

      <section className="mt-8 rounded-lg border border-border bg-surface-muted p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">
          Service checks
        </h2>

        {result.ok ? (
          <dl className="mt-3 space-y-2">
            {Object.entries(result.data.checks).map(([name, status]) => (
              <div key={name} className="flex items-center justify-between gap-4">
                <dt className="capitalize">{name}</dt>
                <dd
                  className={
                    status === 'ok' ? 'font-medium text-accent' : 'font-medium text-danger'
                  }
                >
                  {status === 'ok' ? 'available' : 'unavailable'}
                </dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className="mt-3 text-danger">{result.error.message}</p>
        )}
      </section>
    </main>
  );
}
