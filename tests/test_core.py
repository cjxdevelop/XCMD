import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.config = self.work / 'commands.conf'
        self.config.write_text('hello -- echo hello\n', encoding='utf-8')
        self.env = dict(os.environ, XCMD_CONFIG=str(self.config), PYTHONUTF8='1')
        self.env.pop('CMD_TOOL_CONFIG', None)

    def run_cli(self, *args, input=None):
        return subprocess.run([sys.executable, str(ROOT / 'xcmd'), *args],
                              cwd=self.work, env=self.env, input=input,
                              capture_output=True, text=True, encoding='utf-8')

    def test_version_and_help_do_not_require_config(self):
        self.config.unlink()
        result = self.run_cli('--version')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('xcmd 0.1.0', result.stdout)
        self.assertIn('--install-completion', self.run_cli('--help').stdout)

    def test_new_config_override_takes_priority_over_legacy_override(self):
        self.env['CMD_TOOL_CONFIG'] = str(self.work / 'missing.conf')
        result = self.run_cli('--config')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Path(result.stdout.strip()), self.config)

    def test_init_creates_config_but_never_overwrites_it(self):
        self.config.unlink()
        result = self.run_cli('--init')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('hello --', self.config.read_text(encoding='utf-8-sig'))
        self.config.write_text('mine -- echo preserved\n', encoding='utf-8')
        result = self.run_cli('--init')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.config.read_text(), 'mine -- echo preserved\n')

    def test_platform_sections_override_common_independent_of_order(self):
        platform = 'windows' if os.name == 'nt' else 'linux'
        other = 'linux' if platform == 'windows' else 'windows'
        self.config.write_text(f'[{platform}]\nhello -- echo local\n'
                               f'[{other}]\nhello -- echo other\n'
                               '[all]\nhello -- echo shared\n', encoding='utf-8')
        result = self.run_cli('--show', 'hello')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'echo local')

    def test_duplicate_and_unknown_sections_report_line_without_execution(self):
        for content in ('[all]\nhello -- echo a\nhello -- echo b\n',
                        '[typo]\nhello -- echo a\n'):
            with self.subTest(content=content):
                self.config.write_text(content, encoding='utf-8')
                result = self.run_cli('hello')
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn(str(self.config), result.stderr)
                self.assertEqual(result.stdout, '')

    def test_json_completion_is_unicode_and_side_effect_free(self):
        self.config.write_text('push-test -- echo 中文\nother -- echo other\n', encoding='utf-8')
        result = self.run_cli('--complete-json', 'p')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [{'name': 'push-test', 'command': 'echo 中文'}])
        self.assertEqual(result.stderr, '')

    def test_completion_without_a_prefix_lists_all_names(self):
        result = self.run_cli('--complete-json')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)[0]['name'], 'hello')

    def test_completion_and_execution_reload_changes(self):
        self.assertEqual(self.run_cli('hello').stdout.strip(), 'hello')
        self.config.write_text('next -- echo updated\n', encoding='utf-8')
        self.assertEqual(self.run_cli('--complete', 'n').stdout, 'next\techo updated\n')
        self.assertEqual(self.run_cli('next').stdout.strip(), 'updated')

    def test_shell_execution_uses_working_directory_and_exit_code(self):
        command = '(Get-Location).Path' if os.name == 'nt' else 'pwd'
        self.config.write_text(f'where -- {command}\nfail -- exit 23\n', encoding='utf-8')
        result = self.run_cli('where')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Path(result.stdout.strip()), self.work)
        self.assertEqual(self.run_cli('fail').returncode, 23)

    def test_extra_arguments_are_data_in_both_shells(self):
        command = 'Write-Output' if os.name == 'nt' else "printf '%s\\n'"
        self.config.write_text(f'args -- {command}\n', encoding='utf-8')
        values = ['two words', "one'quote", '$(echo EXPANDED)', '; echo INJECTED', '中文']
        result = self.run_cli('args', *values)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), values)

    def test_config_commands_support_pipes(self):
        command = "'abc' | ForEach-Object { $_.ToUpper() }" if os.name == 'nt' else 'printf abc | tr a-z A-Z'
        self.config.write_text(f'pipe -- {command}\n', encoding='utf-8')
        result = self.run_cli('pipe')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'ABC')


if __name__ == '__main__':
    unittest.main()
