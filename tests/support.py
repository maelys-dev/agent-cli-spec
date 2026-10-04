# SPDX-License-Identifier: MPL-2.0
"""Run the real fixture in memory for mutation tests; keep subprocess tests separate."""
import contextlib
import importlib.util
import io
import os
import pathlib
import subprocess
import sys
import types
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "conformant.py"


class FixtureProgram:
    """The fixture in memory. Without a `command` the kit skips what needs a real process, the
    completion scripts driven in their shells; `shells=True` names one, at the cost of seconds."""

    def __init__(self, defect="", transform=None, shells=False, static=False):
        self.env = {"NO_COLOR": "1", "PAGER": "", "CONFORMANT_BREAK": defect,
                    "CONFORMANT_COMPLETION": "static" if static else ""}
        if shells:
            self.command = [sys.executable, str(FIXTURE)]
            self.timeout = 10
        self.failures = []
        self.transform = transform
        spec = importlib.util.spec_from_file_location("fixture", FIXTURE)
        self.fixture = importlib.util.module_from_spec(spec)
        with patch.dict(os.environ, self.env):
            spec.loader.exec_module(self.fixture)

    def run(self, *arguments, env=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        def pager(*args, **kwargs):
            result = subprocess.run(*args, **kwargs, capture_output=True)
            sys.stdout.write(result.stdout)
            sys.stderr.write(result.stderr)
            return result
        with patch.dict(os.environ, {**self.env, **(env or {})}), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr), \
                patch.object(self.fixture, "subprocess", types.SimpleNamespace(run=pager)):
            code = self.fixture.main(list(arguments))
        result = subprocess.CompletedProcess(arguments, code, stdout.getvalue(), stderr.getvalue())
        result.request_arguments = arguments
        return self.transform(arguments, result) if self.transform else result
