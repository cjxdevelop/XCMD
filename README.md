# xcmd

[简体中文](README.zh-CN.md)

Run named shell commands from a plain text file, with dynamic completion.
Type `xcmd p`, press **Tab**, inspect the configured command and press Enter to run.
No runtime dependencies beyond Python and your shell.

```text
push-SystemUI -- adb push SystemUI.apk /system_ext/priv-app/SystemUI/SystemUI.apk
stop-system_server -- adb shell stop
```

## Supported platforms

| Platform | Execution shell | Completion |
| --- | --- | --- |
| Linux | Bash 4.4+ | Tab displays names and commands |
| Windows | PowerShell 5.1 or 7+ | Tab completes names; Ctrl+Space displays command details |

Python 3.10+ is required. Windows execution prefers `pwsh`, then falls back to
`powershell`. Windows `cmd.exe`, Zsh and Fish completion are outside this release.

## Install from source or a release archive

Clone [XCMD](https://github.com/cjxdevelop/XCMD), then open its directory. With [pipx](https://pipx.pypa.io/):

```console
git clone https://github.com/cjxdevelop/XCMD.git
cd XCMD
pipx install .
xcmd --init
```

You can also install directly with `pipx install git+https://github.com/cjxdevelop/XCMD.git`.

Or install into your own virtual environment with `python -m pip install .`.
Install a built wheel using `python -m pip install path/to/xcmd_tool-0.1.1-py3-none-any.whl`.
The distribution name is `xcmd-tool`; the command is `xcmd`.
This checkout does not assume a package has already been published to PyPI.

### Linux / Bash

```bash
xcmd --install-completion bash
# Enable it in the current terminal too:
eval "$(xcmd --completion bash)"
```

### Windows / PowerShell

```powershell
xcmd --install-completion powershell --profile "$PROFILE"
# Enable it in the current terminal too:
xcmd --completion powershell | Out-String | Invoke-Expression
```

Passing `$PROFILE` targets the profile for the terminal you are using.
Profile installation is idempotent and backs up modified files as `.xcmd.bak.*`.
It does not change your execution policy or global key bindings. If local policy
blocks your profile, configure it according to your environment before loading it.
PowerShell's standard Tab cycles matches; Ctrl+Space opens the completion menu.

## Configuration

```console
xcmd --config
xcmd --edit
```

The default config is `$XDG_CONFIG_HOME/xcmd/commands.conf` (normally
`~/.config/xcmd/commands.conf`) on Linux and `%APPDATA%\xcmd\commands.conf`
on Windows. Existing Linux `~/.config/cmd-tool/commands.conf` files are used when
no new-style config exists. `XCMD_CONFIG` overrides the location; the legacy
`CMD_TOOL_CONFIG` variable remains supported at lower priority.

Each line contains `name -- command`, with whitespace around `--`.
Blank lines and whole-line `#` comments are ignored. Names are case-sensitive
and contain letters, numbers, `_`, `.`, `-`; the first character must be a
letter, number or `_`. UTF-8, UTF-8 BOM and CRLF files are accepted.

```text
# Shared commands: this syntax works in both shells.
hello -- echo 'Hello from xcmd'
pull -- adb pull

[linux]
list-files -- ls -la
logs -- adb logcat | rg SystemUI

[windows]
list-files -- Get-ChildItem -Force
logs -- adb logcat | Select-String SystemUI
```

Unsectioned entries and `[all]` are shared. The matching platform section
overrides shared entries regardless of file order. Duplicate names in the same
section, invalid sections and malformed lines are rejected before execution.
Configuration is re-read for every command and completion.

Commands use the target shell's syntax. Bash-specific syntax does not become
portable merely because it appears in a shared section. PowerShell 5.1 does not
support PowerShell 7's `&&` operator; use a `[windows]` command appropriate to the
shell version you select. Set `XCMD_POWERSHELL` to a full executable path to select
one explicitly. Native-program argument passing follows that PowerShell version;
PowerShell 7 is recommended when empty arguments or embedded double quotes matter.

## Usage

```console
xcmd --list
xcmd --show push-SystemUI
xcmd push-SystemUI
xcmd pull /sdcard/example.txt ./example.txt
xcmd --help
```

Additional arguments are quoted as data and appended to the configured command.
For pipelines or compound commands, they are appended to the final part; put
complex argument placement directly in the configuration.

Commands run in a child shell with the current working directory, environment
and standard input/output. `cd` and `export`/environment assignments do not change
the parent terminal. Relative paths are resolved from the directory where you
invoke `xcmd`. The actual command is printed to stderr before execution; its exit
status is returned. Completion only reads config and never runs its commands.
`--init` creates a sample config without overwriting an existing file.
`--edit` uses `VISUAL`, `EDITOR`, then `nano` on Linux or Notepad on Windows.
`--shell bash|powershell` before a name overrides the default execution shell.

## Existing Linux source installations

The root `xcmd`, `completion.bash` and `install.py` keep the original source
installation working. `python3 install.py` installs the package source under
`~/bin/cmd-tool`, links `~/bin/xcmd`, and retains existing private configuration.
This compatibility installer is Linux-only; use the Python package on Windows.
Keep this directory in place while using its source-checkout installation.

## Develop, test and build

```console
python -m pip install -e .
python -m unittest discover -s tests -v
python -m pip install build
python -m build
python scripts/check_wheel.py dist
```

CI covers Linux and Windows, including Windows PowerShell 5.1 and PowerShell 7.
Tests that need an unavailable shell are explicitly skipped. See
[CONTRIBUTING.md](CONTRIBUTING.md) for details.

## Release a version

Update `pyproject.toml` and `src/xcmd/__init__.py` to the same version, commit the
change, then push a matching tag (for example, `git push origin v0.1.1`). The tag
workflow waits for all Windows/Linux checks, builds and verifies the package,
then publishes a GitHub Release with the wheel, source distribution and SHA256
checksums. The release remains a draft until every asset has been uploaded.

## Uninstall

Remove the marked xcmd completion block from your shell profile, then run
`pipx uninstall xcmd-tool` (or uninstall with the package manager you used).
Your command configuration is retained. Reload or reopen the terminal.
For legacy source installations, also remove the managed `~/bin/xcmd` link.

## License

[Apache-2.0](LICENSE).
