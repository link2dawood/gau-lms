/**
 * Split a search snippet into plain and highlighted parts.
 *
 * Snippets mark matches as `[[phrase]]`. Returning parts rather than HTML means
 * the caller renders <mark> elements itself and never injects markup, so a
 * snippet containing `<` cannot become an injection vector.
 */
export interface SnippetPart {
  readonly text: string;
  readonly match: boolean;
}

export function splitHighlights(snippet: string): SnippetPart[] {
  const parts: SnippetPart[] = [];
  const pattern = /\[\[(.+?)\]\]/g;
  let last = 0;
  for (const found of snippet.matchAll(pattern)) {
    const start = found.index ?? 0;
    if (start > last) parts.push({ text: snippet.slice(last, start), match: false });
    parts.push({ text: found[1] ?? '', match: true });
    last = start + found[0].length;
  }
  if (last < snippet.length) parts.push({ text: snippet.slice(last), match: false });
  return parts;
}
