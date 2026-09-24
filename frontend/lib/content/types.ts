/**
 * Content types shared by the reader, search and CMS.
 *
 * Bodies are Tiptap JSON (architecture rule C.7). Every top-level block carries
 * a stable `blockId`, which the renderer emits as a DOM anchor so reading
 * positions, search hits and later annotations can point at an exact block.
 */

export type NodeType = 'UNIT' | 'CHAPTER' | 'SECTION' | 'SUBSECTION';

export interface TocNode {
  readonly id: string;
  readonly type: NodeType;
  readonly title: string;
  /** Display number, e.g. "6" or "6.4". Not identity: identity is `id`. */
  readonly number: string;
  readonly children: readonly TocNode[];
}

export type Mark =
  | { readonly type: 'bold' }
  | { readonly type: 'italic' }
  | { readonly type: 'link'; readonly attrs: { readonly href: string } };

export interface TextNode {
  readonly type: 'text';
  readonly text: string;
  readonly marks?: readonly Mark[];
}

export type InlineNode = TextNode | { readonly type: 'hardBreak' };

export interface ParagraphNode {
  readonly type: 'paragraph';
  readonly content: readonly InlineNode[];
}

export interface ListItemNode {
  readonly type: 'listItem';
  readonly content: readonly ParagraphNode[];
}

export interface TableCellNode {
  readonly type: 'tableHeader' | 'tableCell';
  readonly content: readonly ParagraphNode[];
}

export interface TableRowNode {
  readonly type: 'tableRow';
  readonly content: readonly TableCellNode[];
}

/**
 * Callout kinds the editor produces, plus `note`.
 *
 * `note` is the reader's fallback and nothing authors it: a callout arriving
 * with a variant this reader does not know is rendered as a neutral note
 * rather than dropped or guessed at. Guessing is the one unacceptable option —
 * showing an unknown callout as a "Practice point" would understate something
 * that might be a safety warning, and in a nursing textbook that is not a
 * cosmetic mistake.
 */
export type CalloutVariant = 'clinical-alert' | 'practice-point' | 'key-term' | 'note';

interface BlockAttrs {
  readonly blockId: string;
}

export type BlockNode =
  | { readonly type: 'heading'; readonly attrs: BlockAttrs & { readonly level: 2 | 3 }; readonly content: readonly InlineNode[] }
  | { readonly type: 'paragraph'; readonly attrs: BlockAttrs; readonly content: readonly InlineNode[] }
  | { readonly type: 'bulletList' | 'orderedList'; readonly attrs: BlockAttrs; readonly content: readonly ListItemNode[] }
  | { readonly type: 'blockquote'; readonly attrs: BlockAttrs; readonly content: readonly ParagraphNode[] }
  | {
      readonly type: 'table';
      readonly attrs: BlockAttrs & { readonly caption: string };
      readonly content: readonly TableRowNode[];
    }
  | {
      readonly type: 'figure';
      readonly attrs: BlockAttrs & { readonly src: string; readonly alt: string; readonly caption: string };
    }
  | {
      readonly type: 'callout';
      readonly attrs: BlockAttrs & { readonly variant: CalloutVariant; readonly title: string };
      readonly content: readonly ParagraphNode[];
    }
  | {
      readonly type: 'references';
      readonly attrs: BlockAttrs & { readonly title: string };
      readonly content: readonly ReferenceItemNode[];
    };

/** One citation. Inline content, so a reference can carry a link (rule C.7). */
export interface ReferenceItemNode {
  readonly type: 'referenceItem';
  readonly content: readonly InlineNode[];
}

export interface ContentDocument {
  readonly type: 'doc';
  readonly content: readonly BlockNode[];
}
