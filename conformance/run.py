#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0
"""Conformance of a program to agent-cli/v2, checked from the outside.

    conformance/run.py PROGRAM [ARG...] [--report FILE] [--json] [--timeout SECONDS]

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
import math
import os
import pathlib
import re
import shlex
import signal
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from validate import json_equal, unsupported_keywords, validate  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
SCHEMAS = {name: json.loads((HERE.parent / "schemas" / f"{name}.json").read_text(encoding="utf-8"))
           for name in ("describe", "envelope", "version", "records")}
GLOBAL_OPTIONS = {
    "--format": {"name": "VALUE", "type": "choice", "choices": ["text", "json", "jsonl"]},
    "--json": None, "--compact": None, "--pretty": None, "--non-interactive": None, "--verbose": None,
    "--progress": {"name": "VALUE", "type": "choice", "choices": ["auto", "always", "never"]},
    "--pager": {"name": "VALUE", "type": "choice", "choices": ["auto", "always", "never"]},
    "--field": {"name": "NAME", "type": "string"},
    "--color": {"name": "VALUE", "type": "choice", "choices": ["auto", "always", "never"]},
    "--help": None,
}
BUILT_INS = {"help": ["help"], "version": ["version"], "describe": ["describe"], "completion": ["completion"],
             "complete.candidates": ["__complete"]}
EXIT_CODES = {"0": "command completed", "1": "execution failed", "2": "valid report with violations"}
GLOBAL_DEFAULTS = {"--format": "text", "--color": "auto", "--progress": "auto", "--pager": "auto"}


class Program:
    def __init__(self, command: list[str], timeout: float = 10) -> None:
        self.command = command
        self.timeout = timeout
        self.failures: list[str] = []
        self.env = {**os.environ, "NO_COLOR": "1"}
        self.env.pop("MAELYS_CLI_FORMAT", None)

    def run(self, *arguments: str, env: dict | None = None) -> subprocess.CompletedProcess:
        argv = [*self.command, *arguments]
        def result(code, stdout, stderr):
            completed = subprocess.CompletedProcess(argv, code, stdout, stderr)
            completed.request_arguments = arguments
            return completed
        with subprocess.Popen(argv, env={**self.env, **(env or {})}, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              start_new_session=os.name == "posix") as process:
            try:
                stdout, stderr = process.communicate(timeout=self.timeout)
            except subprocess.TimeoutExpired:
                if os.name == "posix":
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                else:
                    process.kill()
                try:
                    process.communicate(timeout=self.timeout)
                except subprocess.TimeoutExpired:
                    # a grandchild that left the session may hold the pipes: stop reading, reap the child
                    process.stdout.close()
                    process.stderr.close()
                    process.wait()
                message = f"{shlex.join(arguments)}: timed out after {self.timeout:g}s"
                self.failures.append(message)
                return result(-1, "", message)
        try:
            return result(process.returncode, stdout.decode("utf-8"), stderr.decode("utf-8"))
        except UnicodeDecodeError:
            message = f"{shlex.join(arguments)}: output is not UTF-8"
            self.failures.append(message)
            return result(-1, "", message)


class Report:
    def __init__(self) -> None:
        self.checks: list[dict] = []
        self.output_schemas: dict[str, dict] = {}
        self.output_modes: dict[str, str] = {}
        self.patterns = dict(BUILT_INS)

    def add(self, name: str, passed: bool, detail: str = "") -> bool:
        self.checks.append({"name": name, "passed": passed, "detail": detail})
        return passed

    @property
    def passed(self) -> bool:
        return all(check["passed"] is not False for check in self.checks)

    def skip(self, name: str, detail: str) -> None:
        self.checks.append({"name": name, "passed": None, "detail": detail})


def parse_json(text: str):
    def reject_constant(value):
        raise ValueError(f"not a JSON number: {value}")
    return json.loads(text, parse_constant=reject_constant)


def issues_text(issues: list) -> str:
    return "; ".join(map(repr, issues[:6])) + (" ..." if len(issues) > 6 else "")


def envelope(report: Report, name: str, completed: subprocess.CompletedProcess, expect_ok: bool) -> dict | None:
    """Parse and validate an envelope; on failure, stdout must be empty."""
    stream, other = (completed.stdout, completed.stderr) if expect_ok else (completed.stderr, completed.stdout)
    try:
        body = parse_json(stream)
    except (ValueError, RecursionError):
        report.add(name, False, f"no JSON envelope on {'stdout' if expect_ok else 'stderr'}: {stream[:120]!r}")
        return None
    issues = validate(body, SCHEMAS["envelope"])
    if issues:
        report.add(name, False, issues_text(issues))
        return None
    if body["ok"] != expect_ok:
        report.add(name, False, f"ok is {body['ok']}")
        return None
    if body["exitCode"] != completed.returncode:
        report.add(name, False, f"envelope says exit {body['exitCode']}, process exited {completed.returncode}")
        return None
    if other:
        report.add(name, False, f"the other stream is not empty: {other[:120]!r}")
        return None
    arguments = getattr(completed, "request_arguments", None)
    if arguments:
        matches = [(len(pattern), identifier) for identifier, pattern in report.patterns.items()
                   if list(arguments[:len(pattern)]) == pattern]
        expected = max(matches)[1] if matches else {"--help": "help", "--version": "version"}.get(arguments[0], "unknown")
        if not report.add(f"{name}: envelope identifies the invoked command", body["command"] == expected,
                          f"command {body['command']!r}, expected {expected!r}"):
            return None
    if expect_ok:
        identifier = body["command"]
        schema_name = {"describe": "describe", "version": "version", "complete.candidates": "records"}.get(identifier)
        if report.output_modes.get(identifier) == "json-records":
            schema_name = "records"
        if schema_name:
            issues = validate(body["data"], SCHEMAS[schema_name])
            if not report.add(f"{name} data matches schemas/{schema_name}.json", not issues, issues_text(issues)):
                return None
        if schema_name == "records":
            data = body["data"]
            valid = data["count"] == len(data["records"])
            if identifier == "complete.candidates":
                valid = valid and all(isinstance(item.get("word"), str) for item in data["records"])
            if not report.add(f"{name}: count and completion words are valid", valid):
                return None
        if identifier == "help":
            data = body["data"]
            valid = isinstance(data.get("text"), str) and isinstance(data.get("commands"), list) \
                and all(isinstance(item, str) for item in data["commands"])
            if not report.add(f"{name}: help data has text and command identifiers", valid):
                return None
        if identifier in report.output_schemas:
            try:
                issues = validate(body["data"], report.output_schemas[identifier])
            except (ValueError, LookupError, TypeError, AttributeError, RecursionError, re.error) as error:
                report.add(f"{name}: declared outputSchema can be evaluated", False, str(error))
                return None
            if not report.add(f"{name}: data matches declared outputSchema", not issues, issues_text(issues)):
                return None
    return body


def check_jsonl(report: Report, name: str, completed: subprocess.CompletedProcess, expected: list[dict]) -> None:
    try:
        lines = completed.stdout.split("\n")
        if lines[-1] == "":
            lines.pop()
        records = [parse_json(line) for line in lines]
    except (ValueError, RecursionError):
        report.add(name, False, f"invalid JSONL: {completed.stdout[:120]!r}")
        return
    report.add(name, completed.returncode == 0 and completed.stderr == "" and json_equal(records, expected),
               f"exit {completed.returncode}, stdout {completed.stdout[:80]!r}, stderr {completed.stderr[:80]!r}")


def cell(value) -> str:
    """One field of the section 7 pipe form: a string unquoted and escaped, anything else compact JSON."""
    if isinstance(value, str):
        escapes = {"\\": "\\\\", "\t": "\\t", "\r": "\\r", "\n": "\\n"}
        return "".join(escapes.get(char, f"\\u{ord(char):04x}") if ord(char) < 32 or char == "\\"
                       or ord(char) == 127 else char for char in value)
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def text_records(records: list[dict]) -> str:
    """The section 7 pipe form; column order never depends on schema serialization."""
    columns = sorted({key for record in records for key in record})
    return "".join("\t".join(cell(record[key]) if key in record else "" for key in columns) + "\n" for record in records)


def field_text(value) -> str:
    """Section 5: the pipe rendering of one member of data, whatever its shape."""
    if isinstance(value, list):
        if value and all(isinstance(item, dict) for item in value):
            return text_records(value)
        return "".join(cell(item) + "\n" for item in value)
    if isinstance(value, dict):
        return text_records([value])
    return cell(value) + "\n"


def field_jsonl(value) -> str:
    """Section 5: an array gives one compact JSON value per line, any other member exactly one line."""
    items = value if isinstance(value, list) else [value]
    return "".join(json.dumps(item, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n" for item in items)


def check_field(report: Report, program: Program, catalog: dict) -> None:
    """--field renders one member of data, and refuses what the contract refuses."""
    shapes = {}
    for name in sorted(catalog):
        value = catalog[name]
        if isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
            shapes.setdefault("array of objects", name)
        elif isinstance(value, list):
            shapes.setdefault("array", name)
        elif isinstance(value, dict):
            shapes.setdefault("object", name)
        else:
            shapes.setdefault("scalar", name)
    for shape, name in shapes.items():
        text = program.run("describe", "--field", name, "--format", "text", "--non-interactive")
        report.add(f"--field {name} renders the {shape} member by the section 7 rules",
                   text.returncode == 0 and text.stderr == "" and text.stdout == field_text(catalog[name]),
                   f"exit {text.returncode}, stdout {text.stdout[:80]!r}, stderr {text.stderr[:80]!r}")
        lines = program.run("describe", "--field", name, "--format", "jsonl", "--non-interactive")
        report.add(f"--field {name} in jsonl gives one compact value per line",
                   lines.returncode == 0 and lines.stderr == "" and lines.stdout == field_jsonl(catalog[name]),
                   f"exit {lines.returncode}, stdout {lines.stdout[:80]!r}, stderr {lines.stderr[:80]!r}")
    some = next(iter(shapes.values()), "kind")
    check_failure(report, "--field with --format json fails with VALIDATION_FAILED",
                  program.run("describe", "--field", some, "--json"), "VALIDATION_FAILED")
    # the json refusal is an option conflict and wins over any check inside the command, so jsonl carries this one
    check_failure(report, "--field of a member data does not carry fails with VALIDATION_FAILED",
                  program.run("describe", "--field", "no-such-member", "--format", "jsonl"),
                  "VALIDATION_FAILED")


def check_pager_in_pipe(report: Report, program: Program) -> None:
    """An identity pager alone cannot prove that no process was started.

    The sentinel is named by PAGER; a program that hard-codes its pager and ignores PAGER escapes it."""
    with tempfile.TemporaryDirectory(prefix="agent-cli-pager-") as directory:
        marker = pathlib.Path(directory) / "started"
        script = pathlib.Path(directory) / "pager.py"
        script.write_text("import pathlib, sys\n" + f"pathlib.Path({str(marker)!r}).touch()\n"
                          + "sys.stdout.write(sys.stdin.read())\n", encoding="utf-8")
        env = {"PAGER": shlex.join([sys.executable, str(script)])}
        for mode, words in (("text", ("version",)), ("json", ("version",)),
                            ("jsonl", ("__complete",))):
            tail = ("--", "") if mode == "jsonl" else ()
            reference = program.run(*words, "--format", mode, "--pager", "never", *tail)
            for selection in ("auto", "always", "never"):
                marker.unlink(missing_ok=True)
                completed = program.run(*words, "--format", mode, "--pager", selection, *tail, env=env)
                report.add(f"--pager {selection} never starts a pager in a {mode} pipe",
                           not marker.exists() and completed.returncode == reference.returncode == 0
                           and completed.stdout == reference.stdout and completed.stderr == reference.stderr == "",
                           f"pager started: {marker.exists()}, exit {completed.returncode}")


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
        if visible and command.get("available"):
            report.add(f"{identifier}: __complete offers a visible option where it hides the hidden ones",
                       bool(visible & offered), f"offered {sorted(offered)}, visible {sorted(visible)}")
    if not command.get("available") or command.get("effect") != "read" or any(item.get("required") for item in options) \
            or any(item.get("required") for item in operands):
        return
    for item in hidden:
        words = hidden_option_invocation(item)
        constrained = item.get("requires") or item.get("group") or any(
            item["long"] in rule["options"] and rule["kind"] in ("requires", "all-or-none")
            for rule in command["input"]["constraints"])
        if words is None or constrained:
            continue
        accepted = program.run(*command.get("pattern", []), *words, "--format", "json", "--non-interactive")
        code = ""
        accepted_body = envelope(report, f"{identifier}: hidden option {item.get('long')} envelope", accepted,
                                 expect_ok=accepted.returncode in (0, 2))
        if accepted_body is None:
            continue
        if not accepted_body["ok"]:
            code = accepted_body["error"]["code"]
        report.add(f"{identifier}: hidden option {item.get('long')} is accepted",
                   accepted_body["ok"] or code != "VALIDATION_FAILED", f"exit {accepted.returncode} {code}")


def trunk_shape(item: dict, expected: dict | None) -> bool:
    """An option has a trunk option's shape: a flag, or the same value type and choices; never repeatable."""
    if item.get("repeatable") is not False:
        return False
    argument = item.get("argument")
    if expected is None:
        return argument is None
    return isinstance(argument, dict) and argument.get("type") == expected["type"] \
        and set(argument.get("choices", [])) == set(expected.get("choices", []))


def option_shape(option: dict) -> dict:
    argument = {key: value for key, value in option.get("argument", {}).items()
                if key != "name" and not key.startswith("x-")}
    if "choices" in argument:
        argument["choices"] = sorted(argument["choices"])
    return {"argument": argument, "repeatable": option["repeatable"]}


def run_kit(program: Program) -> Report:
    report = Report()
    try:
        _run_kit(program, report)
    except OSError as error:
        report.add("program can be run", False, str(error))
    for failure in getattr(program, "failures", []):
        report.add("invocation completes within the timeout with UTF-8 output", False, failure)
    return report


def _run_kit(program: Program, report: Report) -> Report:
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
    if issues:
        return report
    commands = [command for command in catalog.get("commands", []) if isinstance(command, dict) and "id" in command]
    by_id = {command["id"]: command for command in commands}
    report.patterns = {identifier: command["pattern"] for identifier, command in by_id.items()}
    report.output_modes = {identifier: command["outputMode"] for identifier, command in by_id.items()}
    for identifier, command in by_id.items():
        try:
            unknown = unsupported_keywords(command["outputSchema"])
        except (ValueError, KeyError, TypeError, AttributeError, RecursionError) as error:
            report.add(f"{identifier}: outputSchema is well formed", False, str(error))
            continue
        if unknown:
            report.skip(f"{identifier}: declared outputSchema validation", "unsupported: " + ", ".join(unknown))
        else:
            report.output_schemas[identifier] = command["outputSchema"]
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
            if long in GLOBAL_DEFAULTS and "default" in item:
                report.add(f"global option {long} declares the contract's default", item["default"] == GLOBAL_DEFAULTS[long],
                           f"default {item['default']!r}")
    global_longs = {item.get("long") for item in catalog.get("globalOptions", [])}
    product_globals = {item["long"]: item for item in catalog["globalOptions"] if item["long"] not in GLOBAL_OPTIONS}
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
        for item in command["input"]["options"]:
            if item["long"] in product_globals:
                declared = product_globals[item["long"]]
                report.add(f"{identifier}: {item['long']} agrees with its product global declaration",
                           json_equal(option_shape(item), option_shape(declared)))
        declared_options = {item.get("long") for item in command.get("input", {}).get("options", [])} | global_longs
        declared_operands = {item.get("name") for item in command.get("input", {}).get("operands", [])}
        unresolved = [entry for item in command.get("input", {}).get("options", [])
                      for entry in list(item.get("requires", [])) if entry not in declared_options]
        unresolved += [entry for item in command.get("input", {}).get("options", [])
                       for entry in list(item.get("conflictsWith", []))
                       if not (isinstance(entry, str) and
                               (entry in declared_options if entry.startswith("--") else entry in declared_operands))]
        unresolved += [entry for rule in command["input"]["constraints"] for entry in rule["options"]
                       if entry not in declared_options]
        report.add(f"{identifier}: requires and conflictsWith name declared options or operands", not unresolved,
                   f"unresolved {unresolved}")
        variadic = [index for index, item in enumerate(command["input"]["operands"]) if item["variadic"]]
        report.add(f"{identifier}: at most the last operand is variadic",
                   not variadic or variadic == [len(command["input"]["operands"]) - 1])
        check_hidden_options(report, program, command)
        one = program.run("describe", identifier, "--format", "json", "--non-interactive")
        body = envelope(report, f"{identifier}: describe {identifier}", one, expect_ok=True)
        if body is not None:
            data = body["data"]
            report.add(f"{identifier}: describe {identifier} returns the catalog's descriptor",
                       data.get("kind") == "command" and json_equal(data.get("commands"), [command])
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
               in (r"^[a-z]([a-z0-9.-]*[a-z0-9-])?$", r"^[a-z](?:[a-z0-9.-]*[a-z0-9-])?$")
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
    candidates = program.run("__complete", "--format", "json", "--", "")
    candidate_body = envelope(report, "__complete envelope", candidates, expect_ok=True)
    version = program.run("version", "--format", "json")
    body = envelope(report, "version envelope", version, expect_ok=True)
    if body is not None:
        issues = validate(body["data"], SCHEMAS["version"])
        report.add("version data matches schemas/version.json", not issues, issues_text(issues))
        report.add("version data agrees with describe",
                   body["data"].get("version") == catalog.get("version") and body["data"].get("program") == catalog.get("program"))
        alias = program.run("version", "--json")
        envelope(report, "version --json envelope", alias, expect_ok=True)
        report.add("--json is the exact alias of --format json", alias.stdout == version.stdout)
        compact = program.run("version", "--json", "--compact")
        pretty_false = program.run("version", "--json", "--pretty=false")
        envelope(report, "version --compact envelope", compact, expect_ok=True)
        envelope(report, "version --pretty=false envelope", pretty_false, expect_ok=True)
        report.add("--pretty=false equals --compact", compact.stdout == pretty_false.stdout and compact.stdout.count("\n") <= 1)
        flag = program.run("--version", "--json")
        envelope(report, "--version envelope", flag, expect_ok=True)
        report.add("--version equals version", flag.stdout == version.stdout)
        verbose_json = program.run("version", "--verbose", "--json")
        if envelope(report, "--verbose writes nothing in JSON mode", verbose_json, expect_ok=True) is not None:
            report.add("--verbose leaves the JSON envelope unchanged", verbose_json.stdout == version.stdout,
                       f"stdout {verbose_json.stdout[:60]!r}")
        check_failure(report, "--verbose leaves a JSON failure envelope alone on stderr",
                      program.run("no-such-command", "--verbose", "--json"), "INVALID_COMMAND")
        jsonl_verbose = program.run("__complete", "--verbose", "--format", "jsonl", "--non-interactive", "--", "")
        if candidate_body is not None:
            check_jsonl(report, "--verbose writes nothing in jsonl mode and preserves records",
                        jsonl_verbose, candidate_body["data"]["records"])
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
                   and progress_never.stderr == "",
                   f"exit {progress_never.returncode}, stderr {progress_never.stderr[:80]!r}")
        check_failure(report, "--progress always leaves a JSON failure envelope alone on stderr",
                      program.run("no-such-command", "--progress", "always", "--json"), "INVALID_COMMAND")
        jsonl_progress = program.run("__complete", "--progress", "always", "--format", "jsonl", "--non-interactive", "--", "")
        if candidate_body is not None:
            check_jsonl(report, "--progress always writes nothing in jsonl mode and preserves records",
                        jsonl_progress, candidate_body["data"]["records"])
        pager_json = program.run("version", "--pager", "always", "--json")
        if envelope(report, "--pager always pages nothing in JSON mode", pager_json, expect_ok=True) is not None:
            report.add("--pager leaves the JSON envelope unchanged", pager_json.stdout == version.stdout,
                       f"stdout {pager_json.stdout[:60]!r}")
        pager_never = program.run("version", "--pager=never", "--format", "text", "--non-interactive")
        report.add("--pager never is accepted and leaves stdout unchanged",
                   pager_never.returncode == 0 and pager_never.stdout == plain_text.stdout
                   and pager_never.stderr == "",
                   f"exit {pager_never.returncode}, stdout {pager_never.stdout[:60]!r}")
        check_pager_in_pipe(report, program)
        check_field(report, program, catalog)
        verbose_false = program.run("version", "--verbose=false", "--format", "text", "--non-interactive")
        report.add("--verbose=false is accepted and silent",
                   verbose_false.returncode == 0 and verbose_false.stdout == plain_text.stdout
                   and verbose_false.stderr == "",
                   f"exit {verbose_false.returncode}, stderr {verbose_false.stderr[:80]!r}")
    help_run = program.run("help", "--format", "json")
    body = envelope(report, "help envelope", help_run, expect_ok=True)
    if body is not None:
        data = body["data"]
        report.add("help data has text and commands",
                   isinstance(data.get("text"), str) and bool(data.get("text")) and isinstance(data.get("commands"), list))
        help_alias = program.run("--help", "--format", "json")
        envelope(report, "--help envelope", help_alias, expect_ok=True)
        report.add("--help equals help", help_alias.stdout == help_run.stdout)
    for words in (("version",), ("help",), ("describe", "--summary")):
        text_run = program.run(*words, "--format", "text", "--non-interactive")
        report.add(f"text success of {' '.join(words)} is on stdout with stderr empty",
                   text_run.returncode == 0 and text_run.stdout.strip() != "" and text_run.stderr == "",
                   f"exit {text_run.returncode}, stdout {text_run.stdout[:40]!r}, stderr {text_run.stderr[:80]!r}")
    # ---- the failures the contract prescribes ----
    check_failure(report, "unknown command fails with INVALID_COMMAND", program.run("no-such-command", "--json"), "INVALID_COMMAND")
    check_failure(report, "unsupported option fails with VALIDATION_FAILED",
                  program.run("version", "--no-such-option", "--json"), "VALIDATION_FAILED")
    check_failure(report, "jsonl on a json-envelope command fails with VALIDATION_FAILED",
                  program.run("version", "--format", "jsonl"), "VALIDATION_FAILED")
    for long, argument in GLOBAL_OPTIONS.items():
        words = [long, argument["choices"][0] if argument.get("choices") else "x"] if argument else [long]
        check_failure(report, f"duplicate {long} fails with VALIDATION_FAILED",
                      program.run("version", *words, *words, *([] if long == "--json" else ["--json"])),
                      "VALIDATION_FAILED")
    for long in ("--format", "--color", "--progress", "--pager"):
        check_failure(report, f"invalid {long} choice fails with VALIDATION_FAILED",
                      program.run("version", f"{long}=invalid-choice", "--json"), "VALIDATION_FAILED")
    transactions = [command for command in commands if isinstance(command.get("effect"), dict)]
    if transactions:
        identifier = transactions[0]["id"]
        check_failure(report, f"{identifier}: --dry-run is refused with VALIDATION_FAILED",
                      program.run(*transactions[0]["pattern"], "--dry-run", "--json"), "VALIDATION_FAILED")
    text = program.run("no-such-command")
    report.add("text failure is 'PROGRAM: [CODE] message' on stderr",
               text.returncode == 1 and text.stdout == "" and text.stderr.startswith(f"{catalog.get('program')}: [INVALID_COMMAND] "),
               text.stderr[:120])
    # ---- completion ----
    for shell in ("bash", "zsh", "fish"):
        script = program.run("completion", shell)
        report.add(f"completion {shell} prints a script calling __complete",
                   script.returncode == 0 and "__complete" in script.stdout)
    body = candidate_body
    if body is not None:
        issues = validate(body["data"], SCHEMAS["records"])
        report.add("__complete data matches schemas/records.json", not issues, issues_text(issues))
        words = {record.get("word") for record in body["data"].get("records", [])}
        visible = {command["pattern"][0] for command in commands if not command["hidden"] and command["available"]}
        report.add("__complete offers the visible command words", visible <= words, f"missing {visible - words}")
        excluded = {command["pattern"][0] for command in commands if command["hidden"] or not command["available"]} - visible
        report.add("__complete omits hidden and unavailable command words", not excluded & words,
                   f"unexpected {excluded & words}")
        jsonl = program.run("__complete", "--format", "jsonl", "--", "")
        check_jsonl(report, "__complete --format jsonl renders the same records, one per line", jsonl, body["data"]["records"])
        text_run = program.run("__complete", "--format", "text", "--non-interactive", "--", "")
        report.add("__complete --format text into a pipe renders one plain line per record, no header",
                   text_run.returncode == 0 and text_run.stderr == "" and text_run.stdout == text_records(body["data"]["records"]),
                   f"stdout {text_run.stdout[:80]!r}, stderr {text_run.stderr[:80]!r}")
    return report


def main(argv: list[str]) -> int:
    as_json, report_path, timeout = False, None, 10.0
    command = []
    index = 0
    try:
        while index < len(argv):
            argument = argv[index]
            if argument == "--":
                command.extend(argv[index + 1:])
                break
            if argument == "--json":
                as_json = True
            elif argument in ("--report", "--timeout"):
                index += 1
                if argument == "--report":
                    report_path = pathlib.Path(argv[index])
                else:
                    timeout = float(argv[index])
                    if not math.isfinite(timeout) or timeout <= 0:
                        raise ValueError("timeout must be a positive finite number")
            else:
                command.append(argument)
            index += 1
    except (IndexError, ValueError) as error:
        print(f"conformance: invalid kit arguments ({error})", file=sys.stderr)
        return 2
    if not command:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    program = Program(command, timeout=timeout)
    try:
        probe = program.run("version", "--non-interactive")
    except OSError as error:
        print(f"conformance: cannot run {shlex.join(command)}: {error.strerror}", file=sys.stderr)
        return 2
    if probe.returncode not in (0, 1) and not probe.stdout and not probe.stderr:
        print(f"conformance: cannot run {shlex.join(command)}", file=sys.stderr)
        return 2
    report = run_kit(program)
    passed = sum(check["passed"] is True for check in report.checks)
    failed = sum(check["passed"] is False for check in report.checks)
    skipped = sum(check["passed"] is None for check in report.checks)
    summary = {"reportVersion": 1, "program": command, "contract": "agent-cli/v2", "passed": report.passed,
               "checks": report.checks, "counts": {"passed": passed, "failed": failed, "skipped": skipped},
               "scope": {"catalog": "all descriptors", "invocations": "built-ins and safe hidden-option probes",
                         "notChecked": ["product business behavior and writes", "protocol streams and delegates",
                                        "terminal rendering (tested separately by implementations)"]}}
    if report_path:
        try:
            report_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        except OSError as error:
            print(f"conformance: cannot write report: {error}", file=sys.stderr)
            return 2
    if as_json:
        print(json.dumps(summary, indent=2))
    else:
        for check in report.checks:
            mark = "SKIP" if check["passed"] is None else "ok  " if check["passed"] else "FAIL"
            print(f"{mark} {check['name']}" + (f"  ({check['detail']})" if check["detail"] and not check["passed"] else ""))
        print(f"conformance: {passed} passed, {failed} failed, {skipped} skipped")
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
