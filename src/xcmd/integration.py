"""Render completion scripts and install reversible profile integration."""
import codecs
from datetime import datetime
from importlib import resources
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

from .config import config_path
from .execution import powershell_executable


BEGIN, END = '# >>> xcmd completion >>>', '# <<< xcmd completion <<<'


def ps_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def render_completion(shell):
    if shell not in ('bash', 'powershell'):
        raise ValueError('completion supports bash and powershell')
    suffix = 'bash' if shell == 'bash' else 'ps1'
    quote = shlex.quote if shell == 'bash' else ps_quote
    template = resources.files('xcmd').joinpath(f'resources/completion.{suffix}').read_text(encoding='utf-8')
    runner = Path(__file__).with_name('entry.py').resolve()
    source_entry = Path(__file__).resolve().parents[2] / 'xcmd'
    console_entry = Path(sys.executable).parent / ('xcmd.exe' if sys.platform == 'win32' else 'xcmd')
    for marker, value in (('@PYTHON@', sys.executable), ('@RUNNER@', str(runner)),
                          ('@SOURCE_ENTRY@', str(source_entry)), ('@CONSOLE_ENTRY@', str(console_entry))):
        template = template.replace(marker, quote(value))
    return template


def install_completion(shell, profile=None):
    script = render_completion(shell)
    if profile is None:
        if shell == 'bash':
            profile = Path.home() / '.bashrc'
        else:
            result = subprocess.run([powershell_executable(), '-NoProfile', '-Command',
                                     '[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false; '
                                     '$PROFILE.CurrentUserAllHosts'],
                                    check=True, capture_output=True, text=True, encoding='utf-8')
            if not result.stdout.strip():
                raise ValueError('cannot locate the PowerShell profile; specify --profile PATH')
            profile = result.stdout.strip()
    profile = Path(profile).expanduser()
    raw = profile.read_bytes() if profile.exists() else b''
    if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        encoding = 'utf-16'
    elif raw.startswith(codecs.BOM_UTF8) or shell == 'powershell':
        encoding = 'utf-8-sig'
    else:
        encoding = 'utf-8'
    original = raw.decode(encoding)
    spans = []
    for begin, end in ((BEGIN, END), ('# >>> cmd-tool >>>', '# <<< cmd-tool <<<')):
        if original.count(begin) != original.count(end) or original.count(begin) > 1:
            raise ValueError(f'{profile}: incomplete or duplicate xcmd integration markers')
        if begin in original:
            start, stop = original.index(begin), original.index(end)
            if stop < start:
                raise ValueError(f'{profile}: reversed xcmd integration markers')
            spans.append((start, stop + len(end)))
    script_path = config_path().parent / ('completion.bash' if shell == 'bash' else 'completion.ps1')
    if (script_path.resolve() == profile.resolve() or script_path.resolve() == config_path().resolve()
            or profile.resolve() == config_path().resolve()):
        raise ValueError('completion script, profile and config must use different files')
    load = f'source {shlex.quote(str(script_path))}' if shell == 'bash' else f'. {ps_quote(script_path)}'
    block = f'{BEGIN}\n{load}\n{END}'
    updated = original
    if spans:
        for index, (start, stop) in reversed(list(enumerate(sorted(spans)))):
            updated = updated[:start] + (block if index == 0 else '') + updated[stop:]
    else:
        updated += ('\n' if updated and not updated.endswith('\n') else '') + '\n' + block + '\n'
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_bytes(script.encode('utf-8-sig' if shell == 'powershell' else 'utf-8'))
    if updated != original:
        profile.parent.mkdir(parents=True, exist_ok=True)
        if profile.exists():
            backup = profile.with_name(profile.name + '.xcmd.bak.' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
            shutil.copy2(profile, backup)
        if raw.startswith(codecs.BOM_UTF16_BE):
            profile.write_bytes(codecs.BOM_UTF16_BE + updated.encode('utf-16-be'))
        else:
            profile.write_bytes(updated.encode(encoding))
    return profile
