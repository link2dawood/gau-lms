import Link from 'next/link';

const SCREENS = [
  { href: '/preview/student', title: 'Student home', note: 'Where a student lands after opening the textbook from Canvas' },
  { href: '/preview/reader', title: 'Reader', note: 'A section with a table, figure and clinical callouts' },
  { href: '/preview/search?q=blood+pressure', title: 'Search results', note: 'Matches grouped by chapter, each opening the exact paragraph' },
  { href: '/preview/faculty', title: 'Faculty dashboard', note: 'Course, linked textbook and reading position' },
  { href: '/preview/cms', title: 'Content editor', note: 'Editing a section as a content administrator' },
  { href: '/preview/cms/history', title: 'Version history', note: 'Comparing a draft with the published version' },
] as const;

export default function PreviewIndex() {
  return (
    <main className="mx-auto max-w-2xl px-5 py-16">
      <h1 className="text-2xl font-semibold text-navy">GAU Interactive Textbook</h1>
      <p className="mt-2 text-ink-muted">Screens for review. Each uses sample content.</p>
      <ul className="mt-10 divide-y divide-border border-y border-border">
        {SCREENS.map((s) => (
          <li key={s.href}>
            <Link href={s.href} className="block py-4 hover:bg-surface-muted">
              <span className="font-medium text-ink">{s.title}</span>
              <span className="mt-0.5 block text-sm text-ink-muted">{s.note}</span>
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
