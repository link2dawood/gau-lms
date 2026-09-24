import { Fragment, type ReactNode } from 'react';

import type {
  BlockNode,
  CalloutVariant,
  ContentDocument,
  InlineNode,
  ParagraphNode,
} from '@/lib/content/types';

/**
 * A block's DOM anchor, omitted when the block has none.
 *
 * The guard keeps a block whose `blockId` is missing rather than dropping it
 * (see lib/content/parse.ts): losing a paragraph is worse than losing the
 * ability to scroll to it. Such a block renders without an `id`, so nothing
 * can anchor to it and nothing breaks.
 */
const anchor = (id: string) => (id ? { id } : {});

/**
 * Renders a Tiptap JSON document as reading content.
 *
 * Every top-level block is emitted with `id={blockId}`, so a reading position,
 * a search result or a deep link can scroll to the exact block (rule C.7). The
 * one exception is a block that arrived without a blockId, which renders
 * without an anchor rather than not at all — see lib/content/parse.ts.
 *
 * This component trusts its input, which is what `parseContentDocument` is
 * for: nothing reaches here unvalidated (D-015). Unknown node types are
 * dropped by the guard, not here, so the reader survives content produced by a
 * newer editor than itself.
 */
export function ContentRenderer({ document }: { document: ContentDocument }) {
  return <div className="reading-flow">{document.content.map(renderBlock)}</div>;
}

function renderInline(node: InlineNode, index: number): ReactNode {
  if (node.type === 'hardBreak') return <br key={index} />;
  let out: ReactNode = node.text;
  for (const mark of node.marks ?? []) {
    if (mark.type === 'bold') out = <strong className="font-semibold text-ink">{out}</strong>;
    else if (mark.type === 'italic') out = <em>{out}</em>;
    else if (mark.type === 'link') {
      const external = /^https?:\/\//.test(mark.attrs.href);
      out = (
        <a
          href={mark.attrs.href}
          className="text-accent underline decoration-accent/40 underline-offset-2 hover:decoration-accent"
          {...(external ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
        >
          {out}
        </a>
      );
    }
  }
  return <Fragment key={index}>{out}</Fragment>;
}

function renderParagraph(node: ParagraphNode, key: number | string, className?: string) {
  return (
    <p key={key} className={className}>
      {node.content.map(renderInline)}
    </p>
  );
}

const CALLOUT_STYLE: Record<CalloutVariant, { bar: string; label: string; title: string }> = {
  'clinical-alert': { bar: 'border-danger', label: 'Clinical alert', title: 'text-danger' },
  'practice-point': { bar: 'border-accent', label: 'Practice point', title: 'text-navy' },
  'key-term': { bar: 'border-navy', label: 'Key term', title: 'text-navy' },
  // The fallback for a callout kind this reader does not know. Neutral on
  // purpose: see the note on CalloutVariant.
  note: { bar: 'border-border', label: 'Note', title: 'text-navy' },
};

function renderBlock(block: BlockNode, index: number): ReactNode {
  const id = block.attrs.blockId;
  // React needs a key even when the block has no anchor, and two unanchored
  // blocks would otherwise collide on the empty string.
  const key = id || `block-${index}`;
  const body = 'font-serif text-[1.0625rem] leading-[1.75] text-ink';

  switch (block.type) {
    case 'heading': {
      const Tag = block.attrs.level === 2 ? 'h2' : 'h3';
      return (
        <Tag
          key={key}
          {...anchor(id)}
          className={
            block.attrs.level === 2
              ? 'mt-12 scroll-mt-24 font-sans text-xl font-semibold text-navy'
              : 'mt-8 scroll-mt-24 font-sans text-lg font-semibold text-navy'
          }
        >
          {block.content.map(renderInline)}
        </Tag>
      );
    }
    case 'paragraph':
      return (
        <p key={key} {...anchor(id)} className={`mt-5 scroll-mt-24 ${body}`}>
          {block.content.map(renderInline)}
        </p>
      );
    case 'bulletList':
    case 'orderedList': {
      const List = block.type === 'bulletList' ? 'ul' : 'ol';
      return (
        <List
          key={key}
          {...anchor(id)}
          className={`mt-5 scroll-mt-24 space-y-2 pl-6 ${body} ${block.type === 'bulletList' ? 'list-disc marker:text-accent' : 'list-decimal marker:text-ink-muted'}`}
        >
          {block.content.map((item, i) => (
            <li key={i} className="pl-1">
              {item.content.map((para, j) => renderParagraph(para, j))}
            </li>
          ))}
        </List>
      );
    }
    case 'blockquote':
      return (
        <blockquote key={key} {...anchor(id)} className={`mt-6 scroll-mt-24 border-l-2 border-border pl-5 italic ${body}`}>
          {block.content.map((para, i) => renderParagraph(para, i))}
        </blockquote>
      );
    case 'table': {
      const [head, ...rows] = block.content;
      return (
        <figure key={key} {...anchor(id)} className="mt-8 scroll-mt-24">
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left font-sans text-[0.9375rem]">
              {head !== undefined && (
                <thead>
                  <tr className="border-b-2 border-navy">
                    {head.content.map((cell, i) => (
                      <th key={i} scope="col" className="py-2.5 pr-4 font-semibold text-navy">
                        {cell.content.map((para, j) => (
                          <Fragment key={j}>{para.content.map(renderInline)}</Fragment>
                        ))}
                      </th>
                    ))}
                  </tr>
                </thead>
              )}
              <tbody>
                {rows.map((row, r) => (
                  <tr key={r} className="border-b border-border">
                    {row.content.map((cell, c) => {
                      const CellTag = c === 0 ? 'th' : 'td';
                      return (
                        <CellTag
                          key={c}
                          {...(c === 0 ? { scope: 'row' as const } : {})}
                          className={`py-2.5 pr-4 align-top ${c === 0 ? 'font-medium text-ink' : 'text-ink'}`}
                        >
                          {cell.content.map((para, j) => (
                            <Fragment key={j}>{para.content.map(renderInline)}</Fragment>
                          ))}
                        </CellTag>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <figcaption className="mt-2.5 font-sans text-sm text-ink-muted">{block.attrs.caption}</figcaption>
        </figure>
      );
    }
    case 'figure':
      return (
        <figure key={key} {...anchor(id)} className="mt-8 scroll-mt-24">
          {/* Sized SVG/PNG from the media library; next/image is adopted with task 3.10. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={block.attrs.src} alt={block.attrs.alt} className="w-full border border-border" />
          <figcaption className="mt-2.5 font-sans text-sm text-ink-muted">{block.attrs.caption}</figcaption>
        </figure>
      );
    case 'callout': {
      const style = CALLOUT_STYLE[block.attrs.variant];
      return (
        <aside
          key={key}
          {...anchor(id)}
          aria-label={`${style.label}: ${block.attrs.title}`}
          className={`mt-8 scroll-mt-24 border-l-[3px] bg-surface-muted py-4 pl-5 pr-5 ${style.bar}`}
        >
          <p className="font-sans text-[0.8125rem] font-medium text-ink-muted">{style.label}</p>
          <p className={`mt-0.5 font-sans text-base font-semibold ${style.title}`}>{block.attrs.title}</p>
          {block.content.map((para, i) =>
            renderParagraph(para, i, 'mt-2 font-serif text-base leading-[1.7] text-ink'),
          )}
        </aside>
      );
    }
    case 'references':
      return (
        <section key={key} {...anchor(id)} aria-labelledby={`${id}-heading`} className="mt-12 scroll-mt-24">
          <h2 id={`${id}-heading`} className="font-sans text-base font-semibold text-navy">
            {block.attrs.title}
          </h2>
          {/* An ordered list, because a citation is referred to by its number
              and a screen reader should announce the count and position. */}
          <ol className="mt-3 space-y-2 pl-6 font-sans text-sm leading-[1.6] text-ink-muted">
            {block.content.map((item, i) => (
              <li key={i} className="pl-1">
                {item.content.map(renderInline)}
              </li>
            ))}
          </ol>
        </section>
      );
    default:
      return null;
  }
}
