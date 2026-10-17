"""Run the suite and expose failures as GitHub check annotations."""
import os
from pathlib import Path
import sys
import unittest


def annotation(value):
    return value.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    suite = unittest.defaultTestLoader.discover(str(root / 'tests'))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if os.environ.get('GITHUB_ACTIONS'):
        for test, traceback in result.failures + result.errors:
            print(f'::error::{annotation(str(test) + chr(10) + traceback)}', flush=True)
    raise SystemExit(0 if result.wasSuccessful() else 1)
