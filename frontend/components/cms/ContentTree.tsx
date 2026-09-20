import { Icon } from '@/components/shell/Icon';
import type { TocNode } from '@/lib/content/types';
import { cn } from '@/utils/cn';

/**
 * Book structure as an administrator sees it: every node, its display number,
 * and whether it has unpublished changes. Order is changed by dragging
 * (task 3.4); the handle is shown for each movable node.
 */
export function ContentTree({
  toc,
  selectedId,
  draftIds,
}: {
  toc: readonly TocNode[];
  selectedId: string;
  draftIds: ReadonlySet<string>;
}) {
  const row = (node: TocNode, depth: number) => {
    const selected = node.id === selectedId;
    return (
      <li key={node.id}>
        <div
          className={cn(
            'group flex items-center gap-2 py-1.5 pr-3 text-sm',
            selected ? 'bg-accent/[0.08] text-navy' : 'text-ink hover:bg-surface-muted',
          )}
          style={{ paddingLeft: `${0.5 + depth * 1.1}rem` }}
          aria-current={selected ? 'true' : undefined}
        >
          <Icon name="grip" className="h-4 w-4 shrink-0 text-border group-hover:text-ink-muted" />
          {node.type === 'UNIT' ? (
            // Units are labelled in words so "Unit 1" is never confused with chapter 1.
            <span className="min-w-0 flex-1 truncate font-medium">
              <span className="text-ink-muted">Unit {node.number}</span> {node.title}
            </span>
          ) : (
            <>
              <span className="w-8 shrink-0 text-ink-muted tabular-nums">{node.number}</span>
              <span className={cn('min-w-0 flex-1 truncate', selected && 'font-medium')}>{node.title}</span>
            </>
          )}
          {draftIds.has(node.id) && (
            <span className="shrink-0 border border-accent/40 px-1.5 text-xs text-accent">Draft</span>
          )}
        </div>
        {node.children.length > 0 && <ul>{node.children.map((child) => row(child, depth + 1))}</ul>}
      </li>
    );
  };

  return (
    <nav aria-label="Book structure">
      <ul>{toc.map((unit) => row(unit, 0))}</ul>
    </nav>
  );
}
