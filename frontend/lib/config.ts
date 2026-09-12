/**
 * Runtime configuration.
 *
 * No Canvas URL, course id, role string or deployment id is ever hard-coded
 * (architecture rule C.6). Everything comes from the environment, and the two
 * base URLs differ by execution context:
 *
 *   browser  requests go to the public origin and are routed by Nginx
 *   server   React Server Components call Django directly over the compose
 *            network, skipping a pointless round trip through the edge
 */

/** True when running in a React Server Component or route handler. */
export const isServer = typeof window === 'undefined';

/**
 * Base URL for API calls, chosen by execution context.
 *
 * On the server, `INTERNAL_API_BASE_URL` is set by docker-compose.yml. In the
 * browser only `NEXT_PUBLIC_`-prefixed variables exist, and an empty string is
 * the correct default: a same-origin relative request is what should go
 * through Nginx.
 */
export function apiBaseUrl(): string {
  if (isServer) {
    const internal = process.env.INTERNAL_API_BASE_URL;
    if (internal !== undefined && internal !== '') {
      return internal.replace(/\/$/, '');
    }
  }
  const publicBase = process.env.NEXT_PUBLIC_API_BASE_URL;
  return publicBase !== undefined ? publicBase.replace(/\/$/, '') : '';
}
