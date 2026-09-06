#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0
"""The smallest program that passes the conformance kit.

A fixture for the kit's own tests: a catalog of the built-ins plus one
transaction, the envelopes, the failures the contract prescribes, the
completion. CONFORMANT_BREAK names a deliberate defect to inject, so the
tests can prove that the kit sees it.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys

BREAK = os.environ.get("CONFORMANT_BREAK", "")
PROGRAM = "conformant"
EXIT_CODES = {"0": "command completed", "1": "execution failed", "2": "valid report with violations"}


def option(long, summary, argument=None, default=None, requires=(), conflicts=(), hidden=False):
    item = {"long": long, "required": False, "repeatable": False, "summary": summary,
            "requires": list(requires), "conflictsWith": list(conflicts)}
    if argument:
        item["argument"] = argument
    if hidden:
        item["hidden"] = True
    if default is not None:
        item["default"] = default
    return item


GLOBAL_OPTIONS = [
    option("--format", "Rendering.", {"name": "VALUE", "type": "choice", "choices": ["text", "json", "jsonl"]}, "text"),
    option("--json", "Alias of --format json."), option("--compact", "One line."), option("--pretty", "Indent."),
    option("--non-interactive", "Never prompt."), option("--verbose", "Details of the run on stderr."),
    option("--progress", "Progress on stderr.", {"name": "VALUE", "type": "choice", "choices": ["auto", "always", "never"]},
           "auto"),
    option("--pager", "Pager on a terminal.", {"name": "VALUE", "type": "choice", "choices": ["auto", "always", "never"]},
           "auto"),
    option("--color", "Colors.", {"name": "VALUE", "type": "choice", "choices": ["auto", "always", "never"]}, "auto"),
    option("--help", "Help."),
]


def command(identifier, pattern, usage, purpose, effect, operands=(), options=(), constraints=(), hidden=False,
            mode="json-envelope"):
    return {"id": identifier, "pattern": pattern, "usage": usage, "purpose": purpose, "effect": effect,
            "outputMode": mode, "external": False, "hidden": hidden, "available": True,
            "input": {"synopsis": usage, "operands": list(operands), "options": list(options),
                      "constraints": list(constraints),
                      "passthrough": False},
            "outputSchema": {"type": "object"}, "exitCodes": dict(EXIT_CODES)}


CATALOG = [
    command("help", ["help"], "help [COMMAND_ID] | --help", "Help.", "read",
            [{"name": "COMMAND_ID", "required": False, "variadic": False, "summary": "Identifier."}]),
    command("version", ["version"], "version | --version", "Identity.", "read"),
    command("describe", ["describe"], "describe [COMMAND_ID] [--summary] [--prefix PREFIX]", "Catalog.", "read",
            [{"name": "COMMAND_ID", "required": False, "variadic": False, "summary": "Identifier."}],
            [option("--summary", "Without schemas."),
             option("--prefix", "Select a command namespace.",
                    {"name": "PREFIX", "type": "string",
                     "pattern": "^[a-z](?:[a-z0-9.-]*[a-z0-9-])?$"},
                    requires=["--summary"], conflicts=["COMMAND_ID"]),
             option("--trace", "Trace the catalog lookup.", hidden=True)],
            [{"kind": "requires", "options": ["--prefix", "--summary"]}]),
    command("completion", ["completion"], "completion SHELL", "Completion script.", "read",
            [{"name": "SHELL", "required": True, "variadic": False, "summary": "Shell.", "type": "choice",
              "choices": ["bash", "zsh", "fish"]}]),
    command("complete.candidates", ["__complete"], "__complete -- WORDS...", "Candidates.", "read",
            [{"name": "WORDS", "required": False, "variadic": True, "summary": "Words."}], hidden=True, mode="json-records"),
    command("note.write", ["note", "write"], "note write FILE [--apply]", "Store a note.", {"plan": "preview", "apply": "apply"},
            [{"name": "FILE", "required": True, "variadic": False, "summary": "File.", "type": "path"}],
            [option("--apply", "Write.")]),
]
offline = command("offline", ["offline"], "offline", "Unavailable in this build.", "read")
offline.update(available=False, unavailableReason="fixture build has no offline backend")
CATALOG.append(offline)
if BREAK == "exit-codes":
    CATALOG[1]["exitCodes"] = {"0": "command completed"}
if BREAK == "extra-member":
    CATALOG[1]["repository"] = "none"
if BREAK == "hidden-leak":
    CATALOG[2]["usage"] = CATALOG[2]["input"]["synopsis"] = CATALOG[2]["usage"] + " [--trace]"
if BREAK == "missing-output-schema":
    for item in CATALOG:
        item.pop("outputSchema")
if BREAK == "output-schema":
    CATALOG[1]["outputSchema"]["required"] = ["neverReturned"]


def offered(item):
    return BREAK == "hidden-leak" or not item.get("hidden")


def envelope(command_id, ok, exit_code, payload, compact):
    body = {"schemaVersion": 2, "contract": "agent-cli/v2", "command": command_id, "ok": ok, "exitCode": exit_code}
    if BREAK == "envelope-types":
        body.update(ok=int(ok), exitCode=False if exit_code == 0 else exit_code)
    if BREAK == "empty-command":
        body["command"] = ""
    body["data" if ok else "error"] = payload
    return json.dumps(body, indent=None if compact else 2, separators=(",", ":") if compact else None) + "\n"


def fail(command_id, code, message, fmt, compact):
    if BREAK == "code-drift" and code == "INVALID_COMMAND":
        code = "INVALID_PATH"
    if fmt == "text":
        sys.stderr.write(f"{PROGRAM}: [{code}] {message}\nHint: read describe.\n")
    else:
        sys.stderr.write(envelope(command_id, False, 1, {"code": code, "message": message, "hint": "read describe."}, compact))
    return 1


def record_text(records):
    columns = sorted(set().union(*(record.keys() for record in records)))
    rows = []
    for record in records:
        fields = []
        for key in columns:
            if key not in record:
                fields.append("")
            elif isinstance(record[key], str):
                value = record[key].replace("\\", "\\\\").replace("\t", "\\t").replace("\r", "\\r").replace("\n", "\\n")
                value = "".join(f"\\u{ord(char):04x}" if ord(char) < 32 or ord(char) == 127 else char for char in value)
                fields.append(value)
            else:
                fields.append(json.dumps(record[key], ensure_ascii=False, separators=(",", ":")))
        rows.append("\t".join(fields) + "\n")
    return "".join(rows)


def main(argv):
    fmt, compact, words, options, passthrough = "text", False, [], {}, None
    declarations = {item["long"]: item for item in GLOBAL_OPTIONS}
    declarations.update({item["long"]: item for command in CATALOG for item in command["input"]["options"]})
    declarations["--version"] = option("--version", "Version.")
    duplicates = []
    index = 0
    while index < len(argv):
        word = argv[index]
        if word == "--":
            passthrough = argv[index + 1:]
            break
        if word.startswith("--"):
            name, equals, value = word.partition("=")
            if declarations.get(name, {}).get("argument") and not equals:
                index += 1
                value = argv[index] if index < len(argv) else ""
            elif not equals:
                value = True
            if name in options:
                duplicates.append(name)
            options[name] = value
        else:
            words.append(word)
        index += 1
    if options.get("--json") in (True, "true") or options.get("--format") == "json":
        fmt = "json"
    if options.get("--format") == "jsonl":
        fmt = "jsonl"
    compact = options.get("--compact") in (True, "true") or options.get("--pretty") == "false"
    if options.get("--help") in (True, "true") and not words:
        words = ["help"]
    if options.get("--version") in (True, "true") and not words:
        words = ["version"]
    by_id = {item["id"]: item for item in CATALOG}
    selected = None
    for item in CATALOG:
        if words[:len(item["pattern"])] == item["pattern"]:
            selected = item
    if selected is None:
        return fail("unknown", "INVALID_COMMAND", f"Unknown command {' '.join(words)!r}.", fmt, compact)
    operands = words[len(selected["pattern"]):] + (passthrough or [])
    known = {item["long"] for item in selected["input"]["options"]} | {item["long"] for item in GLOBAL_OPTIONS}
    if isinstance(selected["effect"], dict) and ("--dry-run" in options or "--plan" in options):
        return fail(selected["id"], "VALIDATION_FAILED", "The command plans by default; use --apply to apply.", fmt, compact)
    for name in options:
        if name not in known and name != "--version":
            return fail(selected["id"], "VALIDATION_FAILED", f"Option {name} is not supported by '{selected['id']}'.", fmt, compact)
    if duplicates:
        return fail(selected["id"], "VALIDATION_FAILED", f"Duplicate option {duplicates[0]}.", fmt, compact)
    for name, value in options.items():
        argument = declarations[name].get("argument")
        if argument is None:
            if value is not True and value not in ("true", "false"):
                return fail(selected["id"], "VALIDATION_FAILED", f"{name} takes true or false.", fmt, compact)
            options[name] = value is True or value == "true"
        elif argument.get("type") == "choice" and value not in argument["choices"]:
            return fail(selected["id"], "VALIDATION_FAILED", f"Invalid choice for {name}.", fmt, compact)
    if selected["id"] == "describe" and "--prefix" in options:
        prefix = options["--prefix"]
        if not options.get("--summary"):
            return fail("describe", "VALIDATION_FAILED", "--prefix requires --summary.", fmt, compact)
        if operands:
            return fail("describe", "VALIDATION_FAILED", "--prefix conflicts with COMMAND_ID.", fmt, compact)
        if not isinstance(prefix, str) or not prefix:
            return fail("describe", "VALIDATION_FAILED", "--prefix requires PREFIX.", fmt, compact)
        if re.fullmatch(r"[a-z](?:[a-z0-9.-]*[a-z0-9-])?", prefix) is None:
            return fail("describe", "VALIDATION_FAILED", "--prefix is not a valid command prefix.", fmt, compact)
    if fmt == "jsonl" and selected["outputMode"] != "json-records":
        return fail(selected["id"], "VALIDATION_FAILED", "jsonl is for json-records commands.", fmt, compact)
    identifier = selected["id"]
    verbose = options.get("--verbose", False)
    progress = options.get("--progress", "auto")
    if progress not in ("auto", "always", "never"):
        return fail(identifier, "VALIDATION_FAILED", "--progress takes auto, always or never.", fmt, compact)
    pager = options.get("--pager", "auto")
    if pager not in ("auto", "always", "never"):
        return fail(identifier, "VALIDATION_FAILED", "--pager takes auto, always or never.", fmt, compact)
    if verbose and (fmt == "text" or BREAK == "verbose-json"):
        sys.stderr.write(f"{PROGRAM}: running {identifier}\n")
    if (progress == "always" or (progress == "auto" and sys.stderr.isatty())) and (fmt == "text" or BREAK == "progress-json"):
        sys.stderr.write("working... \rworking... done\n")
    if identifier == "version":
        data = {"product": "Conformant", "program": PROGRAM, "version": "1.0.0", "contract": "agent-cli/v2",
                "cliApi": 1, "framework": "fixture"}
        text = f"{PROGRAM} 1.0.0\n"
    elif identifier == "help":
        text = "usage\n"
        if operands and operands[0] in by_id:
            target = by_id[operands[0]]
            text = target["usage"] + "\n" + "".join(f"  {item['long']}  {item['summary']}\n"
                                                 for item in target["input"]["options"] if offered(item))
        data = {"text": text, "commands": [item["id"] for item in CATALOG if not item["hidden"]]}
    elif identifier == "describe":
        data = {"schemaVersion": 1, "program": PROGRAM, "product": "Conformant", "version": "1.0.0",
                "contract": "agent-cli/v2", "cliApi": 1, "framework": "fixture"}
        if operands:
            if operands[0] not in by_id:
                return fail("describe", "INVALID_COMMAND", f"Unknown command identifier {operands[0]!r}.", fmt, compact)
            data["kind"], data["commands"] = "command", [by_id[operands[0]]]
        elif options.get("--summary"):
            selected_commands = CATALOG
            if "--prefix" in options:
                prefix = options["--prefix"]
                selected_commands = [item for item in CATALOG
                                     if item["id"] == prefix or item["id"].startswith(prefix + ".")]
                if not selected_commands:
                    return fail("describe", "INVALID_COMMAND", f"Unknown command prefix {prefix!r}.", fmt, compact)
                data["filter"] = {"kind": "command-prefix", "value": prefix}
            data["kind"] = "summary"
            data["commands"] = [{key: value for key, value in item.items() if key not in ("outputSchema", "exitCodes")}
                                for item in selected_commands]
        else:
            data.update({"kind": "catalog", "globalOptions": GLOBAL_OPTIONS, "invariants": ["one catalog"],
                         "output": {"contract": "agent-cli/v2", "schemaVersion": 2, "stdout": "success data only",
                                    "stderr": "diagnostics and failure envelopes"}, "commands": CATALOG})
            if BREAK == "malformed-catalog":
                data["commands"] = [{"id": "version", "input": None}]
        text = json.dumps(data, indent=2) + "\n"
    elif identifier == "completion":
        data = {"shell": operands[0] if operands else "bash", "script": f"complete -F _c {PROGRAM} # __complete\n"}
        text = data["script"]
    elif identifier == "complete.candidates":
        current = operands[-1] if operands else ""
        given = operands[:-1]
        target = next((item for item in CATALOG if given and given[:len(item["pattern"])] == item["pattern"]), None)
        if target is not None and target["available"]:
            longs = {item["long"] for item in target["input"]["options"] if offered(item)}
            longs |= {item["long"] for item in GLOBAL_OPTIONS}
            matching = sorted(long for long in longs - set(given) if long.startswith(current))
        elif target is not None:
            matching = []
        else:
            matching = sorted({item["pattern"][0] for item in CATALOG
                               if not item["hidden"] and item["available"] and item["pattern"][0].startswith(current)})
        data = {"count": len(matching), "records": [{"word": word} for word in matching]}
        header = "WORD\n" if sys.stdout.isatty() or BREAK == "header-in-pipe" else ""
        text = header + record_text(data["records"])
        if BREAK == "text-garbage":
            text = "\x1b[31mgarbage\x1b[0m\n" * len(matching)
    else:
        data = {"mode": "apply" if options.get("--apply") else "plan", "changed": False}
        text = f"note: {data['mode']}\n"
    paging = fmt == "text" and pager != "never" and not options.get("--non-interactive", False) \
        and (sys.stdout.isatty() or BREAK == "pager-in-pipe" and pager == "always") \
        and os.environ.get("PAGER", "less") != ""
    if paging:
        env = dict(os.environ)
        if "PAGER" not in env:
            env.setdefault("LESS", "FRX")
        sys.stdout.flush()
        try:
            pager_command = shlex.split(env.get("PAGER", "less"))
            if pager_command:
                subprocess.run(pager_command, input=text, text=True, check=False, env=env)
            else:
                paging = False
        except (OSError, ValueError):
            paging = False
    if fmt == "text":
        if not paging:
            (sys.stderr if BREAK == "text-on-stderr" else sys.stdout).write(text)
    elif fmt == "jsonl":
        if BREAK == "jsonl-noise" and (verbose or progress == "always"):
            sys.stdout.write("diagnostic noise\n")
        for record in data["records"]:
            sys.stdout.write("not-json\n" if BREAK == "malformed-jsonl" else json.dumps(record, separators=(",", ":")) + "\n")
    else:
        sys.stdout.write(envelope(identifier, True, 0, data, compact))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
