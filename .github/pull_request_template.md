## Task

<!-- Backlog id and title from PROGRESS.md, e.g. "1.5 — Launch endpoint /lti/launch/" -->

Task: 
Depends on (all DONE): 

## What changed

<!-- 2 to 4 lines. What now exists that did not before. -->

## Evidence

<!-- Paste real output: pytest summary, Playwright summary, or the verified command.
     Assertions without pasted output are not evidence. -->

```
```

## Architecture checklist

- [ ] No cross-app model imports or raw queries into another module's tables (Section C.1)
- [ ] New content entities use UUID primary keys; page numbers are not used as identity (C.2)
- [ ] No `ContentVersion` row is updated or deleted by this change (C.3)
- [ ] No content change mutates, resets or orphans a learning record (C.4)
- [ ] No manual enrollment, course creation or role assignment in a production path (C.5)
- [ ] No hard-coded user ids, course ids, role strings, Canvas URLs, client ids or deployment ids (C.6)
- [ ] Content bodies are Tiptap JSON with a `blockId` on every top-level node (C.7)
- [ ] Every new API view declares an explicit permission class and is course-scoped (C.8)
- [ ] Students and faculty see published content only; drafts are admin preview only (C.9)
- [ ] Imports, indexing and roster sync run as Celery tasks, not inline in a request (C.10)

## Hygiene

- [ ] No TODO markers, stub returns, commented-out code or placeholder data left behind
- [ ] No dependency added outside the fixed stack (Section B) without an approved decision
- [ ] `PROGRESS.md` updated; `DECISIONS.md` appended if a binding decision was made
- [ ] Docs updated if this changes environment variables, setup or deployment

## Notes for the next loop

<!-- Anything the next task needs to know. "None" is a valid answer. -->
