import Link from 'next/link';

import { AppHeader } from '@/components/shell/AppHeader';
import { Icon } from '@/components/shell/Icon';
import { SAMPLE_BOOK, SAMPLE_SEARCH } from '@/lib/preview/sample-book';
import { splitHighlights } from '@/utils/highlight';

export const metadata = { title: 'Search' };

export default function SearchPreview() {
  const { query, total, groups } = SAMPLE_SEARCH;

  return (
    <div className="min-h-dvh bg-surface">
      <AppHeader homeHref="/preview/student" courseCode={SAMPLE_BOOK.course.code} courseTitle={SAMPLE_BOOK.course.title} role="Student" />

      <main className="mx-auto max-w-3xl px-5 pb-20 pt-10 sm:px-8">
        <form action="/preview/search" className="flex border-b-2 border-navy">
          <label htmlFor="q" className="sr-only">Search the textbook</label>
          <Icon name="search" className="h-6 w-6 self-center text-navy" />
          <input
            id="q"
            name="q"
            defaultValue={query}
            className="h-14 min-w-0 flex-1 bg-transparent px-3 font-serif text-2xl text-navy outline-none"
          />
        </form>
        <p className="mt-4 text-sm text-ink-muted" role="status">
          {total} matches in {groups.length} chapters
        </p>

        <div className="mt-8 space-y-10">
          {groups.map((group) => (
            <section key={group.chapterNumber} aria-labelledby={`ch-${group.chapterNumber}`}>
              <h2 id={`ch-${group.chapterNumber}`} className="flex items-baseline gap-3 border-b border-border pb-2">
                <span className="font-serif text-2xl font-light text-accent tabular-nums">{group.chapterNumber}</span>
                <span className="font-semibold text-navy">{group.chapterTitle}</span>
              </h2>
              <ul className="mt-2 divide-y divide-border">
                {group.hits.map((hit) => (
                  <li key={hit.blockId}>
                    <Link href={`/preview/reader#${hit.blockId}`} className="group block py-4">
                      <span className="text-sm font-medium text-ink group-hover:text-accent">
                        {hit.sectionNumber} {hit.sectionTitle}
                      </span>
                      <p className="mt-1 font-serif leading-relaxed text-ink">
                        {splitHighlights(hit.snippet).map((part, i) =>
                          part.match ? (
                            <mark key={i} className="bg-accent/15 px-0.5 text-navy">{part.text}</mark>
                          ) : (
                            <span key={i}>{part.text}</span>
                          ),
                        )}
                      </p>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </main>
    </div>
  );
}
