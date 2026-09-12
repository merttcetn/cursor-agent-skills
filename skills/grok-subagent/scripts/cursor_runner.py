"""Shared, dependency-free Cursor CLI runner. No model calls during dry runs."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

DEFAULT_GROK_MODEL = 'cursor-grok-4.6-high-fast'
PROMPT_ARGV_LIMIT = 8000


def find_agent():
    for candidate in ('agent', 'cursor-agent', str(Path.home()/'.local/bin/agent'),
                      str(Path.home()/'.cursor/bin/agent')):
        found = shutil.which(candidate)
        if found:
            return found
    raise FileNotFoundError('Cursor CLI not found. Install Cursor CLI and run agent login.')


def parse_args(profile, argv=None):
    parser = argparse.ArgumentParser(description='Delegate a task through Cursor CLI.')
    parser.add_argument('prompt', nargs='*')
    sources = parser.add_mutually_exclusive_group()
    sources.add_argument('--prompt-file')
    sources.add_argument('--stdin', action='store_true')
    parser.add_argument('--model', required=profile == 'third-party',
                        default=DEFAULT_GROK_MODEL if profile == 'grok' else None)
    parser.add_argument('--mode', choices=('agent', 'ask', 'plan'), default='agent')
    parser.add_argument('--workspace', default=os.getcwd())
    parser.add_argument('--add-dir', action='append', default=[])
    parser.add_argument('--resume')
    parser.add_argument('--worktree', nargs='?', const='')
    parser.add_argument('--worktree-base')
    parser.add_argument('--sandbox', choices=('enabled', 'disabled'), default='enabled')
    parser.add_argument('--approve-mcps', action='store_true', help='Explicitly approve configured MCP servers')
    parser.add_argument('--output-format', choices=('json', 'text'), default='json')
    parser.add_argument('--label')
    parser.add_argument('--out')
    parser.add_argument('--timeout', type=int)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    args.model = args.model.strip()
    model = args.model.lower()
    if not model or model in ('auto', 'default'):
        parser.error('Use an exact model ID from agent models.')
    if profile == 'third-party' and ('grok' in model or 'composer' in model):
        parser.error('Use an explicit third-party model ID; Grok belongs to grok-subagent.')
    if args.prompt and (args.prompt_file or args.stdin):
        parser.error('Choose exactly one prompt source.')
    if args.timeout is not None and args.timeout <= 0:
        parser.error('--timeout must be positive.')
    if args.worktree_base and args.worktree is None:
        parser.error('--worktree-base requires --worktree.')
    if args.resume and args.worktree is not None:
        parser.error('Resume in the existing workspace; do not create another worktree.')
    args.workspace = str(Path(args.workspace).expanduser().resolve())
    if not Path(args.workspace).is_dir():
        parser.error('--workspace must be an existing directory.')
    args.add_dir = [str(Path(p).expanduser().resolve()) for p in args.add_dir]
    return args


def build_command(agent, args, prompt):
    cmd = [agent, '--print', '--output-format', args.output_format,
           '--model', args.model, '--trust', '--workspace', args.workspace]
    if args.approve_mcps:
        cmd.append('--approve-mcps')
    if args.mode == 'agent':
        cmd += ['--force', '--sandbox', args.sandbox]
    else:
        cmd += ['--mode', args.mode]
    for directory in args.add_dir:
        cmd += ['--add-dir', directory]
    if args.resume:
        cmd += ['--resume', args.resume]
    if args.worktree is not None:
        cmd.append('--worktree')
        if args.worktree:
            cmd.append(args.worktree)
        if args.worktree_base:
            cmd += ['--worktree-base', args.worktree_base]
    return cmd + ['--', prompt]


def redact_command(cmd):
    return cmd[:-1] + [f'<prompt {len(cmd[-1])} chars>']


def compact_receipt(raw, args, returncode):
    receipt = dict(ok=False, is_error=True, exit_code=returncode, model=args.model,
                   mode=args.mode, workspace=args.workspace, label=args.label)
    text = raw.strip()
    if args.output_format == 'text':
        receipt.update(ok=returncode == 0 and bool(text),
                       is_error=returncode != 0 or not text, result=text)
        return receipt
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError('Expected a JSON object')
    except ValueError:
        receipt.update(result=text, parse_error='Empty or invalid Cursor JSON output')
        return receipt
    for key in ('session_id', 'request_id', 'duration_ms', 'result', 'subtype'):
        if key in data:
            receipt[key] = data[key]
    error = returncode != 0 or bool(data.get('is_error')) or 'result' not in data
    receipt.update(ok=not error, is_error=error)
    return receipt


def emit(receipt, out):
    rendered = json.dumps(receipt, indent=2, ensure_ascii=False) + '\n'
    if out:
        Path(out).write_text(rendered, encoding='utf-8')
    sys.stdout.write(rendered)


def main(profile='third-party', argv=None):
    args = parse_args(profile, argv)
    staged = None
    try:
        prompt = (Path(args.prompt_file).expanduser().read_text(encoding='utf-8')
                  if args.prompt_file else sys.stdin.read() if args.stdin else ' '.join(args.prompt)).strip()
        if not prompt:
            raise ValueError('Provide a nonempty prompt, --prompt-file, or --stdin.')
        agent = 'agent' if args.dry_run else find_agent()
        prompt_path = None
        if len(prompt.encode('utf-8')) > PROMPT_ARGV_LIMIT:
            if args.prompt_file:
                prompt_path = str(Path(args.prompt_file).expanduser().resolve())
            elif args.dry_run:
                prompt_path = '<temporary-prompt-file>'
            else:
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                                 prefix='cursor-agent-prompt-', suffix='.md', delete=False) as f:
                    staged = Path(f.name)
                    f.write(prompt)
                    prompt_path = str(staged)
        instruction = (f'Read your full instructions from {json.dumps(prompt_path)} first. '
                       'Follow them and do not modify or delete the instruction file.'
                       if prompt_path else prompt)
        cmd = build_command(agent, args, instruction)
        if args.dry_run:
            receipt = dict(ok=True, dry_run=True, model=args.model, label=args.label,
                           prompt_chars=len(prompt), prompt_file=prompt_path, command=redact_command(cmd))
            code = 0
        else:
            completed = subprocess.run(cmd, cwd=args.workspace, capture_output=True,
                                       text=True, encoding='utf-8', errors='replace',
                                       timeout=args.timeout, check=False)
            receipt = compact_receipt(completed.stdout or completed.stderr, args, completed.returncode)
            receipt['command'] = redact_command(cmd)
            code = 0 if receipt['ok'] else completed.returncode or 2
    except subprocess.TimeoutExpired:
        receipt = dict(ok=False, is_error=True, exit_code=124, model=args.model,
                       label=args.label, session_id=args.resume,
                       result=f'Cursor timed out after {args.timeout}s; inspect partial work before retrying.')
        code = 124
    except (OSError, ValueError) as exc:
        receipt = dict(ok=False, is_error=True, model=args.model, label=args.label, result=str(exc))
        code = 1
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)
    try:
        emit(receipt, args.out)
    except OSError as exc:
        print(f'Cannot write receipt: {exc}', file=sys.stderr)
        return 1
    return code
