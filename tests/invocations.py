# SPDX-License-Identifier: MPL-2.0
"""Generated invocations and what every conformant program does with them.

The kit judges an example from the catalog alone (`example_issues`). Turned around, the same judge
says of any command line whether the catalog accepts it, so a few hundred lines can be generated from
a catalog and a program held to what the contract says of each: this finds what a program does that
the text forbids and no check looks at, before an implementer reports it.

It is a test of this repository's reference program, not a part of the kit: it runs `--apply`, in a
home it made, and lines a product may not survive.

It can be pointed at another program, by whoever owns that program:

    python3 tests/invocations.py [--lines N] [--apply] [--reference] [--format-variable NAME]
                                 [--timeout SECONDS] [--budget SECONDS] PROGRAM [ARG...]

Each line runs in a directory and a home made for it. A delegate, a `passthrough` command and a stream
command are never run. Lines carrying `--apply` are left out unless `--apply` is given: with it the
program is trusted to write only under the directory and the home it is given. `--format-variable` names the
environment variable by which the program lets the environment pick its default format (`MAELYS_CLI_FORMAT`):
the lines are then run a second time with it set to `json`. `--lines` sets the random lines drawn per
command, on top of those every command gets, not the number of runs.

Each run is given `--timeout` seconds (30), and one that takes longer is reported as `timeout`. `--budget`
bounds the whole campaign: once it is spent, what was found so far is reported and the campaign is said
incomplete. Exit 0: complete, nothing found; 1: something found; 3: incomplete, nothing found in what ran,
which is no pass.

It judges what it observes: the exit code, the two streams, and the files left under the directory and the
home it gave. A line that runs a command which writes nothing there, writes elsewhere, or removes what it
wrote escapes it: "--help never runs the command" is checked as "--help leaves no file". It reads the catalog
with the kit's own reader, so a misreading the two share is seen only by another implementation; each one
found is kept as a case of its own in tests/test_invariants.py.
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
import time

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


WRONG = ("no-such-choice", "maybe", "-1", "+1", "x", "relative/path", "md5:00", "sha256:ab", "abc", "ABCDEF", "!",
         "99999999", "1.5M", "1KiB", "1m", "16777216T", "5", "1h30m", "5S", "213503982335d", "9223372036854775808",
         "18446744073709551616", "\u0663", "\u0661M", "\u0665s", "0x10", "1e1", "")


def invalid_values(declaration: dict) -> list[str]:
    """Values the declared kind refuses, one of each way of being wrong the judge of section 3 can tell: a digit
    of another script, a number beyond 64 bits, a digest too short, a suffix or a unit that is none."""
    return [value for value in WRONG if value_problem(declaration, value)]


def invalid_value(declaration: dict) -> str | None:
    """A value the declared kind refuses, or None when the judge cannot tell one."""
    return next(iter(invalid_values(declaration)), None)


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
    # no short option: one dash and more is refused before `--`, `-` alone and anything after `--` are operands
    found += [base + ["-x"], base + ["-h"], base + ["-5"], base + ["-"], base + ["--", "-x"]]
    # two options that set the same thing: the last one written wins
    found += [base + ["--json", "--format", "text"], base + ["--format", "text", "--json"],
              base + ["--json", "--compact", "--pretty"], base + ["--json", "--pretty", "--compact"]]
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
        found += [base + [item["long"], wrong] for wrong in invalid_values(item.get("argument") or {"type": "boolean"})
                  if item.get("argument")]
    for place, item in enumerate(command["input"]["operands"]):
        if item.get("type"):
            given = [valid_value(entry) or "kit" for entry in command["input"]["operands"][:place]]
            found += [list(command["pattern"]) + given + [wrong] + base[len(command["pattern"]) + len(operands):]
                      for wrong in invalid_values(item) if not wrong.startswith("-")]
    for _ in range(count):
        line = list(command["pattern"])
        line += operands[:rng.choice([len(operands)] * 4 + [max(0, len(operands) - 1)])]
        for item in rng.sample(options, k=rng.randint(0, len(options))):
            line += spelled(item, wrong=rng.random() < 0.15)
        line += rng.choice(RENDERINGS) if rng.random() < 0.6 else []
        line += rng.choice([[], [], [], ["--help"], ["--version"], ["--no-such-option"], ["kit-extra-operand"]])
        found.append(line)
    return [line for line in found if line]


def implicit_lines(command: dict, global_options: list[dict], explicit: list[list[str]]) -> list[tuple[list[str], list[str]]]:
    """Section 8: for the default command, each of its lines written without its pattern, paired with the same
    words after the pattern. The options come first, the operands after `--`; a line whose first word would be
    `--help` or `--version` is left out, those words selecting help and version in first place. A copy of each
    with a bare word before `--` is paired with None: that word must be refused."""
    pattern = list(command["pattern"])
    valued = {item["long"] for item in command["input"]["options"] + global_options if item.get("argument")}
    pairs, seen = [], set()
    for words in explicit:
        if words[:len(pattern)] != pattern:
            continue
        rest = words[len(pattern):]
        head, tail = (rest[:rest.index("--")], rest[rest.index("--") + 1:]) if "--" in rest else (rest, [])
        options, operands, index = [], [], 0
        while index < len(head):
            word = head[index]
            if word.startswith("-") and word != "-":
                options.append(word)
                if word in valued and "=" not in word and index + 1 < len(head):
                    options.append(head[index + 1])
                    index += 1
            else:
                operands.append(word)
            index += 1
        implicit = options + (["--", *operands, *tail] if operands or tail else [])
        if implicit[:1] in (["--help"], ["--version"]) or tuple(implicit) in seen:
            continue
        seen.add(tuple(implicit))
        pairs.append((implicit, pattern + implicit))
        if options and not (options[0] in valued and len(options) == 1):
            # a bare word right after the first option, or after its value when it takes one; a first option
            # whose value is missing would take the word for it, and the line would be right
            place = 2 if options[0] in valued else 1
            pairs.append((options[:place] + ["kit-bare-word"] + options[place:] + implicit[len(options):], None))
    return pairs


def implicit_violations(default: str, implicit: list[str], done, explicit_done) -> list[str]:
    """What a line that names no command does that section 8 forbids: answer otherwise than the same line after
    the default command's pattern, or take a bare word before `--` for an operand."""
    if explicit_done is not None:
        # a success is the same bytes; a refusal the same code, the order of the refusals within a step being open
        same = (done.returncode, done.stdout, done.stderr) == (explicit_done.returncode, explicit_done.stdout,
                                                              explicit_done.stderr) if done.returncode != 1 \
            else (explicit_done.returncode == 1 and done.stdout == explicit_done.stdout == ""
                  and failure_code(done.stderr) == failure_code(explicit_done.stderr))
        if not same:
            return [f"implicit-differs: the line answers otherwise than after the pattern of {default}"]
        return []
    if done.returncode != 1 or failure_code(done.stderr) != "VALIDATION_FAILED":
        return [f"implicit-absorbs: a bare word before -- is taken as an operand of {default} (exit {done.returncode})"]
    if done.stderr.lstrip().startswith("{") and json.loads(done.stderr).get("command") != default:
        return [f"implicit-absorbs: the refusal of a bare word does not name {default}"]
    return []


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


def given(command: dict, global_options: list[dict], words: list[str]) -> list[tuple[str, str | None]]:
    """The options a line gives before `--`, each with its value or None: a word an option takes as its value
    is that value and no option, `--label --help` giving --label the value `--help` (section 8)."""
    valued = {item["long"] for item in command["input"]["options"] + global_options if item.get("argument")}
    before, options, index = before_separator(words), [], 0
    while index < len(before):
        name, equals, value = before[index].partition("=")
        if name in valued and not equals:
            options.append((name, before[index + 1] if index + 1 < len(before) else None))
            index += 1
        elif name.startswith("--"):
            options.append((name, value if equals else None))
        index += 1
    return options


def open_reading(options: list[tuple[str, str | None]], default: str) -> bool:
    """A line the contract does not settle: `--json=false` where the environment selects json is a choice of
    text for one implementation and a flag not given for another."""
    return default == "json" and ("--json", "false") in options


def flag(options: list[tuple[str, str | None]], long: str) -> bool:
    """Whether a flag is given: `--flag` or `--flag=true`; `--flag=false` is a flag not given (section 2)."""
    return (long, None) in options or (long, "true") in options


def failure_code(stderr: str) -> str | None:
    """The error code of a failure, read from the envelope (json and jsonl) or from `PROGRAM: [CODE] message`."""
    if stderr.lstrip().startswith("{"):
        try:
            return json.loads(stderr)["error"]["code"]
        except (ValueError, KeyError, TypeError):
            return None
    match = re.search(r"\[([A-Z][A-Z0-9_]*)\]", stderr)
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
    options = given(command, global_options, words)
    code, out, err = completed.returncode, completed.stdout, completed.stderr
    # section 8: of the options that set the format, the last one written wins
    chosen = default
    for name, value in options:
        if name == "--format" and value is not None:
            chosen = value
        elif name == "--json" and value in (None, "true"):
            chosen = "json"
    json_mode, formats = chosen == "json", [chosen]
    asks = flag(options, "--help")
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
    if not flag(options, "--apply") and written:
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
        # section 8: a product MAY add codes of its own domain, well formed; the reference program adds none
        given_code = body.get("error", {}).get("code")
        if code == 1 and reference and given_code not in CODES:
            found.append(f"error-code: {given_code!r} is not a code of section 8, which the reference program keeps to")
        elif code == 1 and not re.fullmatch(r"[A-Z][A-Z0-9_]*", str(given_code)):
            found.append(f"error-code: {given_code!r} is not a well-formed code")
    fields = [value for name, value in options if name == "--field"]
    records = command["outputMode"] == "json-records" or bool(fields)
    if reference and code != 1 and out == "" and not records:
        found.append("success-silent: a success of a json-envelope command prints nothing")
    # an option of the command may ask for a diagnostic of its own; of the trunk, only --verbose in text mode does
    text_mode = not json_mode and formats[-1:] != ["jsonl"]
    own = {item["long"] for item in command["input"]["options"]}
    if code != 1 and err != "" and not (text_mode and flag(options, "--verbose")) \
            and not any(name in own for name, _ in options):
        found.append("success-stderr: a success writes to stderr, which only --verbose in text mode allows here")
    if asks:
        # section 8: what one option says alone is judged before --help, what the line lacks as a whole is not,
        # and the rendering is that of help, which is not records
        if alone and failure_code(err) != "VALIDATION_FAILED":
            found += [f"accepts: {kind(issue)}, under --help" for issue in alone]
        field = bool(fields)
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
    field = fields[0] if fields else None
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
         "a word that starts with one dash",
         "a flag with a value that is not true or false", "a value that is not of the declared kind"}


def kind(issue: str) -> str:
    """The rule an issue of `example_issues` is about, without the words of the line."""
    for needle, rule in (("starts with one dash", "a word that starts with one dash"),
                         ("--version is not an option", "--version after a command"),
                         ("operands where", "a wrong number of operands"), ("is not an option", "an undeclared option"),
                         ("is required", "a missing required option"), ("not repeatable", "a repeated option"),
                         ("has no value", "an option without its value"), ("requires", "an unmet requires"),
                         ("conflicts with", "a conflict"), ("does not hold", "a broken constraint"),
                         ("is a flag", "a flag with a value that is not true or false")):
        if needle in issue:
            return rule
    return "a value that is not of the declared kind"


def fresh(sandbox: pathlib.Path) -> pathlib.Path:
    """The sandbox emptied, its home and working directories made again: every run starts from the same state."""
    for name in ("home", "work"):
        shutil.rmtree(sandbox / name, ignore_errors=True)
        (sandbox / name).mkdir()
    return sandbox


class Exhausted(Exception):
    """The campaign's budget is spent."""


def main(argv: list[str]) -> int:
    """Run the generated lines against a program and print what it does that the contract forbids."""
    count, with_apply, reference, variable, timeout, budget = 10, False, False, None, 30.0, None
    while argv and argv[0] in ("--lines", "--apply", "--reference", "--format-variable", "--timeout", "--budget"):
        if argv[0] == "--lines":
            count, argv = int(argv[1]), argv[2:]
        elif argv[0] == "--timeout":
            timeout, argv = float(argv[1]), argv[2:]
        elif argv[0] == "--budget":
            budget, argv = float(argv[1]), argv[2:]
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
    deadline = time.monotonic() + budget if budget is not None else None

    def run(words: list[str], sandbox: pathlib.Path, default: str = "text") -> subprocess.CompletedProcess:
        home = sandbox / "home"
        env = {**kept, "NO_COLOR": "1", "PAGER": "", "HOME": str(home), "XDG_DATA_HOME": str(home / ".local/share"),
               "XDG_CONFIG_HOME": str(home / ".config"), "ZDOTDIR": str(home)}
        if variable and default != "text":
            env[variable] = default
        allowed = timeout
        if deadline is not None:
            allowed = min(timeout, deadline - time.monotonic())
            if allowed <= 0:
                raise Exhausted
        try:
            return subprocess.run([*program, *words], cwd=sandbox / "work", env=env, stdin=subprocess.DEVNULL,
                                  capture_output=True, text=True, timeout=allowed, check=False)
        except subprocess.TimeoutExpired:
            if allowed < timeout:
                raise Exhausted from None
            raise
    found: dict[tuple[str, str], list[tuple[str, list[str]]]] = collections.OrderedDict()
    slow = ("timeout", f"the line did not finish in {timeout:g} seconds")
    total, left_out, incomplete = 0, [], ""
    with tempfile.TemporaryDirectory(prefix="agent-cli-lines-") as directory:
        sandbox = pathlib.Path(directory)
        for name in ("home", "work"):
            (sandbox / name).mkdir()
        catalog: dict = {"commands": []}
        try:
            try:
                catalog = json.loads(run(["describe", "--format", "json"], sandbox).stdout)["data"]
            except subprocess.TimeoutExpired:
                found.setdefault(slow, []).append(("describe", ["describe", "--format", "json"]))
                raise Exhausted("describe did not finish, and the catalog is the campaign's source") from None
            # known before anything runs, so that a campaign cut short counts and names them as a whole one does
            left_out = [command["id"] for command in catalog["commands"] if opaque(command)]
            for words in unknown_lines():
                try:
                    completed = run(words, sandbox)
                except subprocess.TimeoutExpired:
                    found.setdefault(slow, []).append(("unknown", words))
                    continue
                total += 1
                for violation in unknown_violations(words, completed):
                    name, detail = violation.split(": ", 1)
                    found.setdefault((name, detail), []).append(("unknown", words))
            default = next((command for command in catalog["commands"] if command["id"] == catalog.get("defaultCommand")), None)
            if default is not None and not opaque(default):
                # a line that names no command runs the default command: an owner's tool, as every other line here
                for implicit, explicit in implicit_lines(default, catalog["globalOptions"],
                                                         lines(default, random.Random(2130), count)):
                    if flag(given(default, catalog["globalOptions"], implicit), "--apply") and not with_apply:
                        continue
                    # each from the same empty state: under --apply the first may write what the second would find
                    try:
                        done = run(implicit, fresh(sandbox))
                        again = run(explicit, fresh(sandbox)) if explicit is not None else None
                    except subprocess.TimeoutExpired:
                        found.setdefault(slow, []).append((default["id"], implicit))
                        continue
                    total += 1
                    for violation in implicit_violations(default["id"], implicit, done, again):
                        name, detail = violation.split(": ", 1)
                        found.setdefault((name, detail), []).append((default["id"], implicit))
            for default in ["text"] + (["json"] if variable else []):
                rng = random.Random(2130)
                for command in catalog["commands"]:
                    if opaque(command):
                        continue
                    for words in lines(command, rng, count):
                        options = given(command, catalog["globalOptions"], words)
                        if flag(options, "--apply") and not with_apply or open_reading(options, default):
                            continue
                        try:
                            completed = run(words, fresh(sandbox), default)
                        except subprocess.TimeoutExpired:
                            found.setdefault(slow, []).append((command["id"], words))
                            continue
                        written = sorted(str(path.relative_to(sandbox)) for path in sandbox.rglob("*") if path.is_file())
                        total += 1
                        for violation in violations(command, catalog["globalOptions"], words, completed, written, reference,
                                                    default):
                            name, detail = violation.split(": ", 1)
                            detail = re.sub(r"wrote \[.*?\]", "wrote files", detail) + (f" [{variable}={default}]" if default != "text" else "")
                            found.setdefault((name, detail), []).append((command["id"], words))
        except Exhausted as spent:
            incomplete = str(spent) or f"the budget of {budget:g} seconds ran out after {total} lines"
    print(f"{' '.join(argv)}: {total} lines over {len(catalog['commands']) - len(left_out)} commands"
          + (f"; not run: {', '.join(left_out)}" if left_out else "") + ("" if with_apply else "; no line with --apply"))
    for (name, detail), where in found.items():
        commands = sorted({identifier for identifier, _ in where})
        print(f"{name}: {detail}")
        print(f"    {len(where)} lines, on {', '.join(commands[:6])}{' ...' if len(commands) > 6 else ''}")
        for identifier, words in sorted(where, key=lambda entry: len(entry[1]))[:3]:
            print(f"    e.g. {' '.join(words)}")
    if incomplete:
        print(f"campaign incomplete: {incomplete}")
    print(f"{len(found)} kinds of violation" if found else "nothing found in what ran" if incomplete else "nothing found")
    return 1 if found else 3 if incomplete else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
