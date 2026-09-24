import Link from 'next/link';

/**
 * Hierarchical contents, to whatever depth the book actually has.
 *
 * Deliberately recursive rather than unit/chapter/section: the content model
 * has four levels, and an imported book can be irregular enough that a
 * section attaches directly under a unit (D-055). A component that assumed
 * three levels would silently stop rendering the fourth.
 *
 * The branch containing the current node is expanded and everything else is
 * collapsed, so a long book stays navigable. The current entry carries
 * `aria-current="page"`, so it is announced rather than only coloured.
 */

/**
 * A line of contents, as this component needs it.
 *
 * Its own view model rather than the API's `TocEntry`, because `number` is not
 * something the API sends. Display numbering has to be stable — a citation of
 * "6.4" cannot move — and deriving it here from a published-only tree would
 * shift every number whenever a neighbouring chapter was unpublished. Until
 * that is settled it is supplied by the preview and absent in the reader.
 */
export interface ContentsItem {
  readonly id: string;
  readonly title: string;
  readonly number?: string;
  readonly children: readonly ContentsItem[];
}

const INDENT = ['pl-3', 'pl-6', 'pl-9', 'pl-12', 'pl-14'] as const;

function indentFor(depth: number): string {
  return INDENT[Math.min(depth, INDENT.length - 1)] ?? 'pl-3';
}

function Branch({
  items,
  currentId,
  hrefFor,
  depth,
}: {
  items: readonly ContentsItem[];
  currentId: string;
  hrefFor: (item: ContentsItem) => string;
  depth: number;
}) {
  const contains = (item: ContentsItem): boolean =>
    item.id === currentId || item.children.some(contains);

  return (
    <ol className={depth === 0 ? 'space-y-px' : 'mb-1 space-y-px border-l border-border'}>
      {items.map((item) => {
        const current = item.id === currentId;
        const open = contains(item);
        return (
          <li key={item.id}>
            <Link
              href={hrefFor(item)}
              aria-current={current ? 'page' : undefined}
              className={`flex gap-3 py-1.5 pr-3 ${indentFor(depth)} ${
                current
                  ? 'border-l-2 border-accent bg-accent/[0.07] font-medium text-navy'
                  : `border-l-2 border-transparent hover:bg-surface-muted ${
                      open ? 'font-medium text-navy' : 'text-ink'
                    }`
              }`}
            >
              {item.number !== undefined && (
                <span className="shrink-0 text-ink-muted tabular-nums">{item.number}</span>
              )}
              <span className="min-w-0">{item.title}</span>
            </Link>
            {open && item.children.length > 0 && (
              <Branch
                items={item.children}
                currentId={currentId}
                hrefFor={hrefFor}
                depth={depth + 1}
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}

export function TableOfContents({
  items,
  currentId,
  hrefFor,
}: {
  items: readonly ContentsItem[];
  currentId: string;
  hrefFor: (item: ContentsItem) => string;
}) {
  if (items.length === 0) {
    // A published book whose chapters are all still drafts. Not an error —
    // the reader says so rather than showing an empty rail with no
    // explanation (D-053: the two gates are independent).
    return (
      <p className="px-3 text-sm text-ink-muted">Nothing has been published in this book yet.</p>
    );
  }
  return (
    <nav aria-label="Table of contents" className="text-sm">
      <Branch items={items} currentId={currentId} hrefFor={hrefFor} depth={0} />
    </nav>
  );
}
