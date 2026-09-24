/**
 * Reading the contents tree as a sequence.
 *
 * The API returns the table of contents nested, built from the book's reading
 * order (D-055), so a depth-first walk of it *is* that order again — a parent
 * before its children, and a chapter's last section before the next chapter.
 * Nothing here re-derives an order; it only flattens one that already exists.
 *
 * The tree has already been filtered to published nodes by the API, so
 * everything in it is somewhere a reader may actually go. That is what makes
 * it safe to use as a fallback destination and as the denominator of progress.
 */

import type { TocEntry } from '@/lib/api/content';

/** Every entry, depth-first: the order a reader meets them. */
export function flattenToc(toc: readonly TocEntry[]): TocEntry[] {
  const flat: TocEntry[] = [];
  const visit = (entries: readonly TocEntry[]): void => {
    for (const entry of entries) {
      flat.push(entry);
      visit(entry.children);
    }
  };
  visit(toc);
  return flat;
}

/**
 * How far through the book a node sits, from 0 to 1.
 *
 * Measured over the published contents, which is the book as this reader can
 * actually see it — a progress bar counting chapters nobody can open would
 * stall for no visible reason.
 *
 * The last node reads 1, not `n-1/n`: someone who has reached the final
 * section has reached the end of what there is, and showing 96% there invites
 * a hunt for the missing 4%.
 */
export function progressThrough(order: readonly TocEntry[], currentId: string): number {
  if (order.length === 0) return 0;
  const index = order.findIndex((entry) => entry.id === currentId);
  if (index < 0) return 0;
  return order.length === 1 ? 1 : (index + 1) / order.length;
}

/**
 * The node a reader should land on, given what they asked for.
 *
 * A `?node=` that names something outside the published contents — a chapter
 * withdrawn since the link was made, a deep link into another book, a typed
 * id — falls back to the start of the book rather than an error. The request
 * was for the textbook; the specific section is a preference, and D-050 is
 * explicit that the node id on a deep link is a preference expressed inside a
 * verified launch rather than an access decision.
 *
 * Returns null only when there is nothing published at all.
 */
export function resolveDestination(
  order: readonly TocEntry[],
  requestedId: string | undefined,
): TocEntry | null {
  if (requestedId !== undefined && requestedId !== '') {
    const requested = order.find((entry) => entry.id === requestedId);
    if (requested !== undefined) return requested;
  }
  return order[0] ?? null;
}

/** The URL of a node within the reader. */
export const readerHref = (nodeId: string): string =>
  `/reader?node=${encodeURIComponent(nodeId)}`;
