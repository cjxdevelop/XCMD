# Contributing

Use Python 3.10 or newer. Create a virtual environment, then install the checkout:

```console
python -m pip install -e .
python -m unittest discover -s tests -v
```

Tests only use temporary command files and profiles. Never execute the Android
examples as part of automated tests. Bash integration is tested on Linux;
PowerShell tests run when `pwsh` or `powershell` is available. Set
`XCMD_POWERSHELL` to an executable path to choose a particular version.

On Windows, run the suite with both PowerShell 7 and Windows PowerShell 5.1
when changing command execution or completion. Linux-only legacy installer
tests are explicitly skipped on Windows.

Build and verify the distribution:

```console
python -m pip install build
python -m build
python scripts/check_wheel.py dist
```

The wheel smoke test uses pip 22.3+ to install into a separate, pip-free virtual
environment. It does not need the operating system's ensurepip component.

Keep configuration parsing independent of execution. Completion must never
execute configured commands. Test parameters containing spaces, quotes,
Unicode and shell metacharacters when changing argument handling.

For bug reports, include the OS, Python and shell versions, the smallest
reproducible configuration, the command entered and the actual output.
Remove private command contents and paths before posting.

Please include a focused test for behavior changes. Contributions are licensed
under the project's Apache-2.0 license.
