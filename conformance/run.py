#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0
"""Conformance of a program to agent-cli/v2, checked from the outside.

    conformance/run.py PROGRAM [ARG...] [--report FILE] [--json]

PROGRAM is the executable (or a command line whose first word is; pass
`node dist/cli.js` as two arguments). The kit drives it through describe,
version, help, the failures the contract prescribes, the rendering options
and the completion, validates every answer against the schemas next to this
file, and prints one line per check. Exit 0 when every check passes, 1
otherwise, 2 when the program could not be run at all. Nothing is written
by the program: only read commands and refused invocations are used.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from validate import validate  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
SCHEMAS = {name: json.loads((HERE.parent / "schemas" / f"{name}.json").read_text(encoding="utf-8"))
           for name in ("describe", "envelope", "version", "records")}
STABLE_CODES = {"INVALID_COMMAND", "VALIDATION_FAILED", "PRECONDITION_FAILED", "POLICY_FAILED", "ACCESS_DENIED",
                "NOT_FOUND", "IO_FAILED", "PROCESS_FAILED", "PROTOCOL_FAILED", "UNSUPPORTED", "UNEXPECTED"}
GLOBAL_OPTIONS = {
    "--format": {"name": "VALUE", "type": "choice", "choices": ["text", "json", "jsonl"]},
    "--json": None, "--compact": None, "--pretty": None, "--non-interactive": None, "--verbose": None,
    "--progress": {"name": "VALUE", "type": "choice", "choices": ["auto", "always", "never"]},
    "--pager": {"name": "VALUE", "type": "choice", "choices": ["auto", "always", "never"]},
    "--color": {"name": "VALUE", "type": "choice", "choices": ["auto", "always", "never"]},
    "--help": None,
}
BUILT_INS = {"help": ["help"], "version": ["version"], "describe": ["describe"], "completion": ["completion"],
             "complete.candidates": ["__complete"]}
EXIT_CODES = {"0": "command completed", "1": "execution failed", "2": "valid report with violations"}


class Program:
    def __init__(self, command: list[str]) -> None:
        self.command = command
        self.env = {**os.environ, "NO_COLOR": "1"}
        self.env.pop("MAELYS_CLI_FORMAT", None)

    def run(self, *arguments: str, env: dict | None = None) -> subprocess.CompletedProcess:
        return subprocess.run([*self.command, *arguments], env={**self.env, **(env or {})}, check=False, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)


class Report:
    def __init__(self) -> None:
        self.checks: list[dict] = []

    def add(self, name: str, passed: bool, detail: str = "") -> bool:
        self.checks.append({"name": name, "passed": passed, "detail": detail})
        return passed

    @property
    def passed(self) -> bool:
        return all(check["passed"] for check in self.checks)


def issues_text(issues: list) -> str:
    return "; ".join(map(repr, issues[:6])) + (" ..." if len(issues) > 6 else "")


def envelope(report: Report, name: str, completed: subprocess.CompletedProcess, expect_ok: bool) -> dict | None:
    """Parse and validate an envelope; on failure, stdout must be empty."""
    stream, other = (completed.stdout, completed.stderr) if expect_ok else (completed.stderr, completed.stdout)
    try:
        body = json.loads(stream)
    except json.JSONDecodeError:
        report.add(name, False, f"no JSON envelope on {'stdout' if expect_ok else 'stderr'}: {stream[:120]!r}")
        return None
    issues = validate(body, SCHEMAS["envelope"])
    if issues:
        return None if not report.add(name, False, issues_text(issues)) else body
    if body["ok"] != expect_ok:
        report.add(name, False, f"ok is {body['ok']}")
        return None
    if body["exitCode"] != completed.returncode:
        report.add(name, False, f"envelope says exit {body['exitCode']}, process exited {completed.returncode}")
        return None
    if other.strip():
        report.add(name, False, f"the other stream is not empty: {other[:120]!r}")
        return None
    return body


def check_failure(report: Report, name: str, completed: subprocess.CompletedProcess, code: str) -> None:
    if completed.returncode != 1:
        report.add(name, False, f"exit {completed.returncode}, expected 1")
        return
    body = envelope(report, name, completed, expect_ok=False)
    if body is None:
        return
    got = body["error"]["code"]
    report.add(name, got == code, "" if got == code else f"code {got}, expected {code}")


def hidden_option_invocation(item: dict) -> list[str] | None:
    """The words that pass a hidden option with a valid value, or None when the kit cannot choose one."""
    long = item.get("long")
    argument = item.get("argument")
    if not argument:
        return [long]
    kind = argument.get("type")
    if argument.get("choices"):
        return [f"{long}={argument['choices'][0]}"]
    if kind in ("string", "path"):
        return [f"{long}=x"]
    if kind in ("integer", "unsigned"):
        return [f"{long}={argument.get('minimum', 1)}"]
    return None


def check_hidden_options(report: Report, program: Program, command: dict) -> None:
    """A hidden option is listed by describe, never offered to humans, and accepted."""
    identifier = command["id"]
    options = command.get("input", {}).get("options", [])
    operands = command.get("input", {}).get("operands", [])
    hidden = [item for item in options if item.get("hidden") is True]
    if not hidden:
        return
    for item in hidden:
        long = item.get("long")
        report.add(f"{identifier}: hidden option {long} is absent from usage and input.synopsis",
                   long not in str(command.get("usage", "")) and long not in str(command.get("input", {}).get("synopsis", "")))
        help_one = program.run("help", identifier, "--format", "json", "--non-interactive")
        help_body = envelope(report, f"{identifier}: help {identifier} envelope", help_one, expect_ok=True)
        if help_body is not None:
            report.add(f"{identifier}: hidden option {long} is absent from the help text",
                       long not in str(help_body["data"].get("text", "")))
    complete = program.run("__complete", "--format", "json", "--non-interactive", "--", *command.get("pattern", []), "--")
    complete_body = envelope(report, f"{identifier}: __complete after the pattern", complete, expect_ok=True)
    if complete_body is not None:
        offered = {record.get("word") for record in complete_body["data"].get("records", [])}
        for item in hidden:
            report.add(f"{identifier}: hidden option {item.get('long')} is not a completion candidate",
                       item.get("long") not in offered, f"offered {sorted(offered)}")
        visible = {item.get("long") for item in options if not item.get("hidden")}
        if visible:
            report.add(f"{identifier}: __complete offers a visible option where it hides the hidden ones",
                       bool(visible & offered), f"offered {sorted(offered)}, visible {sorted(visible)}")
    if command.get("effect") != "read" or any(item.get("required") for item in options) \
            or any(item.get("required") for item in operands):
        return
    for item in hidden:
        words = hidden_option_invocation(item)
        if words is None or item.get("requires"):
            continue
        accepted = program.run(*command.get("pattern", []), *words, "--format", "json", "--non-interactive")
        code = ""
        if accepted.returncode != 0:
            try:
                code = json.loads(accepted.stderr or "{}").get("error", {}).get("code", "")
            except json.JSONDecodeError:
                code = accepted.stderr[:80]
        report.add(f"{identifier}: hidden option {item.get('long')} is accepted",
                   accepted.returncode == 0 or code not in ("", "VALIDATION_FAILED"), f"exit {accepted.returncode} {code}")


def trunk_shape(item: dict, expected: dict | None) -> bool:
    """An option has a trunk option's shape: a flag, or the same value type and choices; never repeatable."""
    if item.get("repeatable") is not False:
        return False
    argument = item.get("argument")
    if expected is None:
        return argument is None
    return isinstance(argument, dict) and argument.get("type") == expected["type"] \
        and argument.get("choices") == expected["choices"]


def run_kit(program: Program) -> Report:
    report = Report()
    # ---- describe: the catalog, the summary, each command ----
    catalog_run = program.run("describe", "--format", "json", "--non-interactive")
    if catalog_run.returncode != 0 and not catalog_run.stdout:
        report.add("describe answers", False, f"exit {catalog_run.returncode}: {catalog_run.stderr[:200]!r}")
        return report
    body = envelope(report, "describe envelope", catalog_run, expect_ok=True)
    if body is None:
        return report
    catalog = body["data"]
    issues = validate(catalog, SCHEMAS["describe"])
    report.add("describe catalog matches schemas/describe.json", not issues, issues_text(issues))
    if issues and not isinstance(catalog.get("commands"), list):
        return report
    commands = [command for command in catalog.get("commands", []) if isinstance(command, dict) and "id" in command]
    by_id = {command["id"]: command for command in commands}
    report.add("describe kind is catalog", catalog.get("kind") == "catalog", f"kind {catalog.get('kind')!r}")
    report.add("command identifiers are unique", len(by_id) == len(commands))
    for identifier, pattern in BUILT_INS.items():
        present = identifier in by_id
        report.add(f"built-in {identifier} is in the catalog", present)
        if present:
            report.add(f"built-in {identifier} has pattern {' '.join(pattern)}", by_id[identifier].get("pattern") == pattern,
                       f"pattern {by_id[identifier].get('pattern')}")
    report.add("catalog lists the global options",
               {item.get("long") for item in catalog.get("globalOptions", [])} >= set(GLOBAL_OPTIONS),
               f"missing {set(GLOBAL_OPTIONS) - {item.get('long') for item in catalog.get('globalOptions', [])}}")
    for item in catalog.get("globalOptions", []):
        long = item.get("long")
        if long in GLOBAL_OPTIONS:
            report.add(f"global option {long} has the contract's shape", trunk_shape(item, GLOBAL_OPTIONS[long]),
                       f"argument {item.get('argument')}, repeatable {item.get('repeatable')!r}")
    global_longs = {item.get("long") for item in catalog.get("globalOptions", [])}
    for command in commands:
        identifier = command["id"]
        report.add(f"{identifier}: usage equals input.synopsis",
                   command.get("usage") == command.get("input", {}).get("synopsis"))
        report.add(f"{identifier}: exit codes are the contract's", command.get("exitCodes") == EXIT_CODES,
                   f"exitCodes {command.get('exitCodes')}")
        if isinstance(command.get("effect"), dict):
            report.add(f"{identifier}: transaction declares --apply",
                       any(item.get("long") == "--apply" for item in command.get("input", {}).get("options", [])))
        if "protocol" in command:
            report.add(f"{identifier}: a protocol belongs to a protocol-stream command",
                       command.get("outputMode") == "protocol-stream")
        clashes = [item.get("long") for item in command.get("input", {}).get("options", [])
                   if item.get("long") in GLOBAL_OPTIONS and not trunk_shape(item, GLOBAL_OPTIONS[item.get("long")])]
        report.add(f"{identifier}: no option borrows a trunk spelling with another shape", not clashes, f"clashes {clashes}")
        declared_options = {item.get("long") for item in command.get("input", {}).get("options", [])} | global_longs
        declared_operands = {item.get("name") for item in command.get("input", {}).get("operands", [])}
        unresolved = [entry for item in command.get("input", {}).get("options", [])
                      for entry in list(item.get("requires", [])) if entry not in declared_options]
        unresolved += [entry for item in command.get("input", {}).get("options", [])
                       for entry in list(item.get("conflictsWith", []))
                       if not (isinstance(entry, str) and
                               (entry in declared_options if entry.startswith("--") else entry in declared_operands))]
        report.add(f"{identifier}: requires and conflictsWith name declared options or operands", not unresolved,
                   f"unresolved {unresolved}")
        check_hidden_options(report, program, command)
        one = program.run("describe", identifier, "--format", "json", "--non-interactive")
        body = envelope(report, f"{identifier}: describe {identifier}", one, expect_ok=True)
        if body is not None:
            data = body["data"]
            report.add(f"{identifier}: describe {identifier} returns the catalog's descriptor",
                       data.get("kind") == "command" and data.get("commands") == [command]
                       and not any(key in data for key in ("globalOptions", "invariants", "output")),
                       "kind, descriptor or inventory members differ")
    summary = program.run("describe", "--summary", "--format", "json", "--compact", "--non-interactive")
    body = envelope(report, "describe --summary envelope", summary, expect_ok=True)
    if body is not None:
        data = body["data"]
        issues = validate(data, SCHEMAS["describe"])
        report.add("describe --summary matches schemas/describe.json", not issues, issues_text(issues))
        report.add("describe --summary kind is summary", data.get("kind") == "summary")
        report.add("describe --summary lists the same identifiers",
                   [command.get("id") for command in data.get("commands", [])] == list(by_id))
        report.add("describe --summary omits schemas and exit codes",
                   not any("outputSchema" in command or "exitCodes" in command for command in data.get("commands", [])))
        report.add("--compact renders one line", summary.stdout.count("\n") <= 1)
    describe_options = {item.get("long"): item for item in by_id.get("describe", {}).get("input", {}).get("options", [])}
    prefix_option = describe_options.get("--prefix", {})
    report.add("describe declares --prefix",
               prefix_option.get("argument", {}).get("type") == "string"
               and prefix_option.get("argument", {}).get("pattern")
               == r"^[a-z](?:[a-z0-9.-]*[a-z0-9-])?$"
               and "--summary" in prefix_option.get("requires", [])
               and "COMMAND_ID" in prefix_option.get("conflictsWith", []),
               f"option {prefix_option!r}")
    namespaces = [identifier.split(".", 1)[0] for identifier in by_id if "." in identifier]
    prefixes = namespaces or list(by_id)[:1]
    if prefixes:
        prefix = prefixes[0]
        expected = [identifier for identifier in by_id if identifier == prefix or identifier.startswith(prefix + ".")]
        filtered = program.run("describe", "--summary", "--prefix", prefix, "--format", "json", "--compact",
                               "--non-interactive")
        body = envelope(report, "describe filtered summary envelope", filtered, expect_ok=True)
        if body is not None:
            data = body["data"]
            issues = validate(data, SCHEMAS["describe"])
            report.add("describe filtered summary matches schemas/describe.json", not issues, issues_text(issues))
            report.add("describe filtered summary identifies its filter",
                       data.get("kind") == "summary"
                       and data.get("filter") == {"kind": "command-prefix", "value": prefix})
            report.add("describe filtered summary selects the namespace in catalog order",
                       [item.get("id") for item in data.get("commands", [])] == expected)
            report.add("describe filtered summary omits schemas and exit codes",
                       not any("outputSchema" in item or "exitCodes" in item for item in data.get("commands", [])))
            report.add("describe filtered summary omits catalog-only members",
                       not any(key in data for key in ("globalOptions", "invariants", "output")))
        check_failure(report, "describe --prefix of a known prefix without --summary fails with VALIDATION_FAILED",
                      program.run("describe", "--prefix", prefix, "--format", "json"), "VALIDATION_FAILED")
    check_failure(report, "describe --prefix of an unknown prefix without --summary still fails with VALIDATION_FAILED",
                  program.run("describe", "--prefix", "no-such-prefix", "--format", "json"), "VALIDATION_FAILED")
    check_failure(report, "describe rejects an invalid command prefix with VALIDATION_FAILED",
                  program.run("describe", "--summary", "--prefix", "no-such-prefix.", "--format", "json"),
                  "VALIDATION_FAILED")
    check_failure(report, "describe --prefix conflicts with COMMAND_ID",
                  program.run("describe", "help", "--summary", "--prefix", "help", "--format", "json"),
                  "VALIDATION_FAILED")
    check_failure(report, "describe of an unknown prefix fails with INVALID_COMMAND",
                  program.run("describe", "--summary", "--prefix", "no-such-prefix", "--format", "json"),
                  "INVALID_COMMAND")
    check_failure(report, "describe of an unknown identifier fails with INVALID_COMMAND",
                  program.run("describe", "no.such.command", "--format", "json"), "INVALID_COMMAND")
    # ---- version, help ----
    version = program.run("version", "--format", "json")
    body = envelope(report, "version envelope", version, expect_ok=True)
    if body is not None:
        issues = validate(body["data"], SCHEMAS["version"])
        report.add("version data matches schemas/version.json", not issues, issues_text(issues))
        report.add("version data agrees with describe",
                   body["data"].get("version") == catalog.get("version") and body["data"].get("program") == catalog.get("program"))
        alias = program.run("version", "--json")
        report.add("--json is the exact alias of --format json", alias.stdout == version.stdout)
        compact = program.run("version", "--json", "--compact")
        pretty_false = program.run("version", "--json", "--pretty=false")
        report.add("--pretty=false equals --compact", compact.stdout == pretty_false.stdout and compact.stdout.count("\n") <= 1)
        flag = program.run("--version", "--json")
        report.add("--version equals version", flag.stdout == version.stdout)
        verbose_json = program.run("version", "--verbose", "--json")
        if envelope(report, "--verbose writes nothing in JSON mode", verbose_json, expect_ok=True) is not None:
            report.add("--verbose leaves the JSON envelope unchanged", verbose_json.stdout == version.stdout,
                       f"stdout {verbose_json.stdout[:60]!r}")
        check_failure(report, "--verbose leaves a JSON failure envelope alone on stderr",
                      program.run("no-such-command", "--verbose", "--json"), "INVALID_COMMAND")
        jsonl_verbose = program.run("__complete", "--verbose", "--format", "jsonl", "--non-interactive", "--", "")
        report.add("--verbose writes nothing in jsonl mode",
                   jsonl_verbose.returncode == 0 and jsonl_verbose.stderr.strip() == "", jsonl_verbose.stderr[:80])
        plain_text = program.run("version", "--format", "text", "--non-interactive")
        verbose_text = program.run("version", "--verbose", "--format", "text", "--non-interactive")
        report.add("--verbose is accepted in text mode and leaves stdout unchanged",
                   verbose_text.returncode == 0 and verbose_text.stdout == plain_text.stdout,
                   f"exit {verbose_text.returncode}, stdout {verbose_text.stdout[:60]!r}")
        failure_prefix = f"{catalog.get('program')}: ["
        report.add("--verbose diagnostics are not failure renderings",
                   not any(line.startswith(failure_prefix) for line in verbose_text.stderr.splitlines()),
                   verbose_text.stderr[:120])
        progress_json = program.run("version", "--progress", "always", "--json")
        if envelope(report, "--progress always writes nothing in JSON mode", progress_json, expect_ok=True) is not None:
            report.add("--progress leaves the JSON envelope unchanged", progress_json.stdout == version.stdout,
                       f"stdout {progress_json.stdout[:60]!r}")
        progress_always = program.run("version", "--progress", "always", "--format", "text", "--non-interactive")
        report.add("--progress always is accepted in text mode and leaves stdout unchanged",
                   progress_always.returncode == 0 and progress_always.stdout == plain_text.stdout,
                   f"exit {progress_always.returncode}, stdout {progress_always.stdout[:60]!r}")
        report.add("--progress lines are not failure renderings",
                   not any(line.startswith(failure_prefix) for line in progress_always.stderr.splitlines()),
                   progress_always.stderr[:120])
        progress_never = program.run("version", "--progress=never", "--format", "text", "--non-interactive")
        report.add("--progress never is accepted and silent",
                   progress_never.returncode == 0 and progress_never.stdout == plain_text.stdout
                   and progress_never.stderr.strip() == "",
                   f"exit {progress_never.returncode}, stderr {progress_never.stderr[:80]!r}")
        check_failure(report, "--progress always leaves a JSON failure envelope alone on stderr",
                      program.run("no-such-command", "--progress", "always", "--json"), "INVALID_COMMAND")
        jsonl_progress = program.run("__complete", "--progress", "always", "--format", "jsonl", "--non-interactive", "--", "")
        report.add("--progress always writes nothing in jsonl mode",
                   jsonl_progress.returncode == 0 and jsonl_progress.stderr.strip() == "", jsonl_progress.stderr[:80])
        pager_json = program.run("version", "--pager", "always", "--json")
        if envelope(report, "--pager always pages nothing in JSON mode", pager_json, expect_ok=True) is not None:
            report.add("--pager leaves the JSON envelope unchanged", pager_json.stdout == version.stdout,
                       f"stdout {pager_json.stdout[:60]!r}")
        pager_never = program.run("version", "--pager=never", "--format", "text", "--non-interactive")
        report.add("--pager never is accepted and leaves stdout unchanged",
                   pager_never.returncode == 0 and pager_never.stdout == plain_text.stdout
                   and pager_never.stderr.strip() == "",
                   f"exit {pager_never.returncode}, stdout {pager_never.stdout[:60]!r}")
        pager_always = program.run("version", "--pager", "always", "--format", "text", env={"PAGER": "cat"})
        report.add("--pager always into a pipe is accepted and leaves stdout unchanged",
                   pager_always.returncode == 0 and pager_always.stdout == plain_text.stdout
                   and pager_always.stderr.strip() == "",
                   f"exit {pager_always.returncode}, stdout {pager_always.stdout[:60]!r}, stderr {pager_always.stderr[:60]!r}")
        verbose_false = program.run("version", "--verbose=false", "--format", "text", "--non-interactive")
        report.add("--verbose=false is accepted and silent",
                   verbose_false.returncode == 0 and verbose_false.stdout == plain_text.stdout
                   and verbose_false.stderr.strip() == "",
                   f"exit {verbose_false.returncode}, stderr {verbose_false.stderr[:80]!r}")
    help_run = program.run("help", "--format", "json")
    body = envelope(report, "help envelope", help_run, expect_ok=True)
    if body is not None:
        data = body["data"]
        report.add("help data has text and commands",
                   isinstance(data.get("text"), str) and bool(data.get("text")) and isinstance(data.get("commands"), list))
        report.add("--help equals help", program.run("--help", "--format", "json").stdout == help_run.stdout)
    for words in (("version",), ("help",), ("describe", "--summary")):
        text_run = program.run(*words, "--format", "text", "--non-interactive")
        report.add(f"text success of {' '.join(words)} is on stdout with stderr empty",
                   text_run.returncode == 0 and text_run.stdout.strip() != "" and text_run.stderr.strip() == "",
                   f"exit {text_run.returncode}, stdout {text_run.stdout[:40]!r}, stderr {text_run.stderr[:80]!r}")
    # ---- the failures the contract prescribes ----
    check_failure(report, "unknown command fails with INVALID_COMMAND", program.run("no-such-command", "--json"), "INVALID_COMMAND")
    check_failure(report, "unsupported option fails with VALIDATION_FAILED",
                  program.run("version", "--no-such-option", "--json"), "VALIDATION_FAILED")
    check_failure(report, "jsonl on a json-envelope command fails with VALIDATION_FAILED",
                  program.run("version", "--format", "jsonl"), "VALIDATION_FAILED")
    transactions = [command for command in commands if isinstance(command.get("effect"), dict)]
    if transactions:
        identifier = transactions[0]["id"]
        check_failure(report, f"{identifier}: --dry-run is refused with VALIDATION_FAILED",
                      program.run(*transactions[0]["pattern"], "--dry-run", "--json"), "VALIDATION_FAILED")
    text = program.run("no-such-command")
    report.add("text failure is 'PROGRAM: [CODE] message' on stderr",
               text.returncode == 1 and text.stdout == "" and text.stderr.startswith(f"{catalog.get('program')}: [INVALID_COMMAND] "),
               text.stderr[:120])
    unknown_body = json.loads(program.run("no-such-command", "--json").stderr or "{}")
    report.add("failure codes are stable codes", unknown_body.get("error", {}).get("code") in STABLE_CODES)
    # ---- completion ----
    for shell in ("bash", "zsh", "fish"):
        script = program.run("completion", shell)
        report.add(f"completion {shell} prints a script calling __complete",
                   script.returncode == 0 and "__complete" in script.stdout)
    candidates = program.run("__complete", "--format", "json", "--", "")
    body = envelope(report, "__complete envelope", candidates, expect_ok=True)
    if body is not None:
        issues = validate(body["data"], SCHEMAS["records"])
        report.add("__complete data matches schemas/records.json", not issues, issues_text(issues))
        words = {record.get("word") for record in body["data"].get("records", [])}
        visible = {command["pattern"][0] for command in commands if not command.get("hidden")}
        report.add("__complete offers the visible command words", visible <= words, f"missing {visible - words}")
        jsonl = program.run("__complete", "--format", "jsonl", "--", "")
        lines = [line for line in jsonl.stdout.splitlines() if line]
        report.add("__complete --format jsonl renders one record per line",
                   jsonl.returncode == 0 and len(lines) == body["data"].get("count") and all(json.loads(line) for line in lines))
        text_records = program.run("__complete", "--format", "text", "--non-interactive", "--", "")
        text_lines = text_records.stdout.splitlines()
        report.add("__complete --format text into a pipe renders one plain line per record, no header",
                   text_records.returncode == 0 and len(text_lines) == body["data"].get("count"),
                   f"{len(text_lines)} lines for count {body['data'].get('count')}: {text_records.stdout[:80]!r}")
    return report


def main(argv: list[str]) -> int:
    as_json = "--json" in argv
    argv = [argument for argument in argv if argument != "--json"]
    report_path = None
    if "--report" in argv:
        index = argv.index("--report")
        report_path = pathlib.Path(argv[index + 1])
        del argv[index:index + 2]
    if not argv:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    program = Program(argv)
    try:
        probe = program.run("version")
    except OSError as error:
        print(f"conformance: cannot run {' '.join(argv)}: {error.strerror}", file=sys.stderr)
        return 2
    if probe.returncode not in (0, 1) and not probe.stdout and not probe.stderr:
        print(f"conformance: cannot run {' '.join(argv)}", file=sys.stderr)
        return 2
    report = run_kit(program)
    passed = sum(1 for check in report.checks if check["passed"])
    summary = {"program": argv, "contract": "agent-cli/v2", "passed": report.passed,
               "checks": report.checks, "counts": {"passed": passed, "failed": len(report.checks) - passed}}
    if report_path:
        report_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    if as_json:
        print(json.dumps(summary, indent=2))
    else:
        for check in report.checks:
            mark = "ok  " if check["passed"] else "FAIL"
            print(f"{mark} {check['name']}" + (f"  ({check['detail']})" if check["detail"] and not check["passed"] else ""))
        print(f"conformance: {passed} passed, {len(report.checks) - passed} failed")
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
