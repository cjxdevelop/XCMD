import codecs
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = os.environ.get('XCMD_POWERSHELL') or shutil.which('pwsh') or shutil.which('powershell')


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.config = self.work / 'commands.conf'
        self.config.write_text('push-test -- echo 中文\n', encoding='utf-8')
        self.env = dict(os.environ, XCMD_CONFIG=str(self.config), PYTHONUTF8='1')

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / 'xcmd'), *args], env=self.env,
                              text=True, capture_output=True, encoding='utf-8')

    def test_profile_installation_is_idempotent_and_backs_up_original(self):
        for shell in ('bash', 'powershell'):
            with self.subTest(shell=shell):
                profile = self.work / f'{shell} profile'
                original = '# existing user configuration\n'
                profile.write_bytes(original.replace('\n', '\r\n').encode('utf-8'))
                original_bytes = profile.read_bytes()
                for _ in range(2):
                    result = self.run_cli('--install-completion', shell, '--profile', str(profile))
                    self.assertEqual(result.returncode, 0, result.stderr)
                updated = profile.read_text(encoding='utf-8-sig')
                self.assertIn(original, updated)
                self.assertEqual(updated.count('# >>> xcmd completion >>>'), 1)
                backups = list(self.work.glob(profile.name + '.xcmd.bak.*'))
                self.assertEqual(len(backups), 1)
                self.assertEqual(backups[0].read_bytes(), original_bytes)
                self.assertEqual(self.config.read_text(encoding='utf-8'), 'push-test -- echo 中文\n')

    def test_powershell_profile_utf16_is_preserved(self):
        profile = self.work / 'profile.ps1'
        original = "# 已有设置\n"
        profile.write_bytes(original.encode('utf-16'))
        result = self.run_cli('--install-completion', 'powershell', '--profile', str(profile))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(profile.read_bytes().startswith(codecs.BOM_UTF16_LE))
        self.assertIn(original, profile.read_text(encoding='utf-16'))

    def test_powershell_profile_utf16_big_endian_is_preserved(self):
        profile = self.work / 'profile-be.ps1'
        original = '# 原配置\n'
        profile.write_bytes(codecs.BOM_UTF16_BE + original.encode('utf-16-be'))
        result = self.run_cli('--install-completion', 'powershell', '--profile', str(profile))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(profile.read_bytes().startswith(codecs.BOM_UTF16_BE))

    def test_profile_cannot_replace_the_command_configuration(self):
        original = self.config.read_bytes()
        result = self.run_cli('--install-completion', 'bash', '--profile', str(self.config))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(self.config.read_bytes(), original)

    def test_incomplete_profile_marker_is_not_overwritten(self):
        profile = self.work / 'profile'
        original = '# >>> xcmd completion >>>\nuser configuration\n'
        profile.write_text(original, encoding='utf-8')
        result = self.run_cli('--install-completion', 'bash', '--profile', str(profile))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(profile.read_text(), original)

    def test_unknown_completion_shell_fails_without_writing(self):
        result = self.run_cli('--completion', 'cmd.exe')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, '')

    @unittest.skipUnless(shutil.which('bash') and os.name != 'nt', 'Bash integration')
    def test_generated_bash_completion_handles_flags_and_show(self):
        result = self.run_cli('--completion', 'bash')
        self.assertEqual(result.returncode, 0, result.stderr)
        script = self.work / 'completion.bash'
        script.write_text(result.stdout, encoding='utf-8')
        syntax = subprocess.run(['bash', '-n', str(script)], capture_output=True, text=True)
        self.assertEqual(syntax.returncode, 0, syntax.stderr)
        query = f'''source '{script}'
COMP_WORDS=(xcmd --show p); COMP_CWORD=2; COMP_LINE='xcmd --show p'; COMP_POINT=13
_xcmd_tool_complete
printf '\\nRESULT:%s\\n' "${{COMPREPLY[@]}}"
COMP_WORDS=(xcmd --in); COMP_CWORD=1
_xcmd_tool_complete
printf '\\nFLAG:%s\\n' "${{COMPREPLY[@]}}"
'''
        completed = subprocess.run(['bash', '--noprofile', '--norc', '-c', query],
                                   env=self.env, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn('RESULT:push-test', completed.stdout)
        self.assertIn('FLAG:--init', completed.stdout)
        self.assertIn('FLAG:--install-completion', completed.stdout)

    @unittest.skipUnless(POWERSHELL, 'PowerShell is not installed')
    def test_powershell_tabexpansion_includes_command_tooltip(self):
        rendered = self.run_cli('--completion', 'powershell')
        self.assertEqual(rendered.returncode, 0, rendered.stderr)
        script = self.work / 'completion.ps1'
        script.write_text(rendered.stdout, encoding='utf-8-sig')
        quoted = str(script).replace("'", "''")
        expression = f'''. '{quoted}'
$items = @((TabExpansion2 'xcmd p' 6).CompletionMatches | Select-Object CompletionText, ToolTip)
ConvertTo-Json -InputObject $items -Compress
'''
        result = subprocess.run([POWERSHELL, '-NoProfile', '-Command', expression],
                                env=self.env, text=True, capture_output=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        values = json.loads(result.stdout)
        self.assertEqual(values[0]['CompletionText'], 'push-test')
        self.assertIn('echo 中文', values[0]['ToolTip'])

    @unittest.skipUnless(POWERSHELL, 'PowerShell is not installed')
    def test_powershell_legacy_empty_prefix_completion(self):
        rendered = self.run_cli('--completion', 'powershell')
        self.assertEqual(rendered.returncode, 0, rendered.stderr)
        script = self.work / 'legacy-completion.ps1'
        script.write_text(rendered.stdout, encoding='utf-8-sig')
        quoted = str(script).replace("'", "''")
        expression = f'''$PSNativeCommandArgumentPassing = 'Legacy'
. '{quoted}'
$result = @{{
  names = @((TabExpansion2 'xcmd ' 5).CompletionMatches | ForEach-Object {{ $_.CompletionText }})
  show = @((TabExpansion2 'xcmd --show ' 12).CompletionMatches | ForEach-Object {{ $_.CompletionText }})
}}
ConvertTo-Json -InputObject $result -Compress
'''
        result = subprocess.run([POWERSHELL, '-NoProfile', '-Command', expression],
                                env=self.env, text=True, capture_output=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertIn('push-test', data['names'])
        self.assertIn('push-test', data['show'])

    @unittest.skipUnless(POWERSHELL, 'PowerShell is not installed')
    def test_sample_hello_prints_one_line_in_powershell(self):
        self.env['XCMD_POWERSHELL'] = POWERSHELL
        self.config.write_bytes((ROOT / 'commands.conf').read_bytes())
        result = self.run_cli('--shell', 'powershell', 'hello')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'Hello from xcmd')

    @unittest.skipUnless(POWERSHELL, 'PowerShell is not installed')
    def test_powershell_execution_quoting_errors_and_exit_status(self):
        self.env['XCMD_POWERSHELL'] = POWERSHELL
        self.config.write_text('args -- Write-Output\nfail -- exit 23\n'
                               'error -- Get-Item /xcmd-path-that-does-not-exist\n'
                               f"native -- & '{sys.executable.replace(chr(39), chr(39) * 2)}' -c 'import sys; sys.exit(29)'\n",
                               encoding='utf-8')
        values = ['two words', "one'quote", '$(Write-Output INJECTED)', '中文']
        result = self.run_cli('--shell', 'powershell', 'args', *values)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), values)
        self.assertEqual(self.run_cli('--shell', 'powershell', 'fail').returncode, 23)
        self.assertEqual(self.run_cli('--shell', 'powershell', 'native').returncode, 29)
        self.assertNotEqual(self.run_cli('--shell', 'powershell', 'error').returncode, 0)


if __name__ == '__main__':
    unittest.main()
