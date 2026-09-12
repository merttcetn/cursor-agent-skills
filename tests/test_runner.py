import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'shared'))
import cursor_runner as runner


class RunnerTests(unittest.TestCase):
    def invoke(self, profile, argv):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = runner.main(profile, argv)
        return code, json.loads(output.getvalue())

    def test_dry_run_never_executes_or_discovers_cli(self):
        with patch.object(runner, 'find_agent', side_effect=AssertionError), patch.object(runner.subprocess, 'run', side_effect=AssertionError):
            code, data = self.invoke('grok', ['--dry-run', 'private prompt'])
        self.assertEqual(code, 0)
        self.assertEqual(data['model'], runner.DEFAULT_GROK_MODEL)
        self.assertNotIn('private prompt', json.dumps(data))
        self.assertIn('enabled', data['command'])
        self.assertNotIn('--approve-mcps', data['command'])

    def test_third_party_requires_explicit_model(self):
        for argv in ([], ['--model', 'auto'], ['--model', 'cursor-grok-test'], ['--model', 'composer-test']):
            with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                runner.parse_args('third-party', argv)

    def test_resume_mode_and_paths_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix='workspace with spaces ') as directory:
            prompt = Path(directory)/'task with spaces.md'
            prompt.write_text('Do the review.', encoding='utf-8')
            code, data = self.invoke('third-party', ['--model', 'example-opus-id', '--mode', 'ask', '--resume', 'session-123', '--workspace', directory, '--prompt-file', str(prompt), '--dry-run'])
        self.assertEqual(code, 0)
        cmd = data['command']
        self.assertEqual(cmd[cmd.index('--resume')+1], 'session-123')
        self.assertEqual(cmd[cmd.index('--workspace')+1], str(Path(directory).resolve()))
        self.assertNotIn('--force', cmd)

    def test_invalid_prompt_and_option_combinations(self):
        for argv in (['--stdin', 'inline'], ['--timeout', '0'], ['--resume', 'id', '--worktree'], ['--worktree-base', 'main']):
            with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                runner.parse_args('grok', argv)
        code, data = self.invoke('grok', ['--dry-run'])
        self.assertNotEqual(code, 0)
        self.assertTrue(data['is_error'])

    def test_receipt_errors_cannot_report_success(self):
        args = runner.parse_args('grok', [])
        for raw, code in [('', 0), ('not json', 0), ('[]', 0), ('{}', 0), ('{"is_error":true,"result":"failed"}', 0), ('{"result":"done"}', 1)]:
            with self.subTest(raw=raw, code=code):
                data = runner.compact_receipt(raw, args, code)
                self.assertFalse(data['ok'])
                self.assertTrue(data['is_error'])
        data = runner.compact_receipt('{"result":"done","session_id":"test-session"}', args, 0)
        self.assertTrue(data['ok'])
        self.assertEqual(data['session_id'], 'test-session')

    def test_text_output(self):
        args = runner.parse_args('grok', ['--output-format', 'text'])
        self.assertTrue(runner.compact_receipt('done', args, 0)['ok'])
        self.assertFalse(runner.compact_receipt('', args, 0)['ok'])

    def test_timeout_cleans_staged_prompt_and_writes_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)/'receipt.json'
            staged = []
            def timeout(cmd, **kwargs):
                instruction = cmd[-1]
                path = Path(json.loads(instruction.split('from ', 1)[1].split(' first.', 1)[0]))
                staged.append(path)
                self.assertTrue(path.is_file())
                self.assertEqual(path.read_text(encoding='utf-8'), 'x'*9000)
                raise subprocess.TimeoutExpired(cmd, 1)
            with patch.object(runner, 'find_agent', return_value='fake-agent'), patch.object(runner.subprocess, 'run', side_effect=timeout):
                code, data = self.invoke('grok', ['--timeout', '1', '--out', str(out), 'x'*9000])
            self.assertEqual(code, 124)
            self.assertEqual(json.loads(out.read_text())['exit_code'], 124)
            self.assertIsNone(data['session_id'])
            self.assertFalse(staged[0].exists())

    def test_mocked_success_and_environment_auth(self):
        with patch.object(runner, 'find_agent', return_value='fake-agent'), patch.object(runner.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '{"result":"done","session_id":"mock-id"}', '')) as run, patch.dict(os.environ, {'CURSOR_API_KEY': 'synthetic-test-only'}):
            code, data = self.invoke('third-party', ['--model', 'example-model-id', 'task'])
        self.assertEqual(code, 0)
        self.assertEqual(data['session_id'], 'mock-id')
        self.assertNotIn('synthetic-test-only', json.dumps(data))
        self.assertNotIn('--api-key', run.call_args.args[0])

    def test_missing_cli_writes_failure_receipt(self):
        with patch.object(runner, 'find_agent', side_effect=FileNotFoundError('CLI missing')):
            code, data = self.invoke('grok', ['task'])
        self.assertEqual(code, 1)
        self.assertFalse(data['ok'])

    def test_long_prompt_file_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            prompt = Path(directory)/'instructions.md'
            prompt.write_text('ş'*5000, encoding='utf-8')
            with patch.object(runner, 'find_agent', return_value='fake-agent'), patch.object(runner.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '{"result":"done"}', '')) as run:
                code, data = self.invoke('grok', ['--prompt-file', str(prompt)])
            self.assertEqual(code, 0)
            self.assertTrue(prompt.exists())
            instruction = run.call_args.args[0][-1]
            encoded_path = instruction.split('from ', 1)[1].split(' first.', 1)[0]
            self.assertEqual(Path(json.loads(encoded_path)), prompt.resolve())
            self.assertEqual(prompt.read_text(encoding='utf-8'), 'ş'*5000)

    def test_long_stdin_dry_run_does_not_create_temp_files(self):
        with patch.object(runner.sys, 'stdin', io.StringIO('x'*9000)), patch.object(runner.tempfile, 'NamedTemporaryFile', side_effect=AssertionError):
            code, data = self.invoke('grok', ['--stdin', '--dry-run'])
        self.assertEqual(code, 0)
        self.assertEqual(data['prompt_file'], '<temporary-prompt-file>')

    def test_worktree_and_explicit_permissions(self):
        args = runner.parse_args('grok', ['--worktree', 'feature', '--worktree-base', 'main', '--sandbox', 'disabled', '--approve-mcps'])
        cmd = runner.build_command('fake-agent', args, '--leading-dash-prompt')
        self.assertIn('--approve-mcps', cmd)
        self.assertEqual(cmd[cmd.index('--sandbox')+1], 'disabled')
        self.assertEqual(cmd[cmd.index('--worktree')+1], 'feature')
        self.assertEqual(cmd[-2:], ['--', '--leading-dash-prompt'])

    def test_vendored_runners_match_canonical_runtime(self):
        canonical = (ROOT/'shared/cursor_runner.py').read_bytes()
        for name in ('grok-subagent', 'cursor-subagent-3rd'):
            with self.subTest(name=name):
                self.assertEqual((ROOT/'skills'/name/'scripts/cursor_runner.py').read_bytes(), canonical)

    def test_wrappers_work_without_cursor(self):
        for name, extra in [('grok-subagent', []), ('cursor-subagent-3rd', ['--model', 'example-id'])]:
            completed = subprocess.run([sys.executable, str(ROOT/'skills'/name/'scripts/spawn_cursor_agent.py'), '--dry-run', *extra, 'task'], capture_output=True, text=True, check=True)
            self.assertTrue(json.loads(completed.stdout)['dry_run'])

    def test_skill_folders_work_when_copied_standalone(self):
        for name, extra in [('grok-subagent', []), ('cursor-subagent-3rd', ['--model', 'example-id'])]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                copied = Path(directory)/name
                shutil.copytree(ROOT/'skills'/name, copied)
                completed = subprocess.run([sys.executable, str(copied/'scripts/spawn_cursor_agent.py'), '--dry-run', *extra, 'task'], capture_output=True, text=True, check=True)
                self.assertTrue(json.loads(completed.stdout)['dry_run'])


if __name__ == '__main__':
    unittest.main()
