import Link from 'next/link';

import { ContentRenderer } from '@/components/content/ContentRenderer';
import { ReaderShell } from '@/components/reader/ReaderShell';
import { TableOfContents, type ContentsItem } from '@/components/reader/TableOfContents';
import { Icon } from '@/components/shell/Icon';
import type { Role as DisplayRole } from '@/components/shell/AppHeader';
import { fetchNode, fetchToc, fetchTextbook, type NodeLink, type TocEntry } from '@/lib/api/content';
import type { ApiError } from '@/lib/api/errors';
import { fetchLaunchContext, type Role } from '@/lib/api/launch';
import { sessionHeaders } from '@/lib/api/server';
import { flattenToc, progressThrough, readerHref, resolveDestination } from '@/lib/content/toc';

/**
 * The reader: one node of the textbook, with the book around it.
 *
 * Rendered on the server. A chapter is long-form content on the critical path
 * of first paint inside a Canvas iframe, and D-016 chose the internal API base
 * URL for exactly this — fetching from the browser would leave an empty frame
 * until a second round trip finished.
 *
 * Which book is never asked for. The session names the course, the course
 * names one book (D-057), and `?node=` is a preference within that book, not
 * an access decision (D-050) — a node outside the published contents falls
 * back to the start rather than failing.
 */

export const metadata = { title: 'Textbook' };

const ROLE_LABEL: Readonly<Record<Role, DisplayRole>> = {
  STUDENT: 'Student',
  FACULTY: 'Faculty',
  ADMIN: 'Content administrator',
};

/** A whole-page message, for the states where there is no chapter to show. */
function Notice({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <main className="mx-auto max-w-prose px-5 py-24">
      <h1 className="font-serif text-2xl font-semibold text-navy">{title}</h1>
      <div className="mt-4 space-y-3 text-ink-muted">{children}</div>
    </main>
  );
}

/**
 * What to say when a call failed.
 *
 * Each kind is a different situation for the reader and a different fix
 * (D-014). An expired session means reopening from Canvas; a refusal means
 * this is not their course; an unreachable backend means trying again. A
 * malformed response is none of those — it is the contract having moved, and
 * saying "try again" would send someone to retry something that cannot work.
 */
function failure(error: ApiError) {
  switch (error.kind) {
    case 'unauthenticated':
      return (
        <Notice title="Please open the textbook from Canvas">
          <p>Your session has ended. Return to your Canvas course and open the textbook again.</p>
        </Notice>
      );
    case 'forbidden':
      return (
        <Notice title="This content belongs to a different course">
          <p>Open the textbook from the Canvas course it belongs to.</p>
        </Notice>
      );
    case 'not_found':
      return (
        <Notice title="That part of the textbook is not available">
          <p>It may not have been published yet, or it may have been withdrawn.</p>
        </Notice>
      );
    case 'network':
    case 'server':
      return (
        <Notice title="The textbook is not responding">
          <p>This is usually temporary. Please try again in a moment.</p>
        </Notice>
      );
    default:
      return (
        <Notice title="The textbook could not be displayed">
          <p>Something is wrong at our end rather than with your course. Please report this.</p>
        </Notice>
      );
  }
}

/** The API's contents, as the contents component wants it. No numbering: see `ContentsItem`. */
function toContentsItems(entries: readonly TocEntry[]): ContentsItem[] {
  return entries.map((entry) => ({
    id: entry.id,
    title: entry.title,
    children: toContentsItems(entry.children),
  }));
}

function NeighbourLink({ node, direction }: { node: NodeLink; direction: 'previous' | 'next' }) {
  const next = direction === 'next';
  return (
    <Link href={readerHref(node.id)} className={`group ${next ? 'text-right' : ''}`}>
      <span
        className={`flex items-center gap-1 text-sm text-ink-muted ${next ? 'justify-end' : ''}`}
      >
        {next ? null : <Icon name="chevronLeft" className="h-4 w-4" />}
        {next ? 'Next' : 'Previous'}
        {next ? <Icon name="chevronRight" className="h-4 w-4" /> : null}
      </span>
      <span className="mt-1 block font-medium text-navy group-hover:text-accent">{node.title}</span>
    </Link>
  );
}

/**
 * The requested node id, from a query string that may repeat a key.
 *
 * Next hands back an array when it does (`?node=a&node=b`), so typing this as
 * a plain string would be a lie the compiler could not catch. The first value
 * wins; the alternative is refusing a launch over a duplicated parameter.
 */
function requestedNode(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default async function ReaderPage({
  searchParams,
}: {
  searchParams: { node?: string | string[] };
}) {
  const headers = sessionHeaders();

  // Who and where, and which book — both are course-scoped and neither takes a
  // parameter, so there is nothing here a client could tamper with.
  const [context, textbook] = await Promise.all([
    fetchLaunchContext({ headers }),
    fetchTextbook({ headers }),
  ]);
  if (!context.ok) return failure(context.error);
  if (!textbook.ok) return failure(textbook.error);

  if (textbook.data.book === null) {
    // Both are ordinary states with different fixes, which is why D-057 kept
    // them apart rather than collapsing them into "no book".
    return textbook.data.availability === 'NO_BOOK_LINKED' ? (
      <Notice title="No textbook yet">
        <p>
          This course does not have a textbook linked to it. Your instructor or a content
          administrator can set one.
        </p>
      </Notice>
    ) : (
      <Notice title="The textbook is not published yet">
        <p>It will appear here once it has been published.</p>
      </Notice>
    );
  }

  const contents = await fetchToc(textbook.data.book.id, { headers });
  if (!contents.ok) return failure(contents.error);

  const order = flattenToc(contents.data.toc);
  const destination = resolveDestination(order, requestedNode(searchParams.node));
  if (destination === null) {
    return (
      <Notice title={contents.data.book.title}>
        <p>Nothing in this textbook has been published yet.</p>
      </Notice>
    );
  }

  const node = await fetchNode(destination.id, { headers });
  if (!node.ok) return failure(node.error);

  return (
    <ReaderShell
      course={{ code: context.data.course.label, title: context.data.course.title }}
      role={ROLE_LABEL[context.data.role]}
      progress={progressThrough(order, destination.id)}
      contents={
        <TableOfContents
          items={toContentsItems(contents.data.toc)}
          currentId={destination.id}
          hrefFor={(item) => readerHref(item.id)}
        />
      }
    >
      <article className="mx-auto max-w-prose">
        {node.data.breadcrumb.length > 0 && (
          <nav aria-label="Breadcrumb" className="text-sm text-ink-muted">
            <ol className="flex flex-wrap items-center gap-x-1.5 gap-y-1">
              {node.data.breadcrumb.map((step) => (
                <li key={step.id} className="flex items-center gap-x-1.5">
                  <Link href={readerHref(step.id)} className="hover:text-ink">
                    {step.title}
                  </Link>
                  <span aria-hidden>/</span>
                </li>
              ))}
              <li aria-current="page" className="text-ink">
                {node.data.title}
              </li>
            </ol>
          </nav>
        )}

        <header className="mt-10 border-b border-border pb-8">
          <h1 className="font-serif text-[2.125rem] font-semibold leading-tight text-navy">
            {node.data.title}
          </h1>
        </header>

        <ContentRenderer document={node.data.body} />

        {(node.data.previous !== null || node.data.next !== null) && (
          <nav
            aria-label="Section navigation"
            className="mt-12 grid grid-cols-2 gap-4 border-t border-border pt-6"
          >
            {node.data.previous !== null ? (
              <NeighbourLink node={node.data.previous} direction="previous" />
            ) : (
              <span />
            )}
            {node.data.next !== null ? (
              <NeighbourLink node={node.data.next} direction="next" />
            ) : (
              <span />
            )}
          </nav>
        )}
      </article>
    </ReaderShell>
  );
}
