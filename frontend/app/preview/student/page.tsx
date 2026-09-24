import Link from 'next/link';

import { AppHeader } from '@/components/shell/AppHeader';
import { Icon } from '@/components/shell/Icon';
import { SAMPLE_BOOK, SAMPLE_TOC } from '@/lib/preview/sample-book';

export const metadata = { title: 'Home' };

export default function StudentHomePreview() {
  return (
    <div className="min-h-dvh bg-surface-muted">
      <AppHeader homeHref="/preview/student"
        courseCode={SAMPLE_BOOK.course.code}
        courseTitle={SAMPLE_BOOK.course.title}
        role="Student"
        searchHref="/preview/search?q=blood+pressure"
      />

      <main className="mx-auto max-w-5xl px-5 pb-20 pt-10 sm:px-8">
        <p className="text-sm text-ink-muted">{SAMPLE_BOOK.course.code} textbook</p>
        <h1 className="mt-1 font-serif text-3xl font-semibold text-navy sm:text-[2.5rem] sm:leading-tight">
          {SAMPLE_BOOK.title}
        </h1>

        <section aria-labelledby="continue" className="mt-10 bg-navy text-white">
          <div className="grid gap-6 p-6 sm:grid-cols-[auto_1fr_auto] sm:items-center sm:p-8">
            <span className="font-serif text-7xl font-light leading-none text-white/35 tabular-nums">6</span>
            <div>
              <h2 id="continue" className="text-sm text-white/70">Continue where you left off</h2>
              <p className="mt-1 font-serif text-2xl font-semibold">6.4 Blood pressure</p>
              <p className="mt-1 text-sm text-white/70">Chapter 6, Vital signs. Last read on 11 September.</p>
            </div>
            <Link
              href="/preview/reader"
              className="inline-flex h-11 items-center justify-center bg-white px-5 font-medium text-navy hover:bg-white/90"
            >
              Continue reading
            </Link>
          </div>
          <div className="h-1 bg-white/15">
            <div className="h-full w-[46%] bg-accent" />
          </div>
        </section>

        <section aria-labelledby="contents" className="mt-12">
          <div className="flex items-baseline justify-between gap-4">
            <h2 id="contents" className="text-lg font-semibold text-navy">Contents</h2>
            <p className="text-sm text-ink-muted">3 units, 9 chapters</p>
          </div>

          <div className="mt-4 grid gap-px border border-border bg-border md:grid-cols-3">
            {SAMPLE_TOC.map((unit) => (
              <div key={unit.id} className="bg-surface p-5">
                <p className="text-sm text-ink-muted">Unit {unit.number}</p>
                <h3 className="mt-0.5 font-semibold text-ink">{unit.title}</h3>
                <ol className="mt-4 space-y-2.5 text-[0.9375rem]">
                  {unit.children.map((chapter) => (
                    <li key={chapter.id}>
                      <Link href="/preview/reader" className="group flex gap-3">
                        <span className="w-4 shrink-0 text-ink-muted tabular-nums">{chapter.number}</span>
                        <span className="text-ink group-hover:text-accent">{chapter.title}</span>
                      </Link>
                    </li>
                  ))}
                </ol>
              </div>
            ))}
          </div>
        </section>

        <form action="/preview/search" className="mt-12 flex max-w-xl border border-border bg-surface focus-within:border-accent">
          <label htmlFor="q" className="sr-only">Search the textbook</label>
          <Icon name="search" className="ml-4 h-5 w-5 self-center text-ink-muted" />
          <input
            id="q"
            name="q"
            placeholder="Search the textbook"
            className="h-12 min-w-0 flex-1 bg-transparent px-3 outline-none placeholder:text-ink-muted"
          />
          <button type="submit" className="bg-accent px-5 font-medium text-white hover:bg-accent/90">Search</button>
        </form>
      </main>
    </div>
  );
}
