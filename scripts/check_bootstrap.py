"""Install an actual wheel through pipx and verify sourced Shell integration."""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import traceback


ROOT = Path(__file__).resolve().parents[1]


def check(shell, wheel):
    with tempfile.TemporaryDirectory(prefix='xcmd-real-install-') as temporary:
        work = Path(temporary)
        home = work / 'home with spaces'
        home.mkdir()
        config = home / 'config/commands.conf'
        bin_dir = home / 'apps with spaces'
        profile = home / ('profile.ps1' if shell != 'bash' else '.bashrc')
        env = dict(os.environ, HOME=str(home), USERPROFILE=str(home),
                   XCMD_CONFIG=str(config), PIPX_HOME=str(home / 'pipx'),
                   PIPX_BIN_DIR=str(bin_dir), PIPX_DEFAULT_PYTHON=sys.executable,
                   PIPX_SHARED_LIBS=str(home / 'shared'), PYTHONUTF8='1')
        env.pop('CMD_TOOL_CONFIG', None)
        env.pop('PIPX_GLOBAL_HOME', None)
        if shell == 'bash':
            command = f'''source {shlex.quote(str(ROOT / 'install.sh'))} {shlex.quote(str(wheel))} || exit $?
[[ $(xc --complete h) == hello$'\\t'* ]] || exit 20
COMP_WORDS=(xc h); COMP_CWORD=1; COMP_LINE='xc h'; COMP_POINT=6
_xcmd_tool_complete
[[ ${{COMPREPLY[0]}} == hello ]] || exit 21
printf 'custom -- echo preserved\\n' > "$XCMD_CONFIG"
source {shlex.quote(str(ROOT / 'install.sh'))} {shlex.quote(str(wheel))} || exit $?
[[ $(xc --complete custom) == custom$'\\t'* ]] || exit 22
'''
            executable = shutil.which('bash')
            args = [executable, '--noprofile', '--norc', '-c', command]
            future = [executable, '--noprofile', '--rcfile', str(profile), '-ic',
                      'complete -p xc && xc --complete custom']
        else:
            quote = lambda value: "'" + str(value).replace("'", "''") + "'"
            command = f'''$ErrorActionPreference = 'Stop'
$PROFILE = {quote(profile)}
. {quote(ROOT / 'install.ps1')} -Package {quote(wheel)}
if ((Get-Command xc).Source -ne {quote(bin_dir / 'xc.exe')}) {{ throw 'Unexpected launcher path' }}
if (@((TabExpansion2 'xc h' 4).CompletionMatches.CompletionText) -notcontains 'hello') {{ throw 'Current-session completion failed' }}
[IO.File]::WriteAllText($env:XCMD_CONFIG, "custom -- echo preserved`n")
. {quote(ROOT / 'install.ps1')} -Package {quote(wheel)}
if (@((TabExpansion2 'xc custom' 9).CompletionMatches.CompletionText) -notcontains 'custom') {{ throw 'Repeat completion failed' }}
'''
            args = [shell, '-NoProfile', '-Command', command]
            future_script = f'''$ErrorActionPreference = 'Stop'
$env:Path = [Environment]::GetEnvironmentVariable('Path', 'User') + ';' + $env:Path
. {quote(profile)}
if (@((TabExpansion2 'xc custom' 9).CompletionMatches.CompletionText) -notcontains 'custom') {{ throw 'Future completion failed' }}
xc --complete custom
'''
            future = [shell, '-NoProfile', '-Command', future_script]
        result = subprocess.run(args, env=env, capture_output=True, text=True, encoding='utf-8')
        if result.returncode:
            raise RuntimeError(result.stdout + '\n' + result.stderr)
        assert config.read_text(encoding='utf-8') == 'custom -- echo preserved\n'
        assert profile.read_text(encoding='utf-8-sig').count('# >>> xcmd completion >>>') == 1
        result = subprocess.run(future, env=env, capture_output=True, text=True, encoding='utf-8')
        if result.returncode:
            raise RuntimeError(result.stdout + '\n' + result.stderr)
        assert 'custom\t' in result.stdout
        print('Real pipx installer passed:', shell, flush=True)


def main():
    wheels = sorted(Path(sys.argv[1] if len(sys.argv) > 1 else 'dist').glob('xcmd_tool-*.whl'))
    if len(wheels) != 1:
        raise SystemExit('Expected exactly one wheel in the build directory: ' + repr(wheels))
    subprocess.run([sys.executable, '-m', 'pipx', '--version'], check=True)
    shells = ([path for name in ('pwsh', 'powershell') if (path := shutil.which(name))]
              if os.name == 'nt' else ['bash'])
    if not shells:
        raise SystemExit('No supported installation Shell found')
    for shell in shells:
        check(shell, wheels[0].resolve())


if __name__ == '__main__':
    try:
        main()
    except (Exception, SystemExit):
        if os.environ.get('GITHUB_ACTIONS'):
            details = traceback.format_exc().encode('ascii', 'backslashreplace').decode('ascii')
            details = details.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
            print('::error::' + details, flush=True)
        raise
