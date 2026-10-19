#!/usr/bin/env bash
# Source this file so PATH and completion take effect in the calling Bash.
if [[ -z ${BASH_VERSION:-} ]]; then
    printf 'xc: run this installer in Bash.\n' >&2
    return 1 2>/dev/null || exit 1
fi
if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
    printf 'xc: use source install.sh [WHEEL] to enable this terminal.\n' >&2
    exit 1
fi

__xcmd_install() {
    local package=${1:-https://github.com/cjxdevelop/XCMD/releases/download/v0.1.2/xcmd_tool-0.1.2-py3-none-any.whl}
    local bin executable completion path_help
    local -a pipx_command
    if command -v pipx >/dev/null 2>&1; then
        pipx_command=(pipx)
    elif command -v python3 >/dev/null 2>&1 && python3 -m pipx --version >/dev/null 2>&1; then
        pipx_command=(python3 -m pipx)
    else
        printf 'xc: Python 3.10+ and pipx are required. On Ubuntu, install pipx with your package manager first.\n' >&2
        return 1
    fi
    "${pipx_command[@]}" install --force "$package" || return $?
    path_help=$("${pipx_command[@]}" ensurepath --help) || return $?
    if [[ $path_help == *--prepend* ]]; then
        "${pipx_command[@]}" ensurepath --prepend || return $?
    else
        "${pipx_command[@]}" ensurepath || return $?
    fi
    bin=$("${pipx_command[@]}" environment --value PIPX_BIN_DIR) || return $?
    executable=$bin/xc
    if [[ -z $bin || ! -x $executable ]]; then
        printf 'xc: pipx did not expose an executable at %s\n' "$executable" >&2
        return 1
    fi
    case :$PATH: in
        *:"$bin":*) ;;
        *) export PATH="$bin:$PATH" ;;
    esac
    "$executable" --init || return $?
    "$executable" --install-completion bash || return $?
    completion=$("$executable" --completion bash) || return $?
    [[ -n $completion ]] || return 1
    eval "$completion" || return $?
    "$executable" --version || return $?
    printf 'xc: installation complete; Tab completion enabled in this terminal and future Bash sessions.\n'
}

if __xcmd_install "$@"; then
    unset -f __xcmd_install
else
    unset -f __xcmd_install
    return 1
fi
