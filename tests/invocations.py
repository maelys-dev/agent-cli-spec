# SPDX-License-Identifier: MPL-2.0
"""Generated invocations and what every conformant program does with them.

The kit judges an example from the catalog alone (`example_issues`). Turned around, the same judge
says of any command line whether the catalog accepts it, so a few hundred lines can be generated from
a catalog and a program held to what the contract says of each: this finds what a program does that
the text forbids and no check looks at, before an implementer reports it.

It is a test of this repository's reference program, not a part of the kit: it runs `--apply`, in a
home it made, and lines a product may not survive.

It can be pointed at another program, by whoever owns that program:

    python3 tests/invocations.py [--lines N] [--apply] [--reference] [--format-variable NAME] PROGRAM [ARG...]

Each line runs in a directory and a home made for it. A delegate, a `passthrough` command and a stream
command are never run. Lines carrying `--apply` are left out unless `--apply` is given: with it the
program is trusted to write only under the directory and the home it is given. `--format-variable` names the
environment variable by which the program lets the environment pick its default format (`MAELYS_CLI_FORMAT`):
the lines are then run a second time with it set to `json`.
"""
from __future__ import annotations

import collections
import json
import os
import pathlib
import random
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "conformance"))
from run import example_issues, value_problem  # noqa: E402

CODES = {"INVALID_COMMAND", "VALIDATION_FAILED", "PRECONDITION_FAILED", "POLICY_FAILED", "ACCESS_DENIED", "NOT_FOUND",
         "IO_FAILED", "PROCESS_FAILED", "PROTOCOL_FAILED", "UNSUPPORTED", "UNEXPECTED"}
RENDERINGS = (["--format", "json"], ["--json"], ["--format", "text"], ["--format", "jsonl"], ["--json", "--compact"],
              ["--non-interactive"], ["--color", "never"], ["--pager", "never"], ["--verbose"], ["--progress", "never"],
              ["--verbose", "--json"],
              ["--field", "mode"], ["--field", "mode", "--format", "jsonl"], ["--field", "no-such-member"],
              ["--field", "mode", "--json"])


def valid_value(declaration: dict) -> str | None:
    """A value of the declared kind, or None when none of the candidates is one."""
    kind = declaration.get("type", "string")
    widths = declaration.get("digits")
    width = (widths if isinstance(widths, int) else widths[0]) if widths else 64
    candidates = {"choice": declaration.get("choices", [])[:1], "boolean": ["true"],
                  "unsigned": [str(declaration.get("minimum", 1))], "integer": [str(declaration.get("minimum", 1))],
                  "absolute-path": ["/srv/kit"], "sha256": ["ab" * 32], "hex": ["ab" * (width // 2)],
                  "digest": [f"{declaration.get('algorithms', ['sha256'])[0]}:{'ab' * (width // 2)}"],
                  "size": ["1M"], "duration": ["5s"]}.get(kind, ["kit", "a", "note", "v1", "a-b", "1"])
    return next((value for value in candidates if not value_problem(declaration, value)), None)


def invalid_value(declaration: dict) -> str | None:
    """A value the declared kind refuses, or None when the kit's judge cannot tell one."""
    candidates = ["no-such-choice", "maybe", "-1", "x", "relative/path", "md5:00", "abc", "!", "99999999"]
    return next((value for value in candidates if value_problem(declaration, value)), None)


def opaque(command: dict) -> bool:
    """A command whose line the catalog does not own, or whose stdout it does not render."""
    return bool(command.get("external") or command["input"].get("passthrough")
                or command["outputMode"] == "protocol-stream")


def lines(command: dict, rng: random.Random, count: int) -> list[list[str]]:
    """Command lines for one command: the plain one, each rule broken once, and random mixtures."""
    operands = [valid_value(item) or "kit" for item in command["input"]["operands"] if item.get("required")]
    base = list(command["pattern"]) + operands
    options = command["input"]["options"]
    for item in options:
        if item.get("required"):
            base += [item["long"]] + ([valid_value(item["argument"]) or "kit"] if item.get("argument") else [])

    def spelled(item: dict, wrong: bool = False) -> list[str]:
        if not item.get("argument"):
            return [item["long"]]
        value = (invalid_value if wrong else valid_value)(item["argument"])
        return [item["long"], value] if value is not None else []

    found = [base, base + ["--no-such-option"], base + ["--", "kit"], base + ["kit-extra-operand"],
             base + ["--help"], base + ["--version"], base[:-1] if operands else base]
    found += [base + rendering for rendering in RENDERINGS] + [base + ["--help", "--json"]]
    found += [base + ["--help", "--format", "jsonl"], base + ["--help", "--format", "jsonl", "--field", "commands"],
              list(command["pattern"]) + ["--help"]]
    # after `--` a word is an operand whatever its spelling; a flag set to false is a flag not given
    found += [base + ["--", "--help"], base + ["--", "--version"], base + ["--help", "--", "kit"],
              base + ["--help=false"], base + ["--help=true"], base + ["--help=false", "--json"],
              base + ["--json=false"], base + ["--help", "--help"], base + ["--help", "--field", "commands", "--json"]]
    for place, item in enumerate(options):
        found += [base + spelled(item), base + spelled(item) + spelled(item), base + spelled(item, wrong=True),
                  base + [item["long"]], base + spelled(item) + ["--help"], base + spelled(item) + ["--version"],
                  base + spelled(item) + ["--json"], base + ([] if item.get("argument") else [f"{item['long']}=false"]),
                  base + spelled(item) + ["--help", "--json"], base + spelled(item) + ["--field", "no-such-member"],
                  base + spelled(item) + ["--field", "mode", "--format", "jsonl"]]
        found += [base + spelled(item) + spelled(other) for other in options[place + 1:]]
        if item.get("argument") and valid_value(item["argument"]) is not None:
            joined = f"{item['long']}={valid_value(item['argument'])}"
            found += [base + [joined], base + [joined, "--help"], base + [joined, "--format", "jsonl"]]
        else:
            found += [base + [f"{item['long']}=true"], base + [f"{item['long']}=false", "--help"]]
    for _ in range(count):
        line = list(command["pattern"])
        line += operands[:rng.choice([len(operands)] * 4 + [max(0, len(operands) - 1)])]
        for item in rng.sample(options, k=rng.randint(0, len(options))):
            line += spelled(item, wrong=rng.random() < 0.15)
        line += rng.choice(RENDERINGS) if rng.random() < 0.6 else []
        line += rng.choice([[], [], [], ["--help"], ["--version"], ["--no-such-option"], ["kit-extra-operand"]])
        found.append(line)
    return [line for line in found if line]


def unknown_lines() -> list[list[str]]:
    """Lines that name no command: resolution fails first, whatever else they carry (section 8, step 1)."""
    name = "kit-no-such-command"
    return [[name], [name, "--help"], [name, "--json"], [name, "--no-such-option"], [name, "--help", "--json"],
            [name, "--format", "jsonl"], [name, "--field", "mode"], [name, "kit", "--version"], [name, "--", "--help"]]


def unknown_violations(words: list[str], completed) -> list[str]:
    found = []
    if completed.returncode != 1 or completed.stdout != "":
        found.append(f"unknown-command: exit {completed.returncode} with {len(completed.stdout)} bytes on stdout")
    elif failure_code(completed.stderr) != "INVALID_COMMAND":
        found.append(f"unknown-command: fails with {failure_code(completed.stderr)}, not INVALID_COMMAND")
    elif completed.stderr.lstrip().startswith("{") and json.loads(completed.stderr).get("command") != "unknown":
        found.append(f"unknown-command: the envelope names {json.loads(completed.stderr).get('command')!r}")
    return found


def before_separator(words: list[str]) -> list[str]:
    return words[:words.index("--")] if "--" in words else words


def flag(before: list[str], long: str) -> bool:
    """Whether a flag is given: `--flag` or `--flag=true`; `--flag=false` is a flag not given (section 2)."""
    return long in before or f"{long}=true" in before


def failure_code(stderr: str) -> str | None:
    """The error code of a failure, read from the envelope (json and jsonl) or from `PROGRAM: [CODE] message`."""
    if stderr.lstrip().startswith("{"):
        try:
            return json.loads(stderr)["error"]["code"]
        except (ValueError, KeyError, TypeError):
            return None
    match = re.search(r"\[([A-Z_]+)\]", stderr)
    return match.group(1) if match else None


def violations(command: dict, global_options: list[dict], words: list[str], completed, written: list[str],
               reference: bool = False, default: str = "text") -> list[str]:
    """What this run does that the contract forbids, each as `invariant: detail`. An empty list is a pass.

    `reference` adds what holds of the reference program only: it refuses nothing the catalog accepts, and a
    success of it prints. A product may refuse a value for a reason of its own (a name that is not defined, a
    file that is not there), VALIDATION_FAILED being the code for it, and a command with nothing to say to a
    human is silent in text mode, its envelope being what counts.

    `default` is the format the environment selected for this run, where the implementation has such a variable."""
    found: list[str] = []
    before = before_separator(words)
    code, out, err = completed.returncode, completed.stdout, completed.stderr
    formats = [before[index + 1] for index, word in enumerate(before[:-1]) if word == "--format"]
    formats += [word.partition("=")[2] for word in before if word.startswith("--format=")]
    chosen = "json" if flag(before, "--json") else formats[-1] if formats else default
    json_mode, formats = chosen == "json", [chosen]
    asks = flag(before, "--help")
    # ---- what holds for every line ----
    if code not in (0, 1, 2):
        found.append(f"exit: {code} is not 0, 1 or 2")
    if "Traceback" in err or "Traceback" in out:
        found.append("crash: a traceback instead of a failure")
    if code == 1 and out != "":
        found.append("failure-stdout: a failure leaves stdout empty (section 7)")
    if code == 1 and err == "":
        found.append("failure-silent: a failure says nothing on stderr")
    if code == 1 and written:
        found.append(f"failure-writes: a failure wrote {written[:3]}")
    if not flag(before, "--apply") and written:
        found.append(f"plan-writes: without --apply the line wrote {written[:3]} (section 4)")
    if opaque(command):
        return found
    if asks and written:
        found.append(f"help-writes: --help ran the command, which wrote {written[:3]} (section 6)")
    if command.get("available") is False and not asks and code != 1:
        found.append("unavailable-runs: a command this build cannot run did not fail (section 8)")
    alone = [issue for issue in example_issues(command, global_options, words)
             if kind(issue) in ALONE and issue.startswith("--") and not issue.endswith("is hidden")]
    body = None
    if json_mode:
        try:
            body = json.loads(out if code != 1 else err)
        except ValueError:
            found.append("envelope: the JSON rendering is not one JSON document")
    if body is not None:
        if body.get("exitCode") != code or body.get("ok") is not (code != 1) or isinstance(body.get("exitCode"), bool):
            found.append(f"envelope: ok {body.get('ok')!r} and exitCode {body.get('exitCode')!r} for exit {code}")
        # sections 6 and 8: the help a line gives is named help, and so is a refusal of its rendering; what one
        # option says alone is refused before, in the name of the command
        named = "help" if asks and not alone else command["id"]
        if body.get("command") != named:
            found.append(f"envelope-command: names {body.get('command')!r}, not {named!r}")
        if code == 1 and body.get("error", {}).get("code") not in CODES:
            found.append(f"error-code: {body.get('error', {}).get('code')!r} is not a code of section 8")
    records = command["outputMode"] == "json-records" or "--field" in before
    if reference and code != 1 and out == "" and not records:
        found.append("success-silent: a success of a json-envelope command prints nothing")
    # an option of the command may ask for a diagnostic of its own; of the trunk, only --verbose in text mode does
    text_mode = not json_mode and formats[-1:] != ["jsonl"]
    own = {item["long"] for item in command["input"]["options"]}
    if code != 1 and err != "" and not (text_mode and flag(before, "--verbose")) \
            and not any(word.partition("=")[0] in own for word in before):
        found.append("success-stderr: a success writes to stderr, which only --verbose in text mode allows here")
    if asks:
        # section 8: what one option says alone is judged before --help, what the line lacks as a whole is not,
        # and the rendering is that of help, which is not records
        if alone and failure_code(err) != "VALIDATION_FAILED":
            found += [f"accepts: {kind(issue)}, under --help" for issue in alone]
        field = "--field" in before
        if not alone and code == 1 and not field and formats[-1:] != ["jsonl"]:
            found.append("help-refused: --help on a line that only lacks something as a whole is refused")
        if not alone and formats[-1:] == ["jsonl"] and not field and failure_code(err) != "VALIDATION_FAILED":
            found.append("help-jsonl: under --help, jsonl without --field is not refused as it is for help")
        return found
    # ---- what the catalog says of the line ----
    grammar = [issue for issue in example_issues(command, global_options, words) if not issue.endswith("is hidden")]
    failed = failure_code(err) if code == 1 else None
    if grammar and failed != "VALIDATION_FAILED":
        found += [f"accepts: {kind(issue)}" for issue in grammar]
    field = before[before.index("--field") + 1] if "--field" in before[:-1] else None
    schema = command.get("outputSchema", {})
    # a read decides on --field from its data, which the catalog does not hold; a command that may write, from
    # the `required` of its outputSchema (section 5)
    rendering = (formats[-1:] == ["jsonl"] and command["outputMode"] != "json-records" and field is None) \
        or (field is not None and (json_mode or command["effect"] == "read" or field not in schema.get("required", [])))
    if command.get("available") is False:
        # step 5 comes after the line is read and before its rendering: a line that is right names the cause
        if not grammar and failed in ("VALIDATION_FAILED", "INVALID_COMMAND"):
            found.append(f"unavailable-order: a right line of an unavailable command fails with {failed} (section 8)")
        return found
    if reference and not grammar and not rendering and failed == "VALIDATION_FAILED":
        found.append("refuses: a line the catalog accepts fails with VALIDATION_FAILED")
    return found


ALONE = {"an undeclared option", "--version after a command", "a repeated option", "an option without its value",
         "a flag with a value that is not true or false", "a value that is not of the declared kind"}


def kind(issue: str) -> str:
    """The rule an issue of `example_issues` is about, without the words of the line."""
    for needle, rule in (("--version is not an option", "--version after a command"),
                         ("operands where", "a wrong number of operands"), ("is not an option", "an undeclared option"),
                         ("is required", "a missing required option"), ("not repeatable", "a repeated option"),
                         ("has no value", "an option without its value"), ("requires", "an unmet requires"),
                         ("conflicts with", "a conflict"), ("does not hold", "a broken constraint"),
                         ("is a flag", "a flag with a value that is not true or false")):
        if needle in issue:
            return rule
    return "a value that is not of the declared kind"


def main(argv: list[str]) -> int:
    """Run the generated lines against a program and print what it does that the contract forbids."""
    count, with_apply, reference, variable = 10, False, False, None
    while argv and argv[0] in ("--lines", "--apply", "--reference", "--format-variable"):
        if argv[0] == "--lines":
            count, argv = int(argv[1]), argv[2:]
        elif argv[0] == "--format-variable":
            variable, argv = argv[1], argv[2:]
        else:
            with_apply, reference, argv = with_apply or argv[0] == "--apply", reference or argv[0] == "--reference", argv[1:]
    if not argv:
        print(__doc__.split("It can be pointed", 1)[1].split("\n\n", 2)[1], file=sys.stderr)
        return 2
    first = shutil.which(argv[0]) or argv[0]
    program = [os.path.abspath(first) if os.path.exists(first) else first] \
        + [os.path.abspath(word) if os.path.exists(word) else word for word in argv[1:]]
    kept = {key: value for key, value in os.environ.items() if key not in ("MAELYS_CLI_FORMAT", variable)}

    def run(words: list[str], sandbox: pathlib.Path, default: str = "text") -> subprocess.CompletedProcess:
        home = sandbox / "home"
        env = {**kept, "NO_COLOR": "1", "PAGER": "", "HOME": str(home), "XDG_DATA_HOME": str(home / ".local/share"),
               "XDG_CONFIG_HOME": str(home / ".config"), "ZDOTDIR": str(home)}
        if variable and default != "text":
            env[variable] = default
        return subprocess.run([*program, *words], cwd=sandbox / "work", env=env, stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=30, check=False)
    found: dict[tuple[str, str], list[tuple[str, list[str]]]] = collections.OrderedDict()
    total, left_out = 0, []
    with tempfile.TemporaryDirectory(prefix="agent-cli-lines-") as directory:
        sandbox = pathlib.Path(directory)
        for name in ("home", "work"):
            (sandbox / name).mkdir()
        catalog = json.loads(run(["describe", "--format", "json"], sandbox).stdout)["data"]
        for words in unknown_lines():
            total += 1
            for violation in unknown_violations(words, run(words, sandbox)):
                name, detail = violation.split(": ", 1)
                found.setdefault((name, detail), []).append(("unknown", words))
        for default in ["text"] + (["json"] if variable else []):
            rng = random.Random(2130)
            for command in catalog["commands"]:
                if opaque(command):
                    left_out += [command["id"]] if command["id"] not in left_out else []
                    continue
                for words in lines(command, rng, count):
                    if flag(before_separator(words), "--apply") and not with_apply:
                        continue
                    for name in ("home", "work"):
                        shutil.rmtree(sandbox / name, ignore_errors=True)
                        (sandbox / name).mkdir()
                    try:
                        completed = run(words, sandbox, default)
                    except subprocess.TimeoutExpired:
                        found.setdefault(("timeout", "the line did not finish in 30 seconds"), []).append((command["id"], words))
                        continue
                    written = sorted(str(path.relative_to(sandbox)) for path in sandbox.rglob("*") if path.is_file())
                    total += 1
                    for violation in violations(command, catalog["globalOptions"], words, completed, written, reference,
                                                default):
                        name, detail = violation.split(": ", 1)
                        detail = re.sub(r"wrote \[.*?\]", "wrote files", detail) + (f" [{variable}={default}]" if default != "text" else "")
                        found.setdefault((name, detail), []).append((command["id"], words))
    print(f"{' '.join(argv)}: {total} lines over {len(catalog['commands']) - len(left_out)} commands"
          + (f"; not run: {', '.join(left_out)}" if left_out else "") + ("" if with_apply else "; no line with --apply"))
    for (name, detail), where in found.items():
        commands = sorted({identifier for identifier, _ in where})
        print(f"{name}: {detail}")
        print(f"    {len(where)} lines, on {', '.join(commands[:6])}{' ...' if len(commands) > 6 else ''}")
        for identifier, words in sorted(where, key=lambda entry: len(entry[1]))[:3]:
            print(f"    e.g. {' '.join(words)}")
    print("nothing found" if not found else f"{len(found)} kinds of violation")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
