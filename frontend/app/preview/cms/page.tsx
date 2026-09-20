import Link from 'next/link';

import { ContentTree } from '@/components/cms/ContentTree';
import { ContentRenderer } from '@/components/content/ContentRenderer';
import { AppHeader } from '@/components/shell/AppHeader';
import { Icon } from '@/components/shell/Icon';
import { SAMPLE_BOOK, SAMPLE_SECTION_BLOOD_PRESSURE, SAMPLE_TOC } from '@/lib/preview/sample-book';

export const metadata = { title: 'Edit 6.4 Blood pressure' };

const TOOLS = ['Heading', 'Bold', 'Italic', 'List', 'Link', 'Table', 'Figure', 'Callout', 'Reference'] as const;

export default function CmsEditorPreview() {
  return (
    <div className="flex min-h-dvh flex-col bg-surface-muted">
      <AppHeader courseCode="Content management" courseTitle={SAMPLE_BOOK.title} role="Content administrator" />

      <div className="flex min-h-0 flex-1">
        <aside className="hidden w-80 shrink-0 overflow-y-auto border-r border-border bg-surface py-4 lg:block">
          <div className="flex items-center justify-between px-4 pb-3">
            <h2 className="font-semibold text-navy">Structure</h2>
            <button type="button" className="flex items-center gap-1 text-sm font-medium text-accent">
              <Icon name="plus" className="h-4 w-4" /> Add
            </button>
          </div>
          <ContentTree toc={SAMPLE_TOC} selectedId="s64" draftIds={new Set(['s64'])} />
        </aside>

        <main className="min-w-0 flex-1 overflow-y-auto">
          <div className="border-b border-border bg-surface px-6 py-4">
            <p className="text-sm text-ink-muted">Unit 2 / Chapter 6, Vital signs / Section 6.4</p>
            <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-2">
              <h1 className="font-serif text-2xl font-semibold text-navy">Blood pressure</h1>
              <p className="text-sm text-ink-muted">Draft saved at 14:32, not yet published</p>
            </div>
          </div>

          <div role="toolbar" aria-label="Formatting" className="flex flex-wrap gap-1 border-b border-border bg-surface px-4 py-2">
            {TOOLS.map((tool) => (
              <button
                key={tool}
                type="button"
                className="h-8 px-2.5 text-sm text-ink hover:bg-surface-muted aria-pressed:bg-navy aria-pressed:text-white"
                aria-pressed={tool === 'Callout'}
              >
                {tool}
              </button>
            ))}
          </div>

          <div className="px-4 py-8 sm:px-8">
            <div className="mx-auto max-w-prose border border-border bg-surface px-6 py-8 shadow-[0_1px_0_rgb(216_224_230)] sm:px-10">
              <ContentRenderer document={SAMPLE_SECTION_BLOOD_PRESSURE} />
            </div>
          </div>
        </main>

        <aside className="hidden w-80 shrink-0 border-l border-border bg-surface p-5 xl:block">
          <h2 className="font-semibold text-navy">Publish changes</h2>
          <label htmlFor="note" className="mt-5 block text-sm font-medium text-ink">Change note</label>
          <textarea
            id="note"
            rows={3}
            defaultValue="Add documentation practice point"
            className="mt-1.5 w-full resize-none border border-border p-2.5 text-sm outline-none focus:border-accent"
          />
          <p className="mt-1.5 text-xs text-ink-muted">Shown in version history. Required to publish.</p>

          <div className="mt-6 border-t border-border pt-5 text-sm">
            <p className="text-ink">Publishing creates version 8.</p>
            <p className="mt-1 text-ink-muted">Version 7 stays in the history and can be restored.</p>
            <p className="mt-4 text-ink">42 students have a saved position in this section.</p>
            <p className="mt-1 text-ink-muted">Their positions are kept when you publish.</p>
          </div>

          <div className="mt-6 grid gap-2">
            <button type="button" className="h-10 bg-navy font-medium text-white hover:bg-navy/90">Publish</button>
            <Link
              href="/preview/reader"
              className="flex h-10 items-center justify-center gap-2 border border-border font-medium text-navy hover:border-accent"
            >
              <Icon name="eye" className="h-4 w-4" /> Preview as student
            </Link>
            <Link href="/preview/cms/history" className="mt-2 text-center text-sm text-accent hover:underline">
              Version history
            </Link>
          </div>
        </aside>
      </div>
    </div>
  );
}
