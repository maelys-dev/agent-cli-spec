# SPDX-License-Identifier: MPL-2.0
"""The fixture implements a pager; exercise its actual terminal boundaries."""
import json
import os
import pathlib
import select
import shlex
import subprocess
import sys
import tempfile
import unittest

from support import FIXTURE

if os.name == "posix":
    import pty


@unittest.skipUnless(os.name == "posix", "pseudo-terminals require POSIX")
class TerminalTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="agent cli terminal ")
        self.addCleanup(self.directory.cleanup)
        root = pathlib.Path(self.directory.name)
        self.marker = root / "pager-started.json"
        pager = root / "pager.py"
        pager.write_text("import json, os, pathlib, sys\n"
                         + f"pathlib.Path({str(self.marker)!r}).write_text(json.dumps(dict(LESS=os.environ.get('LESS'))))\n"
                         + "sys.stdout.write(sys.stdin.read())\n", encoding="utf-8")
        self.pager = shlex.join([sys.executable, str(pager)])
        less = root / "less"
        less.write_text("#!/bin/sh\nexec " + self.pager + ' "$@"\n', encoding="utf-8")
        less.chmod(0o755)
        self.env = {**os.environ, "NO_COLOR": "1", "TERM": "xterm", "PAGER": self.pager,
                    "PATH": str(root) + os.pathsep + os.environ.get("PATH", ""), "CONFORMANT_BREAK": ""}
        self.env.pop("LESS", None)

    def terminal(self, *arguments, env=None, stream="stdout"):
        self.marker.unlink(missing_ok=True)
        environment = {**self.env, **(env or {})}
        environment = {key: value for key, value in environment.items() if value is not None}
        master, slave = pty.openpty()
        try:
            with subprocess.Popen([sys.executable, str(FIXTURE), *arguments], stdin=subprocess.DEVNULL,
                                  stdout=slave if stream == "stdout" else subprocess.PIPE,
                                  stderr=slave if stream == "stderr" else subprocess.PIPE,
                                  env=environment, text=True) as process:
                try:
                    stdout, stderr = process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate()
                    raise
            # Keep our slave open until the master is drained: macOS can discard
            # queued bytes when the final slave closes.
            chunks = []
            while select.select([master], [], [], 0.05)[0]:
                chunks.append(os.read(master, 65536))
            rendered = b"".join(chunks).decode("utf-8").replace("\r\n", "\n")
            return process.returncode, rendered if stream == "stdout" else stdout, rendered if stream == "stderr" else stderr
        finally:
            os.close(slave)
            os.close(master)

    def test_pager_matrix(self):
        for name, flags, environment, expected in (
            ("auto", (), {}, True),
            ("always", ("--pager=always",), {}, True),
            ("never", ("--pager=never",), {}, False),
            ("non-interactive", ("--non-interactive", "--pager=always"), {}, False),
            ("non-interactive=false", ("--non-interactive=false", "--pager=always"), {}, True),
            ("empty PAGER", (), {"PAGER": ""}, False),
            ("whitespace PAGER", (), {"PAGER": "   "}, False),
            ("invalid PAGER", (), {"PAGER": "'unterminated"}, False),
            ("missing pager", (), {"PAGER": "/nonexistent/agent-cli-pager"}, False),
        ):
            with self.subTest(case=name):
                code, stdout, stderr = self.terminal("version", *flags, env=environment)
                self.assertEqual((code, stdout, stderr), (0, "conformant 1.0.0\n", ""))
                self.assertEqual(self.marker.exists(), expected)

    def test_default_less_and_existing_less_options(self):
        for value, expected in ((None, "FRX"), ("custom", "custom"), ("", "")):
            with self.subTest(LESS=value):
                code, stdout, stderr = self.terminal("version", env={"PAGER": None, "LESS": value})
                self.assertEqual((code, stdout, stderr), (0, "conformant 1.0.0\n", ""))
                self.assertEqual(json.loads(self.marker.read_text())["LESS"], expected)

    def test_machine_modes_never_page_on_a_terminal(self):
        for arguments in (("version", "--json", "--pager=always"),
                          ("__complete", "--format=jsonl", "--pager=always", "--", "")):
            code, stdout, stderr = self.terminal(*arguments)
            self.assertEqual(code, 0)
            self.assertEqual(stderr, "")
            self.assertFalse(self.marker.exists())
            if "--json" in arguments:
                self.assertTrue(json.loads(stdout)["ok"])
            else:
                self.assertTrue(all("word" in json.loads(line) for line in stdout.splitlines()))

    def test_progress_uses_stderr_terminal_and_machine_mode_suppresses_it(self):
        for flags, present in (((), True), (("--progress=never",), False),
                               (("--json", "--progress=always", "--verbose"), False)):
            code, stdout, stderr = self.terminal("version", *flags, stream="stderr")
            self.assertEqual(code, 0)
            self.assertEqual("working" in stderr, present)
            self.assertNotIn("working", stdout)
