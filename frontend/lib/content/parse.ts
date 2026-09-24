/**
 * Validating a Tiptap document at the boundary.
 *
 * A node's body arrives as JSONB the backend never inspects beyond its outer
 * shape, so by the time it reaches the reader it is `unknown`. D-015 forbids
 * casting it: a cast asserts a shape the compiler cannot verify, and the
 * symptom of a wrong one is an `undefined` surfacing deep inside a component,
 * far from the cause. These guards turn the same problem into one decision,
 * here.
 *
 * **What is strict and what is lenient, and why.** The document envelope is
 * strict — something that is not a Tiptap document is rejected outright and
 * the reader shows an error, because there is nothing to show. Individual
 * blocks are lenient: an unrecognised or malformed block is dropped and the
 * rest of the chapter renders. Rejecting the chapter because one callout lost
 * its title would take a whole section away from a student over a defect in a
 * paragraph they may not even be reading, and the editor (task 3.5) will
 * outgrow this reader — content from a newer editor must still be readable.
 *
 * Within a block the bias runs the other way again: text is preserved wherever
 * possible. An unknown mark loses its emphasis but keeps its sentence, a
 * heading at an unsupported level is clamped rather than discarded, and a
 * block with no `blockId` keeps its text and loses only its anchor. Losing a
 * paragraph is always worse than losing the formatting of one.
 */

import type {
  BlockNode,
  CalloutVariant,
  ContentDocument,
  InlineNode,
  ListItemNode,
  Mark,
  ParagraphNode,
  ReferenceItemNode,
  TableCellNode,
  TableRowNode,
  TextNode,
} from '@/lib/content/types';

type Unknown = Record<string, unknown>;

const isObject = (value: unknown): value is Unknown =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const str = (value: unknown): string => (typeof value === 'string' ? value : '');

/** The `attrs` bag of a node, or an empty one — attrs are routinely absent. */
const attrsOf = (node: Unknown): Unknown => (isObject(node.attrs) ? node.attrs : {});

/** A node's children, always an array, so every caller can just map it. */
const childrenOf = (node: Unknown): readonly unknown[] =>
  Array.isArray(node.content) ? node.content : [];

function mapDefined<T>(values: readonly unknown[], parse: (value: unknown) => T | null): T[] {
  const parsed: T[] = [];
  for (const value of values) {
    const item = parse(value);
    if (item !== null) parsed.push(item);
  }
  return parsed;
}

function parseMark(value: unknown): Mark | null {
  if (!isObject(value)) return null;
  if (value.type === 'bold') return { type: 'bold' };
  if (value.type === 'italic') return { type: 'italic' };
  if (value.type === 'link') {
    const href = str(attrsOf(value).href);
    // A link with no destination is not a link. The text survives it.
    return href ? { type: 'link', attrs: { href } } : null;
  }
  return null;
}

function parseInline(value: unknown): InlineNode | null {
  if (!isObject(value)) return null;
  if (value.type === 'hardBreak') return { type: 'hardBreak' };
  if (value.type !== 'text' || typeof value.text !== 'string') return null;

  const marks = Array.isArray(value.marks) ? mapDefined(value.marks, parseMark) : [];
  // `exactOptionalPropertyTypes`: an absent key and a key set to undefined are
  // different types, so the key is omitted rather than set.
  const node: TextNode = marks.length > 0 ? { type: 'text', text: value.text, marks } : { type: 'text', text: value.text };
  return node;
}

const parseInlineContent = (node: Unknown): InlineNode[] => mapDefined(childrenOf(node), parseInline);

function parseParagraph(value: unknown): ParagraphNode | null {
  if (!isObject(value) || value.type !== 'paragraph') return null;
  return { type: 'paragraph', content: parseInlineContent(value) };
}

/**
 * The paragraphs inside a list item, quote, cell or callout.
 *
 * Anything that is not a paragraph — a nested list, an image — is dropped.
 * This reader renders one level; the editor may come to produce more, and
 * that is a later task rather than a reason to reject the block now.
 */
const parseParagraphs = (node: Unknown): ParagraphNode[] => mapDefined(childrenOf(node), parseParagraph);

function parseListItem(value: unknown): ListItemNode | null {
  if (!isObject(value) || value.type !== 'listItem') return null;
  return { type: 'listItem', content: parseParagraphs(value) };
}

function parseCell(value: unknown): TableCellNode | null {
  if (!isObject(value)) return null;
  if (value.type !== 'tableHeader' && value.type !== 'tableCell') return null;
  return { type: value.type, content: parseParagraphs(value) };
}

function parseRow(value: unknown): TableRowNode | null {
  if (!isObject(value) || value.type !== 'tableRow') return null;
  const content = mapDefined(childrenOf(value), parseCell);
  // A row with no cells would render as an empty stripe.
  return content.length > 0 ? { type: 'tableRow', content } : null;
}

function parseReferenceItem(value: unknown): ReferenceItemNode | null {
  if (!isObject(value) || value.type !== 'referenceItem') return null;
  return { type: 'referenceItem', content: parseInlineContent(value) };
}

const CALLOUT_VARIANTS: readonly CalloutVariant[] = ['clinical-alert', 'practice-point', 'key-term', 'note'];

function parseVariant(value: unknown): CalloutVariant {
  const found = CALLOUT_VARIANTS.find((variant) => variant === value);
  // Never guessed at. A callout kind this reader does not know is a neutral
  // note, because rendering an unknown kind as a "Practice point" would
  // understate something that might be a safety warning.
  return found ?? 'note';
}

/** Body headings are h2 or h3: the node's own title owns the page's h1. */
function parseHeadingLevel(value: unknown): 2 | 3 {
  return value === 3 || (typeof value === 'number' && value >= 3) ? 3 : 2;
}

export function parseBlock(value: unknown): BlockNode | null {
  if (!isObject(value) || typeof value.type !== 'string') return null;

  const attrs = attrsOf(value);
  // Kept even when absent. A block with no anchor cannot be scrolled to; a
  // block that was dropped cannot be read at all.
  const blockId = str(attrs.blockId);

  switch (value.type) {
    case 'heading':
      return {
        type: 'heading',
        attrs: { blockId, level: parseHeadingLevel(attrs.level) },
        content: parseInlineContent(value),
      };
    case 'paragraph':
      return { type: 'paragraph', attrs: { blockId }, content: parseInlineContent(value) };
    case 'bulletList':
    case 'orderedList':
      return {
        type: value.type,
        attrs: { blockId },
        content: mapDefined(childrenOf(value), parseListItem),
      };
    case 'blockquote':
      return { type: 'blockquote', attrs: { blockId }, content: parseParagraphs(value) };
    case 'table': {
      const content = mapDefined(childrenOf(value), parseRow);
      // A table with no rows is nothing to show, caption or not.
      if (content.length === 0) return null;
      return { type: 'table', attrs: { blockId, caption: str(attrs.caption) }, content };
    }
    case 'figure': {
      const src = str(attrs.src);
      // Without a source there is no figure — and unlike text, there is no
      // part of it that survives. The caption alone would be a dangling label.
      if (!src) return null;
      return {
        type: 'figure',
        // `alt` may legitimately be empty: that is how HTML marks an image as
        // decorative. What it may not be is missing, which is why it is read
        // through `str` rather than passed along.
        attrs: { blockId, src, alt: str(attrs.alt), caption: str(attrs.caption) },
      };
    }
    case 'callout':
      return {
        type: 'callout',
        attrs: { blockId, variant: parseVariant(attrs.variant), title: str(attrs.title) },
        content: parseParagraphs(value),
      };
    case 'references': {
      const content = mapDefined(childrenOf(value), parseReferenceItem);
      if (content.length === 0) return null;
      return {
        type: 'references',
        attrs: { blockId, title: str(attrs.title) || 'References' },
        content,
      };
    }
    default:
      // A block type this reader has never heard of. Dropped, deliberately:
      // the editor will outgrow the reader, and a chapter that mostly renders
      // beats one that does not render at all.
      return null;
  }
}

/**
 * Narrow an API response body to a document this reader can render.
 *
 * Returns null only when the value is not a Tiptap document at all, which the
 * API client turns into a `malformed` error naming the request (D-014). A
 * document whose blocks are all unrecognised parses successfully and renders
 * empty — that is a content problem, not a contract one, and the two should
 * not produce the same message.
 */
export function parseContentDocument(value: unknown): ContentDocument | null {
  if (!isObject(value) || value.type !== 'doc' || !Array.isArray(value.content)) return null;
  return { type: 'doc', content: mapDefined(value.content, parseBlock) };
}
