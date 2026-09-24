import { cookies } from 'next/headers';

/**
 * Forwarding the reader's session on a server-rendered call.
 *
 * `credentials: 'include'` means nothing on the server — there is no browser
 * and no cookie jar, only the request Next is currently handling. A React
 * Server Component that fetched the read API without this would arrive at
 * Django anonymous, and every course-scoped endpoint would refuse it (D-012).
 *
 * Why render on the server at all: D-016 chose `INTERNAL_API_BASE_URL` for
 * exactly this case. A chapter is long-form content on the critical path of
 * first paint, and fetching it from the browser would mean an empty frame
 * inside Canvas until a second round trip finished.
 */

/**
 * The incoming request's cookies, as a header for an internal API call.
 *
 * The whole jar is forwarded rather than one named cookie. The name of the
 * session cookie is a backend setting the frontend deliberately does not
 * know (rule C.6), and this is the browser's own request being relayed one
 * hop to the same platform's API over the compose network — not a credential
 * being handed to a third party.
 *
 * Reading cookies opts this render out of static generation, which is
 * correct: a reader's page is per-user and course-scoped, and caching one
 * would be the bug (see `RequestOptions.cache`).
 */
export function sessionHeaders(): Record<string, string> {
  const jar = cookies().toString();
  return jar === '' ? {} : { Cookie: jar };
}
