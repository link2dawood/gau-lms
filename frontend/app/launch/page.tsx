import { LaunchRouter } from '@/components/launch/LaunchRouter';

/**
 * Where a Canvas launch lands.
 *
 * `apps/lti` redirects here once it has verified the launch and provisioned
 * the user, course and membership. Everything after that depends on the
 * browser's own session state, so the work happens client-side.
 */
export const dynamic = 'force-dynamic';

export const metadata = {
  title: 'Opening your textbook',
};

export default function LaunchPage() {
  return <LaunchRouter />;
}
