# Cursor third-party worker prompt template

Cursor agents do not see the Codex conversation. Every dispatch must be self-contained.

Copy this shape into the prompt file:

```markdown
## Your task
<concrete end-to-end work this agent owns>

## Workspace
- Root: <absolute path>
- Files you own (read + write): <list>
- Files you must NOT touch: <list>
- Read-only references: <list>

## Constraints
- Do the work yourself. Do not spawn Codex, `codex exec`, or another Cursor agent.
- You share the codebase with other workers. Preserve their edits and adapt to them.
- Do not commit, push, deploy, send messages, or change account settings unless explicitly authorized in this task.
- Stay in scope. Do not invent APIs, names, or files the contract does not cover.
- Prefer the smallest change that completes the task.

## Frozen contract (if siblings exist)
<shared API/schema/names — conform, do not reinterpret>

## Siblings (if parallel)
- <label>: <one sentence> — owns <scope>
They run in parallel. You cannot talk to them.

## Return format (REQUIRED)
End with a compact summary. Do not dump full file contents.

- status: done | needs_input | blocked | failed
- summary: one paragraph
- files_changed: list of paths
- checks: commands/results, including failures and checks not run
- result: task-specific facts a sibling or master needs
- session note: anything a follow-up prompt should know
```

Keep the prompt under a few hundred lines. Point at files by path instead of pasting them unless the file is tiny or not on disk.
