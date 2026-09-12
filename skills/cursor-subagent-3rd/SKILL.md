---
name: cursor-subagent-3rd
description: "Delegate tasks to user-selected third-party models through Cursor CLI, including GPT Sol/Terra/Luna, Claude Opus/Sonnet/Fable, Gemini, and other models available in the user's Cursor account. Use when the user invokes cursor-subagent-3rd or asks for Cursor agents with a non-Grok model, including Turkish requests such as 'Bu taskı cursor-subagent-3rd ile gpt sol agentları ile yap'. Grok delegation belongs to grok-subagent."
---

# Cursor Subagent 3rd

Keep orchestration here and run delegated work through the local Cursor CLI with the user's chosen model. GPT and Claude selections here both run through Cursor, not native Codex subagents, Claude Code, or separate provider API clients. Cursor account usage applies to delegated calls; orchestration still uses this conversation's quota.

## Model selection

Run `agent models` once at the start of the task to discover models available to this account. Use `agent --list-models` if needed. Do not inspect authentication files or print keys.

Resolve the user's wording against that live list. Preserve the family and any requested version, effort, thinking, or fast modifier. Pass the exact listed ID to `--model` on every dispatch, including resumes. Never invent slugs such as `gpt-sol` or `claude-opus`.

For an unversioned family, select its newest clearly versioned listed release. If effort is unspecified, prefer `high`, then `medium`, then the unqualified model. Prefer non-fast unless fast is requested. For Claude, honor an explicit thinking preference; otherwise prefer non-thinking when available. These are skill defaults, not claims about Cursor defaults.

Announce the selected ID briefly and proceed when the match is clear. If no family was named, ask which to use. A bare `Claude` or `GPT` does not select a family: ask whether the user wants Opus/Sonnet/etc. or Sol/Terra/etc. If a requested version or modifier is unavailable, show the nearest available choices and ask. Never silently substitute another provider, Grok, Composer, or `auto`.

Model IDs are account-dependent. For example, “GPT Sol” selects the listed Sol family and “Claude Opus” selects the listed Opus family; these names are not literal CLI IDs. Do not treat examples as proof that a model is available or has been tested.

Support other third-party families, including Gemini, Fable, Muse Spark, Kimi, and GLM, by resolving against the same live list rather than a fixed provider allowlist. If the user assigns different models to different roles, preserve that mapping. A single selected model applies to all workers unless instructed otherwise.

## Delegation

Explicit invocation means use Cursor even for one small task. Choose agent count from independent responsibilities; plural wording alone does not require redundant agents. Do not use native Codex subagents, `codex exec`, another provider's CLI, or nested agents for delegated work. The Grok skill's generic triggers do not override this skill's model selection.

Use agent mode for implementation, `--mode ask` for read-only research/review, and `--mode plan` only for explicitly requested planning. Write self-contained prompt files using [references/prompt-template.md](references/prompt-template.md). Include the goal, absolute workspace, relevant conversation context, owned files, constraints, and acceptance checks. Cursor workers cannot see this conversation.

For parallel work, define disjoint write ownership and shared interfaces before launching independent script processes. Tell workers they share the codebase, must preserve others' edits, and must not spawn agents. Sequential follow-ups should resume the same agent.

Delegate only actions already authorized for the task. Commit/push, deployment, external messages, and unrelated account changes require their own user authorization.

## Dispatch

Create a unique task directory with the platform temp API; in a POSIX shell, set `TASK_DIR="$(mktemp -d)"` and write the prompt files there before dispatch.

The bundled runner requires an explicit model; it has no Grok or automatic fallback. Resolve its path relative to this installed skill if moved. Prefer prompt files over inline shell strings.

```bash
THIRD_PARTY_SCRIPT="${CODEX_HOME:-$HOME/.codex}/skills/cursor-subagent-3rd/scripts/spawn_cursor_agent.py"
python3 "$THIRD_PARTY_SCRIPT" --model "$SOL_MODEL" --label implementation --workspace /absolute/repo --prompt-file "$TASK_DIR/cursor-third-party-task.md" --out "$TASK_DIR/cursor-third-party-task.json"
```

Set `SOL_MODEL` and `OPUS_MODEL` to exact IDs from the live list before using these commands. Claude review example:

```bash
python3 "$THIRD_PARTY_SCRIPT" --model "$OPUS_MODEL" --mode ask --label review --workspace /absolute/repo --prompt-file "$TASK_DIR/cursor-third-party-review.md" --out "$TASK_DIR/cursor-third-party-review.json"
```

Use unique temporary prompt and receipt paths per task/lane. `--dry-run` checks command construction without making a model call; it does not validate account access. Authentication uses the existing local `agent` login or `CURSOR_API_KEY` environment variable.

To give the same worker another task, keep its receipt and invoke the runner with `--resume <session_id>`, the same workspace, the explicit model, a new prompt file, and a new receipt path. Keep the prior model unless the user requests a change.

## Verify and finish

Read compact receipt fields: `ok`, `is_error`, `model`, `label`, `session_id`, and `result`. `model` records the requested model, not independent proof of server-side execution. Inspect changed files and relevant checks before reporting success. Report the chosen model, completed result, validation, and unresolved issues concisely.

On missing CLI, authentication failure, or unavailable model, report the concrete blocker; do not silently execute the delegated task in another runtime. For recoverable failures, inspect the receipt and resume or narrow the task; avoid repeated identical retries. On timeout, inspect partial work and any known session before starting another agent that could duplicate edits. Do not claim rollback or a resumable session unless confirmed.

## Runner behavior

Both skills use one shared runtime in the repository checkout. Agent mode passes `--force` with `--sandbox enabled`; disabling sandboxing requires explicit `--sandbox disabled`. Workspace trust is enabled for headless execution. MCP auto-approval is opt-in with `--approve-mcps`. Authentication comes from Cursor login or `CURSOR_API_KEY`; the runner does not accept keys on the command line.
