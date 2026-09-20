import type { Metadata, Viewport } from 'next';
import { IBM_Plex_Sans, Literata } from 'next/font/google';

import '@/app/globals.css';

// Literata was designed for long-form reading on screens; IBM Plex Sans carries
// the interface. Self-hosted by next/font, so no request leaves the platform.
const literata = Literata({ subsets: ['latin', 'latin-ext'], variable: '--font-literata', display: 'swap' });
const plex = IBM_Plex_Sans({
  subsets: ['latin', 'latin-ext'],
  weight: ['400', '500', '600'],
  variable: '--font-plex',
  display: 'swap',
});

export const metadata: Metadata = {
  title: {
    default: 'GAU Interactive Textbook',
    template: '%s · GAU Interactive Textbook',
  },
  description: 'Interactive textbook platform for GAU.',
  // The reader is launched from Canvas, never found through search.
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  // Not maximum-scale: pinch-zoom must keep working on a phone, which is an
  // accessibility requirement and a Phase 1 acceptance criterion.
  viewportFit: 'cover',
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${literata.variable} ${plex.variable}`}>
      <body className="min-h-dvh">{children}</body>
    </html>
  );
}
