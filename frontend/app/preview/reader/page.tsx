import Link from 'next/link';

import { ContentRenderer } from '@/components/content/ContentRenderer';
import { ReaderShell } from '@/components/reader/ReaderShell';
import { TableOfContents } from '@/components/reader/TableOfContents';
import { Icon } from '@/components/shell/Icon';
import { SAMPLE_BOOK, SAMPLE_SECTION_BLOOD_PRESSURE, SAMPLE_TOC } from '@/lib/preview/sample-book';

export const metadata = { title: '6.4 Blood pressure' };

export default function ReaderPreview({ searchParams }: { searchParams: { contents?: string } }) {
  const contents = (
    <TableOfContents toc={SAMPLE_TOC} currentId="s64" hrefFor={() => '/preview/reader'} />
  );

  return (
    <ReaderShell
      course={SAMPLE_BOOK.course}
      role="Student"
      contents={contents}
      progress={0.46}
      initiallyOpen={searchParams.contents === 'open'}
    >
      <article className="mx-auto max-w-prose">
        <nav aria-label="Breadcrumb" className="text-sm text-ink-muted">
          <ol className="flex flex-wrap items-center gap-x-1.5 gap-y-1">
            <li>Unit 2</li>
            <li aria-hidden>/</li>
            <li>Chapter 6, Vital signs</li>
            <li aria-hidden>/</li>
            <li aria-current="page" className="text-ink">Blood pressure</li>
          </ol>
        </nav>

        <header className="mt-10 flex items-end gap-5 border-b border-border pb-8">
          <span className="font-serif text-[5.5rem] font-light leading-[0.8] text-accent tabular-nums">6</span>
          <div className="pb-1">
            <p className="text-sm text-ink-muted">Section 6.4</p>
            <h1 className="mt-1 font-serif text-[2.125rem] font-semibold leading-tight text-navy">Blood pressure</h1>
          </div>
        </header>

        <ContentRenderer document={SAMPLE_SECTION_BLOOD_PRESSURE} />

        <p className="mt-12 text-sm text-ink-muted">Your place in this section is saved automatically.</p>

        <nav aria-label="Section navigation" className="mt-6 grid grid-cols-2 gap-4 border-t border-border pt-6">
          <Link href="/preview/reader" className="group">
            <span className="flex items-center gap-1 text-sm text-ink-muted">
              <Icon name="chevronLeft" className="h-4 w-4" /> Previous
            </span>
            <span className="mt-1 block font-medium text-navy group-hover:text-accent">6.3 Respiration</span>
          </Link>
          <Link href="/preview/reader" className="group text-right">
            <span className="flex items-center justify-end gap-1 text-sm text-ink-muted">
              Next <Icon name="chevronRight" className="h-4 w-4" />
            </span>
            <span className="mt-1 block font-medium text-navy group-hover:text-accent">6.5 Oxygen saturation</span>
          </Link>
        </nav>
      </article>
    </ReaderShell>
  );
}
