import { notFound } from 'next/navigation';

/**
 * Interface preview, built with sample content before the content API exists.
 *
 * Off unless ENABLE_UI_PREVIEW=true, so it cannot appear on a deployed
 * environment by accident. Evaluated per request rather than at build time, so
 * the flag is honoured by the production image too.
 */
export const dynamic = 'force-dynamic';

export const metadata = { title: 'Interface preview' };

export default function PreviewLayout({ children }: { children: React.ReactNode }) {
  if (process.env.ENABLE_UI_PREVIEW !== 'true') notFound();

  return (
    <>
      <p className="bg-navy px-4 py-1.5 text-center text-[0.8125rem] text-white/90">
        Interface preview with sample content. Not connected to Canvas or the textbook service.
      </p>
      {children}
    </>
  );
}
