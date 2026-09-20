import { AppHeader } from '@/components/shell/AppHeader';
import { SAMPLE_BOOK, SAMPLE_VERSIONS } from '@/lib/preview/sample-book';
import { cn } from '@/utils/cn';

export const metadata = { title: 'Version history, 6.4 Blood pressure' };

const STATUS_LABEL = { draft: 'Draft', published: 'Published', superseded: 'Earlier version' } as const;

interface DiffLine {
  readonly kind: 'same' | 'removed' | 'added';
  readonly text: string;
}

// Comparison of version 7 (published) with version 8 (draft), block by block.
const LEFT: readonly DiffLine[] = [
  { kind: 'same', text: 'Most measurement error comes from preparation and positioning rather than from the device.' },
  { kind: 'removed', text: 'The cuff should cover most of the upper arm.' },
  { kind: 'same', text: 'Figure 6.4. Systolic ranges by category.' },
];
const RIGHT: readonly DiffLine[] = [
  { kind: 'same', text: 'Most measurement error comes from preparation and positioning rather than from the device.' },
  { kind: 'added', text: 'The cuff bladder encircles at least 80% of the arm. A cuff that is too small overestimates pressure.' },
  { kind: 'same', text: 'Figure 6.4. Systolic ranges by category.' },
  {
    kind: 'added',
    text: 'Practice point: Document what you did, not only what you found. Record the arm used, patient position, and cuff size alongside the reading.',
  },
];

function Column({ title, subtitle, lines }: { title: string; subtitle: string; lines: readonly DiffLine[] }) {
  return (
    <div className="min-w-0 border border-border bg-surface">
      <div className="border-b border-border px-5 py-3">
        <p className="font-semibold text-navy">{title}</p>
        <p className="text-sm text-ink-muted">{subtitle}</p>
      </div>
      <ol className="space-y-2 p-5 font-serif text-[0.9375rem] leading-relaxed">
        {lines.map((line, i) => (
          <li
            key={i}
            className={cn(
              'border-l-2 py-1.5 pl-3',
              line.kind === 'same' && 'border-transparent text-ink-muted',
              line.kind === 'removed' && 'border-danger bg-danger/[0.06] text-ink line-through decoration-danger/50',
              line.kind === 'added' && 'border-accent bg-accent/[0.08] text-ink',
            )}
          >
            <span className="sr-only">{line.kind === 'same' ? 'Unchanged: ' : line.kind === 'added' ? 'Added: ' : 'Removed: '}</span>
            {line.text}
          </li>
        ))}
      </ol>
    </div>
  );
}

export default function VersionHistoryPreview() {
  return (
    <div className="min-h-dvh bg-surface-muted">
      <AppHeader courseCode="Content management" courseTitle={SAMPLE_BOOK.title} role="Content administrator" />

      <main className="mx-auto max-w-7xl px-5 pb-20 pt-8 sm:px-8">
        <p className="text-sm text-ink-muted">Section 6.4</p>
        <h1 className="mt-1 font-serif text-3xl font-semibold text-navy">Version history: Blood pressure</h1>
        <p className="mt-2 max-w-2xl text-ink-muted">
          Every publish is kept. Restoring an earlier version creates a new draft, so nothing is overwritten.
        </p>

        <div className="mt-8 grid gap-6 lg:grid-cols-[20rem_1fr]">
          <ol className="divide-y divide-border self-start border border-border bg-surface" aria-label="Versions">
            {SAMPLE_VERSIONS.map((v) => {
              const selected = v.number >= 7;
              return (
                <li key={v.number} className={cn('p-4', selected && 'bg-accent/[0.06]')}>
                  <div className="flex items-baseline justify-between gap-3">
                    <p className="font-semibold text-ink">Version {v.number}</p>
                    <span
                      className={cn(
                        'text-xs',
                        v.status === 'published' && 'font-medium text-accent',
                        v.status !== 'published' && 'text-ink-muted',
                      )}
                    >
                      {STATUS_LABEL[v.status]}
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-ink">{v.note}</p>
                  <p className="mt-1 text-xs text-ink-muted">
                    {v.author}, {v.publishedOn}
                  </p>
                  {v.status === 'superseded' && (
                    <button type="button" className="mt-2 text-sm font-medium text-accent hover:underline">
                      Restore as new draft
                    </button>
                  )}
                </li>
              );
            })}
          </ol>

          <section aria-label="Comparison">
            <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-sm text-ink-muted">
              <span>Comparing version 7 with version 8</span>
              <span className="flex items-center gap-1.5"><span className="h-3 w-3 bg-accent/30" /> Added</span>
              <span className="flex items-center gap-1.5"><span className="h-3 w-3 bg-danger/25" /> Removed</span>
            </div>
            <div className="mt-3 grid gap-4 md:grid-cols-2">
              <Column title="Version 7" subtitle="Published 9 September 2026" lines={LEFT} />
              <Column title="Version 8" subtitle="Draft, not published" lines={RIGHT} />
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
