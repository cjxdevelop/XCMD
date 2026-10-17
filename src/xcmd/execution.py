"""Execute configured commands using Bash or PowerShell."""
import base64
import os
import shlex
import shutil
import subprocess


def powershell_executable():
    override = os.environ.get('XCMD_POWERSHELL')
    if override:
        return override
    for name in ('pwsh', 'powershell'):
        found = shutil.which(name)
        if found:
            return found
    raise ValueError('PowerShell not found; install PowerShell or set XCMD_POWERSHELL')


def command_line(command, arguments, shell):
    if not arguments:
        return command
    if shell == 'bash':
        suffix = shlex.join(arguments)
    else:
        suffix = ' '.join("'" + value.replace("'", "''") + "'" for value in arguments)
    return command + ' ' + suffix


def execution_argv(command, shell):
    if shell == 'bash':
        executable = shutil.which('bash')
        if not executable:
            raise ValueError('Bash not found')
        return [executable, '-c', command, 'xcmd']
    script = '''[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
$OutputEncoding = [Console]::OutputEncoding
$ErrorActionPreference = 'Stop'
$global:LASTEXITCODE = 0
try {
    & {
''' + command + '''
        $xcmdSucceeded = $?
        $xcmdExitCode = $LASTEXITCODE
        if (-not $xcmdSucceeded) {
            if ($xcmdExitCode -ne 0) { exit $xcmdExitCode }
            exit 1
        }
    }
    exit 0
} catch {
    [Console]::Error.WriteLine($_.ToString())
    exit 1
}
'''
    encoded = base64.b64encode(script.encode('utf-16-le')).decode('ascii')
    return [powershell_executable(), '-NoLogo', '-NoProfile', '-EncodedCommand', encoded]


def execute(command, shell):
    result = subprocess.call(execution_argv(command, shell))
    return 128 - result if result < 0 else result
