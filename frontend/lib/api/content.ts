/**
 * Typed bindings for the read API (task 2.6).
 *
 * Three endpoints, all course-scoped by the session a Canvas launch wrote:
 * which textbook this course opens, that book's contents, and one node's
 * published body. None of them takes a course; there is nothing here for a
 * client to widen.
 *
 * Every response is narrowed by a guard rather than cast (D-015), and the
 * guards convert the API's `snake_case` to `camelCase` as they go. That
 * conversion belongs here, at the boundary, so the rest of the frontend reads
 * idiomatically and a rename on either side surfaces in one file.
 */

import { request, type RequestOptions } from '@/lib/api/client';
import type { ApiResult } from '@/lib/api/errors';
import { parseContentDocument } from '@/lib/content/parse';
import type { ContentDocument, NodeType } from '@/lib/content/types';

/** Why a course does or does not open a readable textbook (D-057). */
export type BookAvailability = 'AVAILABLE' | 'NO_BOOK_LINKED' | 'BOOK_NOT_PUBLISHED';

export interface BookSummary {
  readonly id: string;
  readonly title: string;
  readonly slug: string;
  readonly description: string;
}

export interface TextbookResponse {
  readonly availability: BookAvailability;
  /** Present only when the book may be read — the backend withholds it otherwise. */
  readonly book: BookSummary | null;
}

export interface TocEntry {
  readonly id: string;
  readonly title: string;
  /** Absent when the backend sends a kind this reader does not know. */
  readonly nodeType?: NodeType;
  readonly depth: number;
  readonly children: readonly TocEntry[];
}

export interface TocResponse {
  readonly book: BookSummary;
  readonly toc: readonly TocEntry[];
}

export interface NodeLink {
  readonly id: string;
  readonly title: string;
  readonly nodeType?: NodeType;
}

export interface NodeResponse {
  readonly id: string;
  readonly title: string;
  readonly nodeType?: NodeType;
  readonly bookId: string;
  /** Outermost first. Shorter than the node's depth when an ancestor is unpublished. */
  readonly breadcrumb: readonly NodeLink[];
  readonly body: ContentDocument;
  /** Which version produced this text — what a reader's bug report needs. */
  readonly versionNumber: number;
  readonly previous: NodeLink | null;
  readonly next: NodeLink | null;
}

type Unknown = Record<string, unknown>;

const isObject = (value: unknown): value is Unknown =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const NODE_TYPES: readonly NodeType[] = ['UNIT', 'CHAPTER', 'SECTION', 'SUBSECTION'];

/**
 * The node kind, when it is one this reader knows.
 *
 * Omitted rather than guessed at or fatal: it is a label, and the tree's shape
 * comes from `depth`. An unfamiliar kind costs a caption, not a chapter.
 */
function nodeTypeOf(value: unknown): NodeType | undefined {
  return NODE_TYPES.find((type) => type === value);
}

/** Spread into an object literal — `exactOptionalPropertyTypes` rejects an explicit undefined. */
function optionalNodeType(value: unknown): { nodeType?: NodeType } {
  const nodeType = nodeTypeOf(value);
  return nodeType === undefined ? {} : { nodeType };
}

function parseBookSummary(value: unknown): BookSummary | null {
  if (!isObject(value)) return null;
  const { id, title, slug, description } = value;
  if (typeof id !== 'string' || id === '') return null;
  if (typeof title !== 'string' || typeof slug !== 'string' || typeof description !== 'string') {
    return null;
  }
  return { id, title, slug, description };
}

const AVAILABILITY: readonly BookAvailability[] = [
  'AVAILABLE',
  'NO_BOOK_LINKED',
  'BOOK_NOT_PUBLISHED',
];

export function parseTextbookResponse(value: unknown): TextbookResponse | null {
  if (!isObject(value)) return null;
  const availability = AVAILABILITY.find((candidate) => candidate === value.availability);
  if (availability === undefined) return null;

  // Null is the expected shape for both unavailable states, so it is not a
  // parse failure — but a book that is present must still be well formed.
  if (value.book === null || value.book === undefined) return { availability, book: null };
  const book = parseBookSummary(value.book);
  return book === null ? null : { availability, book };
}

function parseTocEntry(value: unknown): TocEntry | null {
  if (!isObject(value)) return null;
  const { id, title, depth } = value;
  if (typeof id !== 'string' || id === '' || typeof title !== 'string') return null;
  if (typeof depth !== 'number') return null;

  const children: TocEntry[] = [];
  if (Array.isArray(value.children)) {
    for (const child of value.children) {
      const parsed = parseTocEntry(child);
      // A malformed branch is dropped; the rest of the contents still lists.
      // Losing one line beats losing a student's only way to navigate.
      if (parsed !== null) children.push(parsed);
    }
  }
  return { id, title, depth, ...optionalNodeType(value.node_type), children };
}

export function parseTocResponse(value: unknown): TocResponse | null {
  if (!isObject(value) || !Array.isArray(value.toc)) return null;
  const book = parseBookSummary(value.book);
  if (book === null) return null;

  const toc: TocEntry[] = [];
  for (const entry of value.toc) {
    const parsed = parseTocEntry(entry);
    if (parsed !== null) toc.push(parsed);
  }
  return { book, toc };
}

function parseNodeLink(value: unknown): NodeLink | null {
  if (!isObject(value)) return null;
  const { id, title } = value;
  if (typeof id !== 'string' || id === '' || typeof title !== 'string') return null;
  return { id, title, ...optionalNodeType(value.node_type) };
}

export function parseNodeResponse(value: unknown): NodeResponse | null {
  if (!isObject(value)) return null;
  const { id, title, book_id: bookId, version_number: versionNumber } = value;
  if (typeof id !== 'string' || id === '' || typeof title !== 'string') return null;
  if (typeof bookId !== 'string' || bookId === '') return null;
  if (typeof versionNumber !== 'number') return null;

  // The body is the one part that cannot degrade: a node with no readable
  // document is a page with nothing on it, and that is a contract failure
  // rather than a content one.
  const body = parseContentDocument(value.body);
  if (body === null) return null;

  const breadcrumb: NodeLink[] = [];
  if (Array.isArray(value.breadcrumb)) {
    for (const step of value.breadcrumb) {
      const parsed = parseNodeLink(step);
      if (parsed !== null) breadcrumb.push(parsed);
    }
  }

  return {
    id,
    title,
    ...optionalNodeType(value.node_type),
    bookId,
    breadcrumb,
    body,
    versionNumber,
    previous: parseNodeLink(value.previous),
    next: parseNodeLink(value.next),
  };
}

/** Which textbook this launch opens. The reader's first call: it needs a book id. */
export function fetchTextbook(options: RequestOptions = {}): Promise<ApiResult<TextbookResponse>> {
  return request('/api/textbook/', parseTextbookResponse, options);
}

export function fetchToc(
  bookId: string,
  options: RequestOptions = {},
): Promise<ApiResult<TocResponse>> {
  return request(`/api/books/${encodeURIComponent(bookId)}/toc/`, parseTocResponse, options);
}

export function fetchNode(
  nodeId: string,
  options: RequestOptions = {},
): Promise<ApiResult<NodeResponse>> {
  return request(`/api/nodes/${encodeURIComponent(nodeId)}/`, parseNodeResponse, options);
}
