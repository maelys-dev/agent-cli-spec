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
import sys

BREAK = os.environ.get("CONFORMANT_BREAK", "")
PROGRAM = "conformant"
EXIT_CODES = {"0": "command completed", "1": "execution failed", "2": "valid report with violations"}


def option(long, summary, argument=None, default=None):
    item = {"long": long, "required": False, "repeatable": False, "summary": summary, "requires": [], "conflictsWith": []}
    if argument:
        item["argument"] = argument
    if default is not None:
        item["default"] = default
    return item


GLOBAL_OPTIONS = [
    option("--format", "Rendering.", {"name": "VALUE", "type": "choice", "choices": ["text", "json", "jsonl"]}, "text"),
    option("--json", "Alias of --format json."), option("--compact", "One line."), option("--pretty", "Indent."),
    option("--non-interactive", "Never prompt."),
    option("--color", "Colors.", {"name": "VALUE", "type": "choice", "choices": ["auto", "always", "never"]}, "auto"),
    option("--help", "Help."),
]


def command(identifier, pattern, usage, purpose, effect, operands=(), options=(), hidden=False, mode="json-envelope"):
    return {"id": identifier, "pattern": pattern, "usage": usage, "purpose": purpose, "effect": effect,
            "outputMode": mode, "external": False, "hidden": hidden, "available": True,
            "input": {"synopsis": usage, "operands": list(operands), "options": list(options), "constraints": [],
                      "passthrough": False},
            "outputSchema": {"type": "object"}, "exitCodes": dict(EXIT_CODES)}


CATALOG = [
    command("help", ["help"], "help [COMMAND_ID] | --help", "Help.", "read",
            [{"name": "COMMAND_ID", "required": False, "variadic": False, "summary": "Identifier."}]),
    command("version", ["version"], "version | --version", "Identity.", "read"),
    command("describe", ["describe"], "describe [COMMAND_ID] [--summary]", "Catalog.", "read",
            [{"name": "COMMAND_ID", "required": False, "variadic": False, "summary": "Identifier."}],
            [option("--summary", "Without schemas.")]),
    command("completion", ["completion"], "completion SHELL", "Completion script.", "read",
            [{"name": "SHELL", "required": True, "variadic": False, "summary": "Shell.", "type": "choice",
              "choices": ["bash", "zsh", "fish"]}]),
    command("complete.candidates", ["__complete"], "__complete -- WORDS...", "Candidates.", "read",
            [{"name": "WORDS", "required": False, "variadic": True, "summary": "Words."}], hidden=True, mode="json-records"),
    command("note.write", ["note", "write"], "note write FILE [--apply]", "Store a note.", {"plan": "preview", "apply": "apply"},
            [{"name": "FILE", "required": True, "variadic": False, "summary": "File.", "type": "path"}],
            [option("--apply", "Write.")]),
]
if BREAK == "exit-codes":
    CATALOG[1]["exitCodes"] = {"0": "command completed"}
if BREAK == "extra-member":
    CATALOG[1]["repository"] = "none"


def envelope(command_id, ok, exit_code, payload, compact):
    body = {"schemaVersion": 2, "contract": "agent-cli/v2", "command": command_id, "ok": ok, "exitCode": exit_code}
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


def main(argv):
    fmt, compact, words, options, passthrough = "text", False, [], {}, None
    index = 0
    while index < len(argv):
        word = argv[index]
        if word == "--":
            passthrough = argv[index + 1:]
            break
        if word.startswith("--"):
            name, _, value = word.partition("=")
            if name in ("--format", "--color") and not value:
                index += 1
                value = argv[index] if index < len(argv) else ""
            options[name] = value or True
        else:
            words.append(word)
        index += 1
    if "--json" in options or options.get("--format") == "json":
        fmt = "json"
    if options.get("--format") == "jsonl":
        fmt = "jsonl"
    compact = "--compact" in options or options.get("--pretty") == "false"
    if "--help" in options and not words:
        words = ["help"]
    if "--version" in options and not words:
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
        return fail(selected["id"], "VALIDATION_FAILED", "--dry-run is not supported: the command plans by default.", fmt, compact)
    for name in options:
        if name not in known and name != "--version":
            return fail(selected["id"], "VALIDATION_FAILED", f"Option {name} is not supported by '{selected['id']}'.", fmt, compact)
    if fmt == "jsonl" and selected["outputMode"] != "json-records":
        return fail(selected["id"], "VALIDATION_FAILED", "jsonl is for json-records commands.", fmt, compact)
    identifier = selected["id"]
    if identifier == "version":
        data = {"product": "Conformant", "program": PROGRAM, "version": "1.0.0", "contract": "agent-cli/v2",
                "cliApi": 1, "framework": "fixture"}
        text = f"{PROGRAM} 1.0.0\n"
    elif identifier == "help":
        data = {"text": "usage\n", "commands": [item["id"] for item in CATALOG if not item["hidden"]]}
        text = data["text"]
    elif identifier == "describe":
        data = {"schemaVersion": 1, "program": PROGRAM, "product": "Conformant", "version": "1.0.0",
                "contract": "agent-cli/v2", "cliApi": 1, "framework": "fixture"}
        if operands:
            if operands[0] not in by_id:
                return fail("describe", "INVALID_COMMAND", f"Unknown command identifier {operands[0]!r}.", fmt, compact)
            data["kind"], data["commands"] = "command", [by_id[operands[0]]]
        elif "--summary" in options:
            data["kind"] = "summary"
            data["commands"] = [{key: value for key, value in item.items() if key not in ("outputSchema", "exitCodes")}
                                for item in CATALOG]
        else:
            data.update({"kind": "catalog", "globalOptions": GLOBAL_OPTIONS, "invariants": ["one catalog"],
                         "output": {"contract": "agent-cli/v2", "schemaVersion": 2, "stdout": "success data only",
                                    "stderr": "diagnostics and failure envelopes"}, "commands": CATALOG})
        text = json.dumps(data, indent=2) + "\n"
    elif identifier == "completion":
        data = {"shell": operands[0] if operands else "bash", "script": f"complete -F _c {PROGRAM} # __complete\n"}
        text = data["script"]
    elif identifier == "complete.candidates":
        current = operands[-1] if operands else ""
        matching = sorted({item["pattern"][0] for item in CATALOG if not item["hidden"] and item["pattern"][0].startswith(current)})
        data = {"count": len(matching), "records": [{"word": word} for word in matching]}
        text = "".join(word + "\n" for word in matching)
    else:
        data = {"mode": "apply" if "--apply" in options else "plan", "changed": False}
        text = f"note: {data['mode']}\n"
    if fmt == "text":
        sys.stdout.write(text)
    elif fmt == "jsonl":
        for record in data["records"]:
            sys.stdout.write(json.dumps(record, separators=(",", ":")) + "\n")
    else:
        sys.stdout.write(envelope(identifier, True, 0, data, compact))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
