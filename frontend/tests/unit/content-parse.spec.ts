import { expect, test } from '@playwright/test';

import { parseBlock, parseContentDocument } from '@/lib/content/parse';
import type { BlockNode } from '@/lib/content/types';

/**
 * The boundary between JSONB the backend never inspects and a renderer that
 * trusts its input (D-015).
 *
 * The shape of these tests follows the guard's two biases: the envelope is
 * strict, and everything inside it prefers keeping text over keeping form.
 */

const doc = (...blocks: unknown[]) => ({ type: 'doc', content: blocks });
const paragraph = (blockId: string, text: string) => ({
  type: 'paragraph',
  attrs: { blockId },
  content: [{ type: 'text', text }],
});

/** The text a block renders, flattened, for assertions that ignore structure. */
function textOf(block: BlockNode | null): string {
  if (block === null) return '';
  const parts: string[] = [];
  const walk = (value: unknown): void => {
    if (Array.isArray(value)) {
      value.forEach(walk);
      return;
    }
    if (typeof value === 'object' && value !== null) {
      const node = value as Record<string, unknown>;
      if (typeof node.text === 'string') parts.push(node.text);
      walk(node.content);
    }
  };
  walk(block);
  return parts.join('');
}

test.describe('the document envelope is strict', () => {
  for (const [label, value] of [
    ['a string of HTML', '<p>hello</p>'],
    ['a bare array of blocks', [{ type: 'paragraph' }]],
    ['null', null],
    ['an empty object', {}],
    ['a node that is not a doc', { type: 'paragraph', content: [] }],
    ['a doc with no content key', { type: 'doc' }],
    ['a doc whose content is not an array', { type: 'doc', content: 'text' }],
  ] as const) {
    test(`${label} is rejected outright`, () => {
      expect(parseContentDocument(value)).toBeNull();
    });
  }

  test('a well-formed but empty document is accepted', () => {
    expect(parseContentDocument(doc())).toEqual({ type: 'doc', content: [] });
  });

  test('a document of entirely unknown blocks parses but renders nothing', () => {
    // Deliberately not null: this is a content problem, not a contract one,
    // and the reader must not report it as a malformed response.
    const parsed = parseContentDocument(doc({ type: 'mermaidDiagram' }, { type: 'poll' }));
    expect(parsed).toEqual({ type: 'doc', content: [] });
  });
});

test.describe('one bad block never costs the chapter', () => {
  test('an unknown block is dropped and its neighbours survive', () => {
    const parsed = parseContentDocument(
      doc(paragraph('b1', 'Before.'), { type: 'videoEmbed' }, paragraph('b2', 'After.')),
    );
    expect(parsed?.content.map((b) => b.attrs.blockId)).toEqual(['b1', 'b2']);
  });

  test('a figure with no source is dropped rather than left as a dangling caption', () => {
    expect(parseBlock({ type: 'figure', attrs: { blockId: 'f1', caption: 'Figure 1' } })).toBeNull();
  });

  test('a table with no rows is dropped', () => {
    expect(parseBlock({ type: 'table', attrs: { blockId: 't1', caption: 'A' }, content: [] })).toBeNull();
  });
});

test.describe('text survives whatever happens to its formatting', () => {
  test('an unknown mark loses the emphasis and keeps the sentence', () => {
    const block = parseBlock({
      type: 'paragraph',
      attrs: { blockId: 'b1' },
      content: [{ type: 'text', text: 'Vital signs', marks: [{ type: 'highlight' }, { type: 'bold' }] }],
    });
    expect(textOf(block)).toBe('Vital signs');
    expect(block).toMatchObject({ content: [{ marks: [{ type: 'bold' }] }] });
  });

  test('a link with no destination keeps its text', () => {
    const block = parseBlock({
      type: 'paragraph',
      attrs: { blockId: 'b1' },
      content: [{ type: 'text', text: 'See the policy', marks: [{ type: 'link', attrs: {} }] }],
    });
    expect(textOf(block)).toBe('See the policy');
    // The key is dropped, not emptied: once the only mark is gone there is no
    // `marks` at all, which is the same shape a plain run of text has.
    expect(block?.type === 'paragraph' && 'marks' in block.content[0]!).toBe(false);
  });

  test('a text node with no marks omits the key rather than setting it undefined', () => {
    // exactOptionalPropertyTypes makes those different types, and an explicit
    // undefined would not survive a round trip through JSON.
    const block = parseBlock(paragraph('b1', 'Plain.'));
    expect(block?.type === 'paragraph' && 'marks' in block.content[0]!).toBe(false);
  });

  test('a heading at an unsupported level is clamped, not discarded', () => {
    // The node's own title is the page's h1, so a body heading is h2 or h3.
    expect(parseBlock({ type: 'heading', attrs: { blockId: 'h', level: 1 }, content: [] })).toMatchObject({
      attrs: { level: 2 },
    });
    expect(parseBlock({ type: 'heading', attrs: { blockId: 'h', level: 5 }, content: [] })).toMatchObject({
      attrs: { level: 3 },
    });
  });

  test('a block with no blockId keeps its text and loses only its anchor', () => {
    const block = parseBlock({ type: 'paragraph', content: [{ type: 'text', text: 'Unanchored.' }] });
    expect(textOf(block)).toBe('Unanchored.');
    expect(block?.attrs.blockId).toBe('');
  });

  test('missing attrs do not throw', () => {
    expect(textOf(parseBlock({ type: 'paragraph', content: [{ type: 'text', text: 'Bare.' }] }))).toBe('Bare.');
  });
});

test.describe('an unknown callout is never guessed at', () => {
  test('a known variant is kept', () => {
    expect(
      parseBlock({ type: 'callout', attrs: { blockId: 'c', variant: 'clinical-alert', title: 'Care' }, content: [] }),
    ).toMatchObject({ attrs: { variant: 'clinical-alert' } });
  });

  for (const variant of ['warning', 'danger', '', 42, null]) {
    test(`an unrecognised variant ${JSON.stringify(variant)} becomes a neutral note`, () => {
      // Not 'practice-point': rendering an unknown callout as a practice point
      // would understate something that might be a safety warning.
      expect(
        parseBlock({ type: 'callout', attrs: { blockId: 'c', variant, title: 'T' }, content: [] }),
      ).toMatchObject({ attrs: { variant: 'note' } });
    });
  }
});

test.describe('structure that the reader does not render is dropped, not fatal', () => {
  test('a nested list inside a list item is dropped and the paragraph stays', () => {
    const block = parseBlock({
      type: 'bulletList',
      attrs: { blockId: 'l1' },
      content: [
        {
          type: 'listItem',
          content: [
            { type: 'paragraph', content: [{ type: 'text', text: 'Outer' }] },
            { type: 'bulletList', content: [] },
          ],
        },
      ],
    });
    expect(textOf(block)).toBe('Outer');
  });

  test('a table keeps its header row and its cells', () => {
    const block = parseBlock({
      type: 'table',
      attrs: { blockId: 't1', caption: 'Observations' },
      content: [
        {
          type: 'tableRow',
          content: [{ type: 'tableHeader', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Sign' }] }] }],
        },
        {
          type: 'tableRow',
          content: [{ type: 'tableCell', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Pulse' }] }] }],
        },
      ],
    });
    expect(block).toMatchObject({ content: [{ content: [{ type: 'tableHeader' }] }, { content: [{ type: 'tableCell' }] }] });
    expect(textOf(block)).toBe('SignPulse');
  });

  test('a figure keeps an empty alt, which is how HTML marks one decorative', () => {
    expect(parseBlock({ type: 'figure', attrs: { blockId: 'f', src: '/a.png', alt: '' } })).toMatchObject({
      attrs: { alt: '', caption: '' },
    });
  });

  test('references default their own heading when the content does not carry one', () => {
    expect(
      parseBlock({
        type: 'references',
        attrs: { blockId: 'r' },
        content: [{ type: 'referenceItem', content: [{ type: 'text', text: 'Smith 2024' }] }],
      }),
    ).toMatchObject({ attrs: { title: 'References' } });
  });

  test('an empty reference list is dropped rather than rendering a lone heading', () => {
    expect(parseBlock({ type: 'references', attrs: { blockId: 'r' }, content: [] })).toBeNull();
  });
});

test.describe('every block type the backlog names is recognised', () => {
  // A reader that silently stopped supporting a node type would look exactly
  // like content that had none of that type. This is what notices.
  const blocks: Record<string, unknown> = {
    heading: { type: 'heading', attrs: { blockId: 'a', level: 2 }, content: [] },
    paragraph: paragraph('b', 'x'),
    bulletList: { type: 'bulletList', attrs: { blockId: 'c' }, content: [] },
    orderedList: { type: 'orderedList', attrs: { blockId: 'd' }, content: [] },
    blockquote: { type: 'blockquote', attrs: { blockId: 'e' }, content: [] },
    table: {
      type: 'table',
      attrs: { blockId: 'f' },
      content: [{ type: 'tableRow', content: [{ type: 'tableCell', content: [] }] }],
    },
    figure: { type: 'figure', attrs: { blockId: 'g', src: '/x.png', alt: 'x' } },
    callout: { type: 'callout', attrs: { blockId: 'h', variant: 'key-term', title: 'T' }, content: [] },
    references: {
      type: 'references',
      attrs: { blockId: 'i' },
      content: [{ type: 'referenceItem', content: [] }],
    },
  };

  for (const [name, value] of Object.entries(blocks)) {
    test(`${name} parses`, () => {
      expect(parseBlock(value)).toMatchObject({ type: name });
    });
  }
});
