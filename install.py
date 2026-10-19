#!/usr/bin/env python3
"""安装到当前用户目录；保留配置，备份并幂等更新 Bash 初始化文件。"""

from datetime import datetime
import os
from pathlib import Path
import shlex
import shutil
import sys


BEGIN = '# >>> cmd-tool >>>'
END = '# <<< cmd-tool <<<'


def install():
    source = Path(__file__).resolve().parent
    home = Path.home()
    data = home / 'bin/cmd-tool'
    old_data = Path(os.environ.get('XDG_DATA_HOME') or home / '.local/share') / 'cmd-tool'
    config = Path(os.environ.get('CMD_TOOL_CONFIG') or
                  Path(os.environ.get('XDG_CONFIG_HOME') or home / '.config') /
                  'cmd-tool/commands.conf').expanduser()
    executable = home / 'bin/xcmd'
    short_executable = home / 'bin/xc'
    rc = home / '.bashrc'

    # 在写文件前检查入口冲突和已有初始化块，避免覆盖无关程序。
    if executable.exists() or executable.is_symlink():
        if not executable.is_symlink() or executable.resolve() not in (
                (data / 'xcmd').resolve(), (old_data / 'xcmd').resolve()):
            raise ValueError(f'{executable} 已存在且不属于本工具，请先选择其他名称或迁移原文件')
    if short_executable.exists() or short_executable.is_symlink():
        if not short_executable.is_symlink() or short_executable.resolve() != (data / 'xc').resolve():
            raise ValueError(f'{short_executable} 已存在且不属于本工具，请先选择其他名称或迁移原文件')
    original = rc.read_text() if rc.exists() else ''
    if original.count(BEGIN) != original.count(END) or original.count(BEGIN) > 1:
        raise ValueError(f'{rc} 中的 cmd-tool 标记不完整，请先修复')
    if BEGIN in original and original.index(END) < original.index(BEGIN):
        raise ValueError(f'{rc} 中的 cmd-tool 标记顺序错误')

    quoted = shlex.quote(str(data / 'completion.bash'))
    block = f'{BEGIN}\nif [ -r {quoted} ]; then\n    source {quoted}\nfi\n{END}'
    if BEGIN in original:
        start = original.index(BEGIN)
        end = original.index(END) + len(END)
        updated = original[:start] + block + original[end:]
    else:
        updated = original + ('\n' if original and not original.endswith('\n') else '')
        updated += '\n' + block + '\n'

    data.mkdir(parents=True, exist_ok=True)
    for name in ('xc', 'xcmd', 'completion.bash'):
        if (source / name).resolve() != (data / name).resolve():
            shutil.copy2(source / name, data / name)
    if (source / 'src').resolve() != (data / 'src').resolve():
        shutil.copytree(source / 'src', data / 'src', dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    (data / 'xcmd').chmod(0o755)
    (data / 'xc').chmod(0o755)
    config.parent.mkdir(parents=True, exist_ok=True)
    if not config.exists():
        # x 模式保证不会覆盖同时创建的用户配置。
        with config.open('x', encoding='utf-8') as stream:
            stream.write((source / 'commands.conf').read_text())
    executable.parent.mkdir(parents=True, exist_ok=True)
    if executable.is_symlink() and executable.resolve() != (data / 'xcmd').resolve():
        executable.unlink()
    if not executable.is_symlink():
        executable.symlink_to(data / 'xcmd')
    if not short_executable.is_symlink():
        short_executable.symlink_to(data / 'xc')
    # 仅移除旧版本创建且仍指向本工具的链接。
    for legacy, targets in ((home / '.local/bin/cmd', (data / 'cmd', old_data / 'cmd')),
                            (home / '.local/bin/xcmd', (data / 'xcmd', old_data / 'xcmd'))):
        if legacy.is_symlink() and legacy.resolve() in tuple(target.resolve() for target in targets):
            legacy.unlink()
            print(f'已移除本工具的旧入口：{legacy}')
    if updated != original:
        if rc.exists():
            backup = rc.with_name(rc.name + '.cmd-tool.bak.' +
                                  datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
            shutil.copy2(rc, backup)
            print(f'Bash 配置备份：{backup}')
        rc.write_text(updated)

    print(f'配置文件：{config}')
    print(f'程序入口：{short_executable}（兼容入口：{executable}）')
    print('新终端自动生效；当前终端执行：')
    print(f'source {quoted}')


if __name__ == '__main__':
    try:
        if os.name == 'nt':
            raise ValueError('On Windows, use pipx install . and then xcmd --install-completion powershell --profile $PROFILE')
        install()
    except (OSError, UnicodeError, ValueError) as error:
        print(f'安装失败：{error}', file=sys.stderr)
        sys.exit(1)
