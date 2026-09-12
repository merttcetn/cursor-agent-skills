---
name: grok-subagent
description: "Offload implementation, research, review, and parallel work to Cursor CLI subagents running cursor-grok-4.6-high-fast while keeping coordination in the current Codex session. Use when the user invokes $grok-subagent, Codex would otherwise spawn its own subagents, run a long coding/research pass, or the user mentions Cursor subagent, grok 4.6, grok 4.6 high fast, offload to Cursor, or saving Codex limit/quota. Do not use for tiny one-shot edits already in context, git commit/push, or when the user invoked $cursor-subagent-3rd, or requested a non-Grok model through Cursor."
---

# Grok Subagent

Stay the orchestrator. Send real work to Cursor CLI agents on **Grok 4.6 High Fast**. Delegated model calls use the Cursor account. Coordination still uses the current Codex session and its usage limits.

Default model slug: `cursor-grok-4.6-high-fast`. Check `agent models` before dispatch; availability depends on the Cursor account. If unavailable, report it instead of silently substituting a model. Preserve a user-selected model on resumes.

## Hard rules

1. **Keep delegated execution in Cursor.** Do not launch Codex native subagents, `codex exec`, or extra Codex sessions for implementation, research, review, or parallel lanes.
2. **Do the cheap orchestration yourself.** Decompose, freeze the contract, write prompt files, dispatch, wait, summarize. That is the Codex job.
3. **Cursor agents have no Codex context.** Every prompt must be self-contained. See [prompt-template.md](references/prompt-template.md).
4. **Never nest.** Tell each Cursor agent not to spawn Codex, `codex exec`, or another Cursor agent.

Skip this skill and do the work inline when it is a tiny edit, a question already answerable from loaded context, or a git commit/push.

## Mode

Default is **agent** (writes and runs commands). Do not send subagents to plan mode; keep planning in the orchestrator.

For read-only research, exploration, or review, request `--mode ask` and explicitly forbid edits in the prompt.

Use `--mode plan` only if the user explicitly asks the subagent to produce a plan.

## Dispatch

Use the bundled script. Prefer `--prompt-file` so shell quoting cannot mangle the task. Create a unique task directory with the platform temp API; in a POSIX shell, set `TASK_DIR="$(mktemp -d)"` and write the prompt files there before dispatch.

```bash
SCRIPT="${CODEX_HOME:-$HOME/.codex}/skills/grok-subagent/scripts/spawn_cursor_agent.py"

python3 "$SCRIPT" \
  --label api \
  --workspace /absolute/repo \
  --prompt-file "$TASK_DIR/grok-subagent-api.md" \
  --out "$TASK_DIR/grok-subagent-api.json"
```

Resume the same Cursor session to assign follow-up work (this is how you "give that agent another task"):

```bash
python3 "$SCRIPT" \
  --resume "<session_id from the receipt>" \
  --workspace /absolute/repo \
  --prompt-file "$TASK_DIR/grok-subagent-api-followup.md" \
  --out "$TASK_DIR/grok-subagent-api-followup.json"
```

Read-only research:

```bash
python3 "$SCRIPT" --mode ask --workspace /absolute/repo --prompt-file "$TASK_DIR/research.md"
```

`--dry-run` prints a command preview with the prompt redacted, without executing Cursor or checking model availability. Auth is the local `agent` login or `CURSOR_API_KEY`.

## Workflow

1. Decide 1–5 responsibility-scoped lanes. If only one tiny lane, do it yourself. Pick **agent** for writes, **ask** for read-only research.
2. Freeze shared names/APIs/paths before dispatch. Siblings cannot talk.
3. Write one prompt file per lane from [prompt-template.md](references/prompt-template.md).
4. Dispatch independent lanes in parallel (multiple script processes). Sequential work uses `--resume` on the same `session_id`.
5. Wait for receipts. Read `--out` JSON, not raw agent transcripts.
6. Surface each lane by `label`. If the worker reports `needs_input` inside `result`, resume with `--resume`. Retry or re-scope `failed` / `blocked` instead of silently doing the work in Codex.

Receipt fields that matter: `ok`, `is_error`, `session_id`, `result`, `label`. Keep `session_id` if you may send another task.

## Prompt rules

- Absolute workspace path, owned files, forbidden files.
- Concrete definition of done.
- Compact return format; forbid dumping full file bodies.
- For parallel lanes, include sibling map + frozen contract.

## Failures

- `agent` missing: tell the user to install Cursor CLI (`curl https://cursor.com/install -fsS | bash`) or log in (`agent login`). Do not fall back to a Codex subagent.
- Auth/401: same — stop and report. Do not switch to Codex execution.
- Timeout/hang: report the label and `session_id`; ask whether to wait, resume, or abandon.

## Runner behavior

The entry point resolves the shared runtime relative to this skill through its installed symlink. For custom installs, use the actual skill path. Agent mode passes `--force` with `--sandbox enabled`; use `--sandbox disabled` only when the task requires it. Workspace trust is enabled for headless execution. MCP auto-approval requires explicit `--approve-mcps`. Never interpret these flags as authorization for unrelated actions.
