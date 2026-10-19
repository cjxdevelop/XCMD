"""Exercise sourced installers with real launchers and an isolated pipx boundary."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import venv


ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = os.environ.get('XCMD_POWERSHELL') or shutil.which('pwsh') or shutil.which('powershell')


class BootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='xcmd-bootstrap-package-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.package = Path(cls.temporary.name)
        subprocess.run([sys.executable, '-m', 'pip', 'wheel', '--no-deps',
                        '--no-build-isolation', str(ROOT), '-w', str(cls.package)],
                       check=True, capture_output=True)
        cls.wheel = next(cls.package.glob('*.whl'))
        cls.venv = cls.package / 'environment with spaces'
        venv.EnvBuilder(with_pip=False).create(cls.venv)
        cls.bin = cls.venv / ('Scripts' if os.name == 'nt' else 'bin')
        python = cls.bin / ('python.exe' if os.name == 'nt' else 'python')
        subprocess.run([sys.executable, '-m', 'pip', '--python', str(python), 'install',
                        '--no-index', '--no-deps', str(cls.wheel)], check=True, capture_output=True)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='xcmd-bootstrap-user-')
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        self.profile = self.work / 'profile with spaces.ps1'
        self.config = self.work / 'config/commands.conf'
        self.log = self.work / 'pipx.jsonl'
        self.stub = self.work / 'pipx.py'
        self.stub.write_text('''import json, os, sys
from pathlib import Path
args = sys.argv[1:]
with open(os.environ['BOOTSTRAP_LOG'], 'a', encoding='utf-8') as stream:
    stream.write(json.dumps(args) + '\\n')
if args and args[0] == os.environ.get('BOOTSTRAP_FAIL'):
    print('simulated pipx failure', file=sys.stderr)
    raise SystemExit(17)
if args[:1] == ['environment']:
    print(os.environ['BOOTSTRAP_BIN'])
''', encoding='utf-8')
        self.env = dict(os.environ, HOME=str(self.work), USERPROFILE=str(self.work),
                        XCMD_CONFIG=str(self.config), BOOTSTRAP_BIN=str(self.bin),
                        BOOTSTRAP_LOG=str(self.log), BOOTSTRAP_STUB=str(self.stub),
                        BOOTSTRAP_PYTHON=sys.executable, PYTHONUTF8='1')
        self.env.pop('CMD_TOOL_CONFIG', None)
        self.env.pop('BOOTSTRAP_FAIL', None)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def bash(self, body):
        self.assertTrue((ROOT / 'install.sh').is_file(), 'Bash installer is missing')
        prefix = 'pipx() { "$BOOTSTRAP_PYTHON" "$BOOTSTRAP_STUB" "$@"; }\n'
        return subprocess.run(['bash', '--noprofile', '--norc', '-c', prefix + body],
                              env=self.env, text=True, capture_output=True, encoding='utf-8')

    def powershell(self, body):
        self.assertTrue((ROOT / 'install.ps1').is_file(), 'PowerShell installer is missing')
        quote = lambda value: "'" + str(value).replace("'", "''") + "'"
        prefix = ("$ErrorActionPreference = 'Stop'\n"
                  'function pipx { & $env:BOOTSTRAP_PYTHON $env:BOOTSTRAP_STUB @args }\n'
                  f'$PROFILE = {quote(self.profile)}\n')
        return subprocess.run([POWERSHELL, '-NoProfile', '-Command', prefix + body],
                              env=self.env, text=True, capture_output=True, encoding='utf-8')

    @unittest.skipUnless(os.name != 'nt' and shutil.which('bash'), 'Bash installer')
    def test_bash_install_enables_current_and_future_sessions(self):
        import shlex
        result = self.bash(f'''source {shlex.quote(str(ROOT / 'install.sh'))} {shlex.quote(str(self.wheel))} || exit $?
complete -p xc
COMP_WORDS=(xc h); COMP_CWORD=1; COMP_LINE='xc h'; COMP_POINT=6
_xcmd_tool_complete
printf '\\nMATCH:%s\\n' "${{COMPREPLY[@]}}"
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('MATCH:hello', result.stdout)
        self.assertIn('complete -F _xcmd_tool_complete xc', result.stdout)
        self.assertTrue(self.config.is_file())
        future = subprocess.run(['bash', '--noprofile', '--rcfile', str(self.work / '.bashrc'),
                                 '-ic', 'complete -p xc; xc --complete h'],
                                env=self.env, text=True, capture_output=True, encoding='utf-8')
        self.assertEqual(future.returncode, 0, future.stderr)
        self.assertIn('hello\t', future.stdout)
        self.assertEqual(self.calls()[0], ['install', '--force', str(self.wheel)])

    @unittest.skipUnless(os.name != 'nt' and shutil.which('bash'), 'Bash installer')
    def test_bash_repeat_preserves_config_and_profile(self):
        import shlex
        self.config.parent.mkdir()
        original = b'push-test -- echo preserved\r\n'
        self.config.write_bytes(original)
        (self.work / '.bashrc').write_text('# existing settings\n')
        script = shlex.quote(str(ROOT / 'install.sh'))
        result = self.bash(f'source {script} local.whl && source {script} local.whl')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.config.read_bytes(), original)
        profile = (self.work / '.bashrc').read_text()
        self.assertIn('# existing settings', profile)
        self.assertEqual(profile.count('# >>> xcmd completion >>>'), 1)

    @unittest.skipUnless(os.name != 'nt' and shutil.which('bash'), 'Bash installer')
    def test_bash_install_failure_stops_before_configuration(self):
        import shlex
        self.env['BOOTSTRAP_FAIL'] = 'install'
        result = self.bash(f'source {shlex.quote(str(ROOT / "install.sh"))}; exit $?')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.config.exists())
        self.assertFalse((self.work / '.bashrc').exists())
        self.assertNotIn('completion enabled', result.stdout.lower())
        self.assertEqual([call[0] for call in self.calls()], ['install'])

    @unittest.skipUnless(os.name != 'nt' and shutil.which('bash'), 'Bash installer')
    def test_bash_must_be_sourced(self):
        self.assertTrue((ROOT / 'install.sh').is_file(), 'Bash installer is missing')
        result = subprocess.run(['bash', str(ROOT / 'install.sh')], env=self.env,
                                text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('source', result.stderr.lower())

    @unittest.skipUnless(os.name != 'nt' and shutil.which('bash'), 'Bash installer')
    def test_bash_missing_launcher_stops_before_configuration(self):
        import shlex
        self.env['BOOTSTRAP_BIN'] = str(self.work / 'empty bin')
        result = self.bash(f'source {shlex.quote(str(ROOT / "install.sh"))}; exit $?')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('did not expose', result.stderr)
        self.assertFalse(self.config.exists())

    @unittest.skipUnless(POWERSHELL, 'PowerShell installer')
    def test_powershell_install_enables_current_and_persistent_completion(self):
        quote = lambda value: "'" + str(value).replace("'", "''") + "'"
        result = self.powershell(f'''. {quote(ROOT / 'install.ps1')} -Package {quote(self.wheel)}
$items = @((TabExpansion2 'xc h' 4).CompletionMatches | ForEach-Object {{ $_.CompletionText }})
Write-Output ('MATCH:' + ($items -join ','))
Write-Output ('FOUND:' + (Get-Command xc).Name)
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('MATCH:hello', result.stdout)
        self.assertIn('FOUND:xc', result.stdout)
        self.assertIn('# >>> xcmd completion >>>', self.profile.read_text(encoding='utf-8-sig'))
        self.assertEqual(self.calls()[0], ['install', '--force', str(self.wheel)])
        future = self.powershell(f'''. {quote(self.profile)}
Write-Output ('MATCH:' + (((TabExpansion2 'xc h' 4).CompletionMatches | ForEach-Object {{ $_.CompletionText }}) -join ','))
''')
        self.assertEqual(future.returncode, 0, future.stderr)
        self.assertIn('MATCH:hello', future.stdout)

    @unittest.skipUnless(POWERSHELL, 'PowerShell installer')
    def test_powershell_download_style_repeat_preserves_config(self):
        self.config.parent.mkdir()
        original = b'push-test -- echo preserved\r\n'
        self.config.write_bytes(original)
        self.profile.write_bytes('# existing settings\r\n'.encode('utf-16'))
        script = str(ROOT / 'install.ps1').replace("'", "''")
        result = self.powershell(f'''$before = $ErrorActionPreference
1..2 | ForEach-Object {{ Get-Content -LiteralPath '{script}' -Raw | Invoke-Expression }}
if ($ErrorActionPreference -ne $before) {{ throw 'Preference changed' }}
Write-Output ('MATCH:' + (((TabExpansion2 'xc p' 4).CompletionMatches | ForEach-Object {{ $_.CompletionText }}) -join ','))
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('MATCH:push-test', result.stdout)
        self.assertEqual(self.config.read_bytes(), original)
        profile = self.profile.read_text(encoding='utf-16')
        self.assertIn('# existing settings', profile)
        self.assertEqual(profile.count('# >>> xcmd completion >>>'), 1)

    @unittest.skipUnless(POWERSHELL, 'PowerShell installer')
    def test_powershell_install_failure_stops_before_configuration(self):
        self.env['BOOTSTRAP_FAIL'] = 'install'
        script = str(ROOT / 'install.ps1').replace("'", "''")
        result = self.powershell(f". '{script}'")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.config.exists())
        self.assertFalse(self.profile.exists())
        self.assertNotIn('completion enabled', result.stdout.lower())
        self.assertEqual([call[0] for call in self.calls()], ['install'])

    @unittest.skipUnless(POWERSHELL, 'PowerShell installer')
    def test_powershell_missing_launcher_stops_before_configuration(self):
        self.env['BOOTSTRAP_BIN'] = str(self.work / 'empty bin')
        script = str(ROOT / 'install.ps1').replace("'", "''")
        result = self.powershell(f". '{script}'")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('did not expose', result.stderr)
        self.assertFalse(self.config.exists())


if __name__ == '__main__':
    unittest.main()
