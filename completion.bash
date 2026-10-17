# Compatibility loader for a source checkout. Use source, not bash.
[[ -n ${BASH_VERSION:-} ]] || return 0
_xcmd_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
_xcmd_script=$(python3 "$_xcmd_root/xcmd" --completion bash) || return 1
eval "$_xcmd_script"
_xcmd_status=$?
unset _xcmd_root _xcmd_script
return "$_xcmd_status"
