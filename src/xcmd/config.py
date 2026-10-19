"""Configuration paths and platform-specific command definitions."""
from importlib import resources
import os
from pathlib import Path
import re


def current_platform():
    return 'windows' if os.name == 'nt' else 'linux'


def config_path():
    override = os.environ.get('XCMD_CONFIG') or os.environ.get('CMD_TOOL_CONFIG')
    if override:
        return Path(override).expanduser()
    if os.name == 'nt':
        return Path(os.environ.get('APPDATA') or Path.home() / 'AppData/Roaming') / 'xcmd/commands.conf'
    base = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')
    modern, legacy = base / 'xcmd/commands.conf', base / 'cmd-tool/commands.conf'
    return legacy if legacy.is_file() and not modern.exists() else modern


def read_commands(path, platform=None):
    platform = platform or current_platform()
    sections = {name: {} for name in ('all', 'linux', 'windows')}
    section = 'all'
    try:
        content = path.read_text(encoding='utf-8-sig')
    except FileNotFoundError:
        raise ValueError(f'{path}: config not found; run xc --init') from None
    for number, raw in enumerate(content.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('['):
            if line not in ('[all]', '[linux]', '[windows]'):
                raise ValueError(f'{path}:{number}: expected [all], [linux] or [windows]')
            section = line[1:-1]
            continue
        parts = re.split(r'\s+--\s+', line, maxsplit=1)
        if len(parts) != 2 or not parts[1].strip() or '\x00' in line:
            raise ValueError(f'{path}:{number}: expected "name -- command" with a nonempty command')
        name, command = parts[0].strip(), parts[1].strip()
        if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*', name):
            raise ValueError(f'{path}:{number}: invalid name: {name!r}')
        if name in sections[section]:
            raise ValueError(f'{path}:{number}: duplicate name in [{section}]: {name}')
        sections[section][name] = command
    return {**sections['all'], **sections[platform]}


def init_config(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    example = resources.files('xcmd').joinpath('resources/commands.conf').read_text(encoding='utf-8')
    try:
        with path.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(example)
    except FileExistsError:
        return False
    return True
