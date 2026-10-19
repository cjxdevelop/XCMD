# xcmd

[English](README.md)

把常用命令写进文本文件，通过 `xc 名称` 执行。修改配置立即生效，支持名称补全和完整命令提示。

## 平台与安装

需要 Python 3.10+。Linux 使用 Bash 4.4+；Windows 支持 PowerShell 5.1 和 7+，优先使用 `pwsh`，不存在时使用 `powershell`。

推荐使用一行安装入口，前提是已安装 Python 和 [pipx](https://pipx.pypa.io/stable/installation/)。

Ubuntu / Bash：

```bash
source <(curl -fsSL https://github.com/cjxdevelop/XCMD/releases/download/v0.1.2/install.sh)
```

Windows / PowerShell 5.1 或 7+：

```powershell
irm https://github.com/cjxdevelop/XCMD/releases/download/v0.1.2/install.ps1 | iex
```

脚本会通过 pipx 安装或重新安装此版本，配置 PATH，保留已有命令配置，并让当前窗口和后续终端的补全生效。无需另输补全命令或重开终端。安装后运行 `xc --list`，使用已有命令的前缀按 Tab；默认配置含 `hello` 和 `list-files`。PowerShell 执行策略保持不变；若策略禁止 profile，后续终端的自动加载仍受该策略限制。

也可以先查看仓库脚本或下载 Release 附件，再运行 `source ./install.sh` 或 `. ./install.ps1`。本地 wheel 可使用 `source ./install.sh /path/to/package.whl` 或 `. ./install.ps1 -Package C:\path\to\package.whl`。

手动安装方式如下；使用一行安装入口时不必重复执行这些步骤。

下载源码压缩包或克隆本仓库，进入项目目录，使用已安装的 pipx：

```console
git clone https://github.com/cjxdevelop/XCMD.git
cd XCMD
pipx install .
pipx ensurepath
```

执行 `pipx ensurepath` 后，关闭并重新打开终端，再运行 `xc --init`。

也可直接运行 `pipx install git+https://github.com/cjxdevelop/XCMD.git`。

也可在虚拟环境中运行 `python -m pip install .`，或安装构建好的 wheel。发行包名称是 `xcmd-tool`，命令名称是 `xc`，保留 `xcmd` 兼容入口，配置路径与环境变量继续沿用；当前文档使用本地源码安装，不假定已经发布到 PyPI。

Linux/Bash：

```bash
xc --install-completion bash
eval "$(xc --completion bash)"
```

Windows/PowerShell：

如果通过 pipx 安装后找不到 `xc`，运行 `py -m pipx ensurepath`，关闭终端应用后重新打开，再执行 `Get-Command xc` 和 `xc --version`。

如果通过 pip 安装 wheel，先用安装时的同一个 Python 执行 `py -m xcmd --version`（按实际情况将 `py` 替换为安装时的 Python 命令）。若模块可以运行而 `xc --version` 找不到，将安装生成的 `xc.exe` 所在目录加入用户环境变量 `Path`，然后重开终端；pip 的脚本目录警告会显示该路径。若安装在虚拟环境中，需要先激活该环境。也可用 `py -m pip show -f xcmd-tool` 查看安装文件位置。若模块也提示 `No module named xcmd`，需核对安装使用的 Python 或 pipx 环境。

```powershell
xc --install-completion powershell --profile "$PROFILE"
xc --completion powershell | Out-String | Invoke-Expression
```

第一行配置后续终端，第二行让当前终端生效。安装前备份 profile，可重复执行，保留原设置和文件编码；不修改执行策略或全局按键绑定。

Bash 中输入 `xc p` 按 Tab 显示完整命令并补全；PowerShell 的默认 Tab 轮换补全名称，Ctrl+Space 显示带完整命令的候选菜单。本版本不提供传统 cmd.exe、Zsh 或 Fish 的补全。

## 配置

```console
xc --config
xc --edit
```

默认配置：Linux 为 `~/.config/xcmd/commands.conf`，遵循 `XDG_CONFIG_HOME`；Windows 为 `%APPDATA%\xcmd\commands.conf`。Linux 没有新配置时会沿用原 `~/.config/cmd-tool/commands.conf`。环境变量 `XCMD_CONFIG` 可指定文件，也兼容较低优先级的 `CMD_TOOL_CONFIG`。

```text
# 名称 -- 命令；-- 两侧需要空白
hello -- echo 'Hello from xcmd'
push-SystemUI -- adb push SystemUI.apk /system_ext/priv-app/SystemUI/SystemUI.apk
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
xc --list
xc --show push-SystemUI
xc push-SystemUI
xc --help
```

支持追加参数，例如配置 `pull -- adb pull` 后，运行 `xc pull /sdcard/example.txt ./example.txt`。追加参数作为数据引用后附到配置末尾；管道或组合命令需要在中间放参数时，直接写入配置。

相对路径以输入命令时的当前目录为准。执行前向 stderr 打印完整命令，标准输入输出、环境和当前目录会传给子 Shell，退出码返回给调用方。`cd`、`export` 等不会改变父终端。补全只读取配置，不运行配置中的命令。`--init` 不覆盖已有文件；`--edit` 优先使用 VISUAL、EDITOR，再使用 nano 或记事本。

可在名称前加 `--shell bash` 或 `--shell powershell` 显式选择解释器。

## 原有 Linux 安装

仍可执行 `python3 install.py`，把源码运行文件放到 `~/bin/cmd-tool/`、入口放到 `~/bin/xc`（保留 `~/bin/xcmd` 兼容入口），并保留已有命令配置。项目根目录的 `xc` 和 `completion.bash` 用于兼容之前的安装方式，使用期间请保留该目录。Windows 使用标准 Python 包安装。

## 测试与构建

```console
python -m pip install -e .
python -m unittest discover -s tests -v
python -m pip install build
python -m build
python scripts/check_wheel.py dist
```

仓库包含 Windows/Linux CI，Windows 同时验证 PowerShell 5.1 和 7；本机缺少对应 Shell 时，相关测试会明确跳过。贡献方式见 [CONTRIBUTING.md](CONTRIBUTING.md)。

发布新版本时，将 `pyproject.toml` 与 `src/xcmd/__init__.py` 的版本保持一致，提交后创建并推送相应的 `v` 标签。工作流会等待 Windows/Linux 全部检查通过，构建并验证安装包，再发布附有 wheel、源码包和 SHA256 校验文件的 GitHub Release；全部附件上传成功后才公开 Release。

卸载时移除 profile 中带标记的 xcmd 补全块，再使用原包管理方式卸载。配置文件默认保留。Apache-2.0 许可证见 [LICENSE](LICENSE)。
