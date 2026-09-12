import type { Metadata, Viewport } from 'next';

import '@/app/globals.css';

export const metadata: Metadata = {
  title: {
    default: 'GAU Interactive Textbook',
    template: '%s · GAU Interactive Textbook',
  },
  description: 'Interactive textbook platform for Girne American University.',
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
    <html lang="en">
      <body className="min-h-dvh">{children}</body>
    </html>
  );
}
