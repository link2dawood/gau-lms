/** Join class names, skipping falsy entries. The one place conditional classes are assembled. */
export function cn(...classes: ReadonlyArray<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(' ');
}
