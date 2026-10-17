# xcmd

[English](README.md)

把常用命令写进文本文件，通过 `xcmd 名称` 执行。修改配置立即生效，支持名称补全和完整命令提示。

## 平台与安装

需要 Python 3.10+。Linux 使用 Bash 4.4+；Windows 支持 PowerShell 5.1 和 7+，优先使用 `pwsh`，不存在时使用 `powershell`。

下载源码压缩包或克隆本仓库，进入项目目录，使用已安装的 pipx：

```console
git clone https://github.com/cjxdevelop/XCMD.git
cd XCMD
pipx install .
xcmd --init
```

也可直接运行 `pipx install git+https://github.com/cjxdevelop/XCMD.git`。

也可在虚拟环境中运行 `python -m pip install .`，或安装构建好的 wheel。发行包名称是 `xcmd-tool`，命令名称是 `xcmd`；当前文档使用本地源码安装，不假定已经发布到 PyPI。

Linux/Bash：

```bash
xcmd --install-completion bash
eval "$(xcmd --completion bash)"
```

Windows/PowerShell：

```powershell
xcmd --install-completion powershell --profile "$PROFILE"
xcmd --completion powershell | Out-String | Invoke-Expression
```

第一行配置后续终端，第二行让当前终端生效。安装前备份 profile，可重复执行，保留原设置和文件编码；不修改执行策略或全局按键绑定。

Bash 中输入 `xcmd p` 按 Tab 显示完整命令并补全；PowerShell 的默认 Tab 轮换补全名称，Ctrl+Space 显示带完整命令的候选菜单。本版本不提供传统 cmd.exe、Zsh 或 Fish 的补全。

## 配置

```console
xcmd --config
xcmd --edit
```

默认配置：Linux 为 `~/.config/xcmd/commands.conf`，遵循 `XDG_CONFIG_HOME`；Windows 为 `%APPDATA%\xcmd\commands.conf`。Linux 没有新配置时会沿用原 `~/.config/cmd-tool/commands.conf`。环境变量 `XCMD_CONFIG` 可指定文件，也兼容较低优先级的 `CMD_TOOL_CONFIG`。

```text
# 名称 -- 命令；-- 两侧需要空白
hello -- echo 'Hello from xcmd'
push-SystemUI -- adb push ZuiSystemUI.apk /system_ext/priv-app/ZuiSystemUI/ZuiSystemUI.apk
stop-system_server -- adb shell stop

[linux]
list-files -- ls -la
logs -- adb logcat | rg SystemUI

[windows]
list-files -- Get-ChildItem -Force
logs -- adb logcat | Select-String SystemUI
```

空行与整行注释会忽略。名称区分大小写，可以包含字母、数字、下划线、点和连字符，首字符只能是字母、数字或下划线。接受 UTF-8、UTF-8 BOM 和 CRLF 文件。

没有分段的命令和 `[all]` 都是公共命令；对应系统的段覆盖公共同名项，与段落顺序无关。同段重复名称、错误段名和错误格式会在执行前报错。每次执行和补全都重新读取配置。

右侧按当前系统的 Shell 语法执行；不同语法放在各自平台段。PowerShell 5.1 不支持 `&&`，该写法需要 PowerShell 7。可通过 `XCMD_POWERSHELL` 指定解释器路径。调用原生程序时，空参数和内嵌双引号的处理遵循对应 PowerShell 版本，复杂参数建议使用 PowerShell 7。

## 使用与行为

```console
xcmd --list
xcmd --show push-SystemUI
xcmd push-SystemUI
xcmd --help
```

支持追加参数，例如配置 `pull -- adb pull` 后，运行 `xcmd pull /sdcard/example.txt ./example.txt`。追加参数作为数据引用后附到配置末尾；管道或组合命令需要在中间放参数时，直接写入配置。

相对路径以输入命令时的当前目录为准。执行前向 stderr 打印完整命令，标准输入输出、环境和当前目录会传给子 Shell，退出码返回给调用方。`cd`、`export` 等不会改变父终端。补全只读取配置，不运行配置中的命令。`--init` 不覆盖已有文件；`--edit` 优先使用 VISUAL、EDITOR，再使用 nano 或记事本。

可在名称前加 `--shell bash` 或 `--shell powershell` 显式选择解释器。

## 原有 Linux 安装

仍可执行 `python3 install.py`，把源码运行文件放到 `~/bin/cmd-tool/`、入口放到 `~/bin/xcmd`，并保留已有命令配置。项目根目录的 `xcmd` 和 `completion.bash` 用于兼容之前的安装方式，使用期间请保留该目录。Windows 使用标准 Python 包安装。

## 测试与构建

```console
python -m pip install -e .
python -m unittest discover -s tests -v
python -m pip install build
python -m build
python scripts/check_wheel.py dist
```

仓库包含 Windows/Linux CI，Windows 同时验证 PowerShell 5.1 和 7；本机缺少对应 Shell 时，相关测试会明确跳过。贡献方式见 [CONTRIBUTING.md](CONTRIBUTING.md)。

卸载时移除 profile 中带标记的 xcmd 补全块，再使用原包管理方式卸载。配置文件默认保留。Apache-2.0 许可证见 [LICENSE](LICENSE)。
