/**
 * Builders for Tiptap JSON documents.
 *
 * Used wherever content is constructed in code — sample content now, test
 * fixtures and import conversion later — so every block gets its `blockId` the
 * same way and no caller hand-assembles node objects.
 */

import type { BlockNode, CalloutVariant, InlineNode, ParagraphNode } from '@/lib/content/types';

export const text = (value: string): InlineNode => ({ type: 'text', text: value });

export const bold = (value: string): InlineNode => ({ type: 'text', text: value, marks: [{ type: 'bold' }] });

export const italic = (value: string): InlineNode => ({ type: 'text', text: value, marks: [{ type: 'italic' }] });

export const link = (value: string, href: string): InlineNode => ({
  type: 'text',
  text: value,
  marks: [{ type: 'link', attrs: { href } }],
});

export const para = (...inline: InlineNode[]): ParagraphNode => ({ type: 'paragraph', content: inline });

export const paragraph = (blockId: string, ...inline: InlineNode[]): BlockNode => ({
  type: 'paragraph',
  attrs: { blockId },
  content: inline,
});

export const heading = (blockId: string, value: string, level: 2 | 3 = 2): BlockNode => ({
  type: 'heading',
  attrs: { blockId, level },
  content: [text(value)],
});

export const bulletList = (blockId: string, items: InlineNode[][]): BlockNode => ({
  type: 'bulletList',
  attrs: { blockId },
  content: items.map((inline) => ({ type: 'listItem', content: [para(...inline)] })),
});

export const callout = (
  blockId: string,
  variant: CalloutVariant,
  title: string,
  ...body: string[]
): BlockNode => ({
  type: 'callout',
  attrs: { blockId, variant, title },
  content: body.map((b) => para(text(b))),
});

export const table = (blockId: string, caption: string, header: string[], rows: string[][]): BlockNode => ({
  type: 'table',
  attrs: { blockId, caption },
  content: [
    { type: 'tableRow', content: header.map((h) => ({ type: 'tableHeader', content: [para(text(h))] })) },
    ...rows.map((row) => ({
      type: 'tableRow' as const,
      content: row.map((cell) => ({ type: 'tableCell' as const, content: [para(text(cell))] })),
    })),
  ],
});
