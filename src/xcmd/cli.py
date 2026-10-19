"""Public command-line interface; completion never invokes the configured shell."""
import json
import os
import shlex
import subprocess
import sys

from . import __version__
from .config import config_path, init_config, read_commands
from .execution import command_line, execute


HELP = '''Usage: xc [--shell bash|powershell] NAME [ARGUMENTS...]

  --list                         List names and commands (also the default)
  --show NAME                    Show a command without executing it
  --config                       Print the active configuration path
  --init                         Create a sample config; never overwrite one
  --edit                         Edit with VISUAL / EDITOR / platform default
  --completion bash|powershell    Print a shell completion script
  --install-completion SHELL [--profile PATH]
                                 Install completion, backing up the profile
  --version                      Print the version
  --help                         Show this help

Config: name -- command. Optional sections: [all], [linux], [windows].
Linux commands use Bash; Windows commands use PowerShell.
Config changes take effect on the next command or completion.
'''


def run(arguments):
    args = list(arguments)
    shell = 'powershell' if os.name == 'nt' else 'bash'
    if args[:1] == ['--shell']:
        if len(args) < 3 or args[1] not in ('bash', 'powershell'):
            raise ValueError('usage: xc --shell bash|powershell NAME [ARGUMENTS...]')
        shell, args = args[1], args[2:]
    path = config_path()
    if args in (['--help'], ['-h']):
        print(HELP, end='')
        return 0
    if args == ['--version']:
        print(f'xc {__version__}')
        return 0
    if args == ['--config']:
        print(path)
        return 0
    if args == ['--init']:
        created = init_config(path)
        print(f'{"Created" if created else "Already exists"}: {path}')
        return 0
    if args[:1] == ['--completion']:
        from .integration import render_completion
        if len(args) != 2:
            raise ValueError('usage: xc --completion bash|powershell')
        print(render_completion(args[1]), end='')
        return 0
    if args[:1] == ['--install-completion']:
        from .integration import install_completion
        if len(args) == 2:
            profile = None
        elif len(args) == 4 and args[2] == '--profile':
            profile = args[3]
        else:
            raise ValueError('usage: xc --install-completion SHELL [--profile PATH]')
        print(f'Completion installed: {install_completion(args[1], profile)}')
        return 0
    if args == ['--edit']:
        editor = os.environ.get('VISUAL') or os.environ.get('EDITOR')
        if editor:
            values = shlex.split(editor, posix=os.name != 'nt')
            if os.name == 'nt':
                values = [value[1:-1] if len(value) > 1 and value[0] == value[-1] == '"' else value
                          for value in values]
        else:
            values = ['notepad' if os.name == 'nt' else 'nano']
        if not values:
            raise ValueError('EDITOR is empty')
        return subprocess.call([*values, str(path)])

    commands = read_commands(path)
    if not args or args == ['--list']:
        width = max(map(len, commands), default=0)
        for name, command in commands.items():
            print(f'{name:<{width}}  -- {command}')
        return 0
    if len(args) in (1, 2) and args[0] in ('--complete', '--complete-json'):
        prefix = args[1] if len(args) == 2 else ''
        matches = [{'name': name, 'command': command} for name, command in commands.items()
                   if name.startswith(prefix)]
        if args[0] == '--complete-json':
            print(json.dumps(matches, ensure_ascii=False))
        else:
            for item in matches:
                print(item['name'] + '\t' + item['command'].replace('\t', ' '))
        return 0
    if args[0] == '--show':
        if len(args) != 2:
            raise ValueError('usage: xc --show NAME')
        name = args[1]
    else:
        if args[0].startswith('-'):
            raise ValueError(f'unknown option: {args[0]}; use xc --help')
        name = args[0]
    if name not in commands:
        raise ValueError(f'unknown command: {name}; use xc --list')
    if args[0] == '--show':
        print(commands[name])
        return 0
    command = command_line(commands[name], args[1:], shell)
    print('+ ' + command, file=sys.stderr, flush=True)
    return execute(command, shell)


def main(argv=None):
    if os.name == 'nt':
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, 'reconfigure'):
                stream.reconfigure(encoding='utf-8')
    try:
        return run(sys.argv[1:] if argv is None else argv)
    except (OSError, UnicodeError, ValueError) as error:
        print(f'xc: {error}', file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
