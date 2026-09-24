import Link from 'next/link';

import { AppHeader } from '@/components/shell/AppHeader';
import { SAMPLE_BOOK, SAMPLE_TOC } from '@/lib/preview/sample-book';

export const metadata = { title: 'Faculty dashboard' };

const PLANNED = [
  { title: 'Class reading progress', note: 'See which sections the class has reached.' },
  { title: 'Annotations and discussion', note: 'Add notes to passages for your students.' },
  { title: 'Assessments', note: 'Attach questions to sections and send grades to Canvas.' },
] as const;

export default function FacultyPreview() {
  const chapters = SAMPLE_TOC.reduce((n, unit) => n + unit.children.length, 0);

  return (
    <div className="min-h-dvh bg-surface-muted">
      <AppHeader homeHref="/preview/student"
        courseCode={SAMPLE_BOOK.course.code}
        courseTitle={SAMPLE_BOOK.course.title}
        role="Faculty"
        searchHref="/preview/search?q=blood+pressure"
      />

      <main className="mx-auto max-w-5xl px-5 pb-20 pt-10 sm:px-8">
        <p className="text-sm text-ink-muted">Teaching {SAMPLE_BOOK.course.code}</p>
        <h1 className="mt-1 font-serif text-3xl font-semibold text-navy">{SAMPLE_BOOK.course.title}</h1>

        <div className="mt-10 grid gap-6 lg:grid-cols-[1.4fr_1fr]">
          <section aria-labelledby="book" className="border border-border bg-surface p-6">
            <h2 id="book" className="text-sm text-ink-muted">Textbook linked to this course</h2>
            <p className="mt-2 font-serif text-2xl font-semibold text-navy">{SAMPLE_BOOK.title}</p>
            <dl className="mt-6 grid grid-cols-3 gap-4 border-t border-border pt-5">
              <div>
                <dt className="text-sm text-ink-muted">Units</dt>
                <dd className="mt-1 text-2xl font-semibold text-ink tabular-nums">{SAMPLE_TOC.length}</dd>
              </div>
              <div>
                <dt className="text-sm text-ink-muted">Chapters</dt>
                <dd className="mt-1 text-2xl font-semibold text-ink tabular-nums">{chapters}</dd>
              </div>
              <div>
                <dt className="text-sm text-ink-muted">Last updated</dt>
                <dd className="mt-1 text-base font-medium text-ink">9 Sep 2026</dd>
              </div>
            </dl>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link href="/preview/reader" className="inline-flex h-10 items-center bg-navy px-4 font-medium text-white hover:bg-navy/90">
                Open textbook
              </Link>
              <Link href="/preview/search?q=blood+pressure" className="inline-flex h-10 items-center border border-border px-4 font-medium text-navy hover:border-accent">
                Search
              </Link>
            </div>
          </section>

          <section aria-labelledby="resume" className="border border-border bg-surface p-6">
            <h2 id="resume" className="text-sm text-ink-muted">Your reading position</h2>
            <p className="mt-2 font-semibold text-navy">6.4 Blood pressure</p>
            <p className="mt-1 text-sm text-ink-muted">Chapter 6, Vital signs</p>
            <Link href="/preview/reader" className="mt-5 inline-block font-medium text-accent hover:underline">
              Continue reading
            </Link>
          </section>
        </div>

        <section aria-labelledby="planned" className="mt-12">
          <h2 id="planned" className="text-lg font-semibold text-navy">Teaching tools</h2>
          <p className="mt-1 text-sm text-ink-muted">
            Planned for a later phase. These are not available in this release.
          </p>
          <ul className="mt-4 grid gap-px border border-dashed border-border sm:grid-cols-3">
            {PLANNED.map((tool) => (
              <li key={tool.title} className="p-5">
                <p className="font-medium text-ink-muted">{tool.title}</p>
                <p className="mt-1 text-sm text-ink-muted">{tool.note}</p>
              </li>
            ))}
          </ul>
        </section>
      </main>
    </div>
  );
}
