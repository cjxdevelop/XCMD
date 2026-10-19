# Run in the current PowerShell session, including through Invoke-Expression.
param(
    [string]$Package = 'https://github.com/cjxdevelop/XCMD/releases/download/v0.1.2/xcmd_tool-0.1.2-py3-none-any.whl'
)

# Keep helper variables and preference changes out of the caller's scope.
& {
    param($PackageSpec, $CurrentProfile)
    $ErrorActionPreference = 'Stop'
    $pipxCommand = Get-Command pipx -ErrorAction SilentlyContinue
    $pipxPrefix = @()
    if (-not $pipxCommand) {
        foreach ($name in @('py', 'python', 'python3')) {
            $candidate = Get-Command $name -ErrorAction SilentlyContinue
            if (-not $candidate) { continue }
            try {
                & $candidate -m pipx --version 2>$null | Out-Null
                if ($LASTEXITCODE -eq 0) {
                    $pipxCommand = $candidate
                    $pipxPrefix = @('-m', 'pipx')
                    break
                }
            } catch { }
        }
    }
    if (-not $pipxCommand) {
        throw 'xc: Python 3.10+ and pipx are required. Install pipx first with py -m pip install --user pipx.'
    }
    if (-not $CurrentProfile) { throw 'xc: the current PowerShell profile could not be determined.' }

    function Invoke-XcmdPipx {
        param([string[]]$Arguments)
        & $pipxCommand @pipxPrefix @Arguments
        if ($LASTEXITCODE -ne 0) { throw "xc: pipx $($Arguments[0]) failed (exit $LASTEXITCODE)." }
    }
    Invoke-XcmdPipx @('install', '--force', $PackageSpec)
    $pathHelp = (Invoke-XcmdPipx @('ensurepath', '--help')) -join "`n"
    if ($pathHelp.Contains('--prepend')) {
        Invoke-XcmdPipx @('ensurepath', '--prepend')
    } else {
        Invoke-XcmdPipx @('ensurepath')
    }
    $bin = ((Invoke-XcmdPipx @('environment', '--value', 'PIPX_BIN_DIR')) -join "`n").Trim()
    if (-not $bin) { throw 'xc: pipx returned an empty application directory.' }
    $launcherName = if ($env:OS -eq 'Windows_NT') { 'xc.exe' } else { 'xc' }
    $executable = Join-Path $bin $launcherName
    if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
        throw "xc: pipx did not expose an executable at $executable."
    }
    if (($env:PATH -split [IO.Path]::PathSeparator) -notcontains $bin) {
        $env:PATH = $bin + [IO.Path]::PathSeparator + $env:PATH
    }
    & $executable --init
    if ($LASTEXITCODE -ne 0) { throw 'xc: configuration initialization failed.' }
    & $executable --install-completion powershell --profile $CurrentProfile
    if ($LASTEXITCODE -ne 0) { throw 'xc: profile installation failed.' }
    $completion = & $executable --completion powershell
    if ($LASTEXITCODE -ne 0 -or -not $completion) { throw 'xc: completion generation failed.' }
    $completion -join "`n" | Invoke-Expression
    & $executable --version
    if ($LASTEXITCODE -ne 0) { throw 'xc: launcher verification failed.' }
    Write-Output 'xc: installation complete; Tab completion enabled in this terminal.'
    if ($env:OS -eq 'Windows_NT' -and (Get-ExecutionPolicy) -eq 'Restricted') {
        Write-Warning 'The current execution policy blocks profile scripts in future sessions. Ask your administrator which profile policy is permitted; xcmd has not changed the policy.'
    } else {
        Write-Output "Future PowerShell sessions load completion from: $CurrentProfile"
    }
} $Package $PROFILE
