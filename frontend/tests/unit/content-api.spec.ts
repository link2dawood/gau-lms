import { expect, test } from '@playwright/test';

import {
  parseNodeResponse,
  parseTextbookResponse,
  parseTocResponse,
  type TocEntry,
} from '@/lib/api/content';
import { flattenToc, progressThrough, resolveDestination } from '@/lib/content/toc';

/**
 * The boundary between the read API (task 2.6) and the reader.
 *
 * These shapes were written from `apps/content/views.py` rather than observed,
 * so what these tests prove is that the guards behave as designed — not that
 * the two ends agree. That is settled the first time the stack runs.
 */

const BOOK = { id: 'b1', title: 'Nursing', slug: 'nursing', description: 'A textbook.' };
const DOC = { type: 'doc', content: [] };

const entry = (id: string, depth: number, children: unknown[] = []) => ({
  id,
  title: id.toUpperCase(),
  node_type: 'SECTION',
  depth,
  children,
});

test.describe('which textbook a course opens', () => {
  test('an available book is carried', () => {
    expect(parseTextbookResponse({ availability: 'AVAILABLE', book: BOOK })).toEqual({
      availability: 'AVAILABLE',
      book: BOOK,
    });
  });

  for (const availability of ['NO_BOOK_LINKED', 'BOOK_NOT_PUBLISHED']) {
    test(`${availability} carries no book and is not a parse failure`, () => {
      // The backend withholds the book in both cases (D-057). A null here is
      // the contract being honoured, not broken.
      expect(parseTextbookResponse({ availability, book: null })).toEqual({
        availability,
        book: null,
      });
    });
  }

  test('an unknown availability is rejected', () => {
    // Unlike a content node, this is a small closed set the backend owns. A
    // value outside it means the contract moved, and guessing would hide it.
    expect(parseTextbookResponse({ availability: 'MAYBE', book: null })).toBeNull();
  });

  test('a malformed book is rejected even when availability is fine', () => {
    expect(parseTextbookResponse({ availability: 'AVAILABLE', book: { id: 'b1' } })).toBeNull();
  });
});

test.describe('the table of contents', () => {
  test('it nests and converts node_type to camelCase', () => {
    const parsed = parseTocResponse({ book: BOOK, toc: [entry('u1', 1, [entry('c1', 2)])] });
    expect(parsed?.toc[0]).toMatchObject({ id: 'u1', nodeType: 'SECTION' });
    expect(parsed?.toc[0]?.children[0]?.id).toBe('c1');
  });

  test('an empty contents is valid — a published book may have nothing published in it', () => {
    expect(parseTocResponse({ book: BOOK, toc: [] })).toEqual({ book: BOOK, toc: [] });
  });

  test('a malformed branch is dropped and the rest still lists', () => {
    const parsed = parseTocResponse({ book: BOOK, toc: [entry('a', 1), { id: 'b' }, entry('c', 1)] });
    expect(parsed?.toc.map((e) => e.id)).toEqual(['a', 'c']);
  });

  test('an unknown node kind costs the caption, not the entry', () => {
    const parsed = parseTocResponse({
      book: BOOK,
      toc: [{ id: 'x', title: 'X', node_type: 'APPENDIX', depth: 1, children: [] }],
    });
    expect(parsed?.toc[0]?.id).toBe('x');
    expect(parsed?.toc[0] !== undefined && 'nodeType' in parsed.toc[0]).toBe(false);
  });

  test('a response with no toc array is rejected', () => {
    expect(parseTocResponse({ book: BOOK })).toBeNull();
  });
});

test.describe('a node', () => {
  const node = {
    id: 'n1',
    title: 'Blood pressure',
    node_type: 'SECTION',
    book_id: 'b1',
    breadcrumb: [{ id: 'u1', title: 'Unit One', node_type: 'UNIT' }],
    body: DOC,
    version_number: 3,
    previous: { id: 'n0', title: 'Respiration', node_type: 'SECTION' },
    next: null,
  };

  test('it converts to camelCase and keeps the version number', () => {
    expect(parseNodeResponse(node)).toMatchObject({
      id: 'n1',
      nodeType: 'SECTION',
      bookId: 'b1',
      versionNumber: 3,
      previous: { id: 'n0' },
      next: null,
    });
  });

  test('a first or last node has no neighbour on that side', () => {
    expect(parseNodeResponse({ ...node, previous: null, next: null })).toMatchObject({
      previous: null,
      next: null,
    });
  });

  test('an unreadable body is a contract failure, not a content one', () => {
    // Every other field can degrade. A node with no document is a page with
    // nothing on it, which the reader must report rather than render blank.
    expect(parseNodeResponse({ ...node, body: '<p>hello</p>' })).toBeNull();
  });

  test('a malformed breadcrumb step is dropped and the trail survives', () => {
    const parsed = parseNodeResponse({ ...node, breadcrumb: [{ id: 'u1', title: 'U' }, { id: 7 }] });
    expect(parsed?.breadcrumb.map((s) => s.id)).toEqual(['u1']);
  });

  test('a missing version number is rejected', () => {
    const without: Record<string, unknown> = { ...node };
    delete without.version_number;
    expect(parseNodeResponse(without)).toBeNull();
  });
});

test.describe('reading the contents as a sequence', () => {
  const toc: TocEntry[] = [
    { id: 'u1', title: 'Unit', depth: 1, children: [
      { id: 'c1', title: 'Chapter', depth: 2, children: [
        { id: 's1', title: 'One', depth: 3, children: [] },
        { id: 's2', title: 'Two', depth: 3, children: [] },
      ] },
      { id: 'c2', title: 'Chapter Two', depth: 2, children: [] },
    ] },
  ];

  test('flattening recovers reading order across every boundary', () => {
    // A parent before its children, and a chapter's last section before the
    // next chapter — the property the materialised path buys (D-054).
    expect(flattenToc(toc).map((e) => e.id)).toEqual(['u1', 'c1', 's1', 's2', 'c2']);
  });

  test('flattening an empty contents gives an empty order', () => {
    expect(flattenToc([])).toEqual([]);
  });

  test('progress runs from the first node to a full bar at the last', () => {
    const order = flattenToc(toc);
    expect(progressThrough(order, 'u1')).toBeCloseTo(0.2);
    expect(progressThrough(order, 'c2')).toBe(1);
  });

  test('progress for a node outside the contents is zero, not negative', () => {
    expect(progressThrough(flattenToc(toc), 'nowhere')).toBe(0);
    expect(progressThrough([], 'u1')).toBe(0);
  });

  test('a book with one node reads as complete', () => {
    expect(progressThrough([{ id: 'only', title: 'O', depth: 1, children: [] }], 'only')).toBe(1);
  });

  test('a requested node is honoured when it is published', () => {
    expect(resolveDestination(flattenToc(toc), 's2')?.id).toBe('s2');
  });

  test('a requested node that is not in the contents falls back to the start', () => {
    // A chapter withdrawn since the deep link was made. The request was for
    // the textbook; the section was a preference (D-050).
    expect(resolveDestination(flattenToc(toc), 'withdrawn')?.id).toBe('u1');
  });

  test('no request lands at the start of the book', () => {
    expect(resolveDestination(flattenToc(toc), undefined)?.id).toBe('u1');
    expect(resolveDestination(flattenToc(toc), '')?.id).toBe('u1');
  });

  test('a book with nothing published has nowhere to land', () => {
    expect(resolveDestination([], 'anything')).toBeNull();
  });
});
