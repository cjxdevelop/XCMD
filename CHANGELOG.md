# Changelog

## 0.1.2

- Shorten the command to `xc`, retaining `xcmd` as a compatibility entry.

- Add one-command installation for Ubuntu/Bash and Windows/PowerShell.
- Configure PATH, preserve existing commands and enable completion immediately.
- Verify actual pipx installation and repeat installation in Windows/Linux CI.
- Include version-pinned installer scripts and their SHA256 checksums in releases.

## 0.1.1

- Use standard AOSP SystemUI names in all documentation examples.

## 0.1.0

- Package the original Linux helper as a Python CLI with no runtime dependencies.
- Support Bash on Linux and PowerShell 5.1/7+ on Windows.
- Add dynamic completion, command tooltips and reversible profile installation.
- Support shared and platform-specific commands in one text file.
- Preserve legacy Linux configuration and source-checkout entry points.
- Add Windows/Linux CI, source distributions and wheels.
