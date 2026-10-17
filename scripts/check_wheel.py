"""Install a wheel into a clean environment and test its entry point/resources."""
import json
from email.parser import Parser
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import traceback
import venv
import zipfile


def main():
    wheels = sorted(Path(sys.argv[1] if len(sys.argv) > 1 else 'dist').glob('xcmd_tool-*.whl'))
    if not wheels:
        raise SystemExit('No xcmd-tool wheel found; run python -m build first')
    wheel = wheels[-1].resolve()
    with zipfile.ZipFile(wheel) as archive:
        metadata_file = next(name for name in archive.namelist() if name.endswith('.dist-info/METADATA'))
        expected_version = Parser().parsestr(archive.read(metadata_file).decode('utf-8'))['Version']
    with tempfile.TemporaryDirectory(prefix='xcmd-wheel-') as temporary:
        work = Path(temporary)
        environment = work / 'venv'
        venv.EnvBuilder(with_pip=False).create(environment)
        bin_dir = environment / ('Scripts' if os.name == 'nt' else 'bin')
        python = bin_dir / ('python.exe' if os.name == 'nt' else 'python')
        executable = bin_dir / ('xcmd.exe' if os.name == 'nt' else 'xcmd')
        subprocess.run([sys.executable, '-m', 'pip', '--python', str(python),
                        'install', '--no-index', '--no-deps', str(wheel)], check=True)
        env = dict(os.environ, XCMD_CONFIG=str(work / 'commands.conf'), PYTHONUTF8='1')

        def run(*args):
            return subprocess.run([str(executable), *args], cwd=work, env=env,
                                  check=True, capture_output=True, text=True, encoding='utf-8').stdout

        assert run('--version').strip() == 'xcmd ' + expected_version
        run('--init')
        assert run('hello').strip() == 'Hello from xcmd'
        assert json.loads(run('--complete-json', 'h'))[0]['name'] == 'hello'
        for shell in ('bash', 'powershell'):
            rendered = run('--completion', shell)
            assert len(rendered) > 100
            assert '@RUNNER@' not in rendered
            run('--install-completion', shell, '--profile', str(work / (shell + '.profile')))
        print('Wheel smoke test passed: entry point, execution, config, resources and profile installation.')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        if os.environ.get('GITHUB_ACTIONS'):
            details = traceback.format_exc().replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
            print('::error::' + details, flush=True)
        raise
