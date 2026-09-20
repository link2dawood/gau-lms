import Link from 'next/link';

import type { TocNode } from '@/lib/content/types';

/**
 * Hierarchical contents: unit, chapter, section. The chapter containing the
 * current section is expanded; the current section is marked with
 * `aria-current` so assistive technology announces it, not only colour.
 */
export function TableOfContents({
  toc,
  currentId,
  hrefFor,
}: {
  toc: readonly TocNode[];
  currentId: string;
  hrefFor: (node: TocNode) => string;
}) {
  const containsCurrent = (node: TocNode): boolean =>
    node.id === currentId || node.children.some(containsCurrent);

  return (
    <nav aria-label="Table of contents" className="text-sm">
      {toc.map((unit) => (
        <div key={unit.id} className="mb-6">
          <p className="px-3 text-[0.8125rem] font-medium text-ink-muted">
            Unit {unit.number}
            <span className="block font-normal text-ink">{unit.title}</span>
          </p>
          <ol className="mt-2 space-y-px">
            {unit.children.map((chapter) => {
              const open = containsCurrent(chapter);
              return (
                <li key={chapter.id}>
                  <Link
                    href={hrefFor(chapter)}
                    className={`flex gap-3 px-3 py-1.5 hover:bg-surface-muted ${open ? 'font-medium text-navy' : 'text-ink'}`}
                  >
                    <span className="w-5 shrink-0 text-ink-muted tabular-nums">{chapter.number}</span>
                    {chapter.title}
                  </Link>
                  {open && chapter.children.length > 0 && (
                    <ol className="mb-1 ml-[1.625rem] border-l border-border">
                      {chapter.children.map((section) => {
                        const current = section.id === currentId;
                        return (
                          <li key={section.id}>
                            <Link
                              href={hrefFor(section)}
                              aria-current={current ? 'page' : undefined}
                              className={`-ml-px flex gap-3 border-l-2 py-1.5 pl-3 pr-3 ${
                                current
                                  ? 'border-accent bg-accent/[0.07] font-medium text-navy'
                                  : 'border-transparent text-ink-muted hover:text-ink'
                              }`}
                            >
                              <span className="w-7 shrink-0 tabular-nums">{section.number}</span>
                              {section.title}
                            </Link>
                          </li>
                        );
                      })}
                    </ol>
                  )}
                </li>
              );
            })}
          </ol>
        </div>
      ))}
    </nav>
  );
}
