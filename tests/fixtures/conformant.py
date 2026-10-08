#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0
"""The smallest program that passes the conformance kit.

A fixture for the kit's own tests: a catalog of the built-ins plus one
transaction, the envelopes, the failures the contract prescribes, the
completion. CONFORMANT_BREAK names a deliberate defect to inject, so the
tests can prove that the kit sees it. CONFORMANT_COMPLETION=static makes
`completion SHELL` print a script that carries its candidates instead of one
that calls `__complete`.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import subprocess
import sys

BREAK = os.environ.get("CONFORMANT_BREAK", "")
PROGRAM = "conformant"
EXIT_CODES = {"0": "command completed", "1": "execution failed", "2": "valid report with violations"}


def option(long, summary, argument=None, default=None, requires=(), conflicts=(), hidden=False, group=None):
    item = {"long": long, "required": False, "repeatable": False, "summary": summary,
            "requires": list(requires), "conflictsWith": list(conflicts)}
    if argument:
        item["argument"] = argument
    if hidden:
        item["hidden"] = True
    if group:
        item["group"] = group
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
    option("--field", "Render one member of data.", {"name": "NAME", "type": "string"}),
    option("--help", "Help."),
]


def command(identifier, pattern, usage, purpose, effect, operands=(), options=(), constraints=(), hidden=False,
            mode="json-envelope", passthrough=False, external=False, protocol=None):
    entry = {"id": identifier, "pattern": pattern, "usage": usage, "purpose": purpose, "effect": effect,
             "outputMode": mode, "external": external, "hidden": hidden, "available": True,
             "input": {"synopsis": usage, "operands": list(operands), "options": list(options),
                       "constraints": list(constraints),
                       "passthrough": passthrough},
             "outputSchema": {"type": "object"}, "exitCodes": dict(EXIT_CODES)}
    if protocol:
        entry["protocol"] = protocol
    return entry


CATALOG = [
    command("help", ["help"], "help [COMMAND_ID] | --help", "Help.", "read",
            [{"name": "COMMAND_ID", "required": False, "variadic": False, "summary": "Identifier."}]),
    command("version", ["version"], "version | --version", "Identity.", "read"),
    command("describe", ["describe"], "describe [COMMAND_ID] [--summary] [--prefix PREFIX]", "Catalog.", "read",
            [{"name": "COMMAND_ID", "required": False, "variadic": False, "summary": "Identifier."}],
            [option("--summary", "Without schemas."),
             option("--prefix", "Select a command namespace.",
                    {"name": "PREFIX", "type": "string",
                     "pattern": "^[a-z]([a-z0-9.-]*[a-z0-9-])?$"},
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
# Every member the contract allows, so that the schema and the kit meet each of them once.
CATALOG.append(command(
    "limits", ["limits"], "limits TARGET [REF] [LABEL] [SUM] [COUNT...] [--lenient|--strict] [--paired-a --paired-b]",
    "Exercise every declaration the contract allows.", "read",
    [{"name": "TARGET", "required": True, "variadic": False, "summary": "Target.", "type": "choice",
      "choices": ["near", "far"]},
     {"name": "REF", "required": False, "variadic": False, "summary": "A digest of either width.",
      "type": "digest", "algorithms": ["sha256", "sha1"], "digits": [40, 64]},
     {"name": "LABEL", "required": False, "variadic": False, "summary": "A matched label.",
      "type": "string", "pattern": "^[a-z][a-z0-9-]*$"},
     {"name": "SUM", "required": False, "variadic": False, "summary": "A fixed-width hex sum.",
      "type": "hex", "digits": 64},
     {"name": "COUNT", "required": False, "variadic": True, "summary": "Counts.", "type": "unsigned",
      "minimum": 0, "maximum": 64, "x-unit": "items"}],
    [option("--lenient", "Loosen.", conflicts=["--strict"]),
     option("--strict", "Tighten.", conflicts=["--lenient"]),
     option("--paired-a", "First of the pair.", group="pair"),
     option("--paired-b", "Second of the pair.", group="pair"),
     option("--digest", "A digest of either width.",
            {"name": "DIGEST", "type": "digest", "algorithms": ["sha256", "sha1"], "digits": [40, 64]}),
     option("--sum", "A fixed-width hex sum.", {"name": "SUM", "type": "hex", "digits": 64}),
     option("--budget", "A size.", {"name": "SIZE", "type": "size"}, "1M"),
     option("--wait", "A duration.", {"name": "WAIT", "type": "duration"}, "5s"),
     option("--root", "An absolute path.", {"name": "ROOT", "type": "absolute-path"}),
     option("--name", "A matched name.", {"name": "NAME", "type": "string", "pattern": "^[a-z][a-z0-9-]*$"}),
     option("--depth", "A bounded integer.", {"name": "DEPTH", "type": "integer", "minimum": -8, "maximum": 8}),
     option("--report", "Where the report goes.", {"name": "FILE", "type": "path"}, requires=["--strict"]),
     option("--sha", "A sha256.", {"name": "SHA", "type": "sha256", "x-hint": "lowercase"}),
     option("--signed", "An explicit boolean.", {"name": "FLAG", "type": "boolean"}, "true")],
    [{"kind": "at-most-one", "options": ["--lenient", "--strict"]},
     {"kind": "all-or-none", "options": ["--paired-a", "--paired-b"]},
     {"kind": "exactly-one", "options": ["--digest", "--sum"], "x-note": "one width or the other"},
     {"kind": "requires", "options": ["--report", "--strict"]}],
    passthrough=True))
CATALOG.append(command("serve", ["serve"], "serve", "Hand stdio to a protocol.", "stream",
                       mode="protocol-stream", protocol="mcp-json-rpc"))
CATALOG.append(command("tool", ["tool"], "tool -- ARGS...", "Delegate to a child.", "execute",
                       mode="protocol-stream", external=True, passthrough=True))
CATALOG.append(command("note.commit", ["note", "commit"], "note commit FILE [--apply]", "Record a commit.",
                       {"plan": "preview", "apply": "commit", "x-proof": "revision"},
                       [{"name": "FILE", "required": True, "variadic": False, "summary": "File.", "type": "path"}],
                       [option("--apply", "Commit.")]))
CATALOG[-4]["input"]["x-form"] = "exhaustive"
CATALOG[-4]["x-since"] = "2.4.1"

CATALOG.append(command("completion.install", ["completion", "install"], "completion install SHELL [--apply]",
                       "Install the completion script.", {"plan": "preview", "apply": "apply"},
                       [{"name": "SHELL", "required": True, "variadic": False, "summary": "Shell.", "type": "choice",
                         "choices": ["bash", "zsh", "fish"]}],
                       [option("--apply", "Write the script and the startup block."),
                        option("--expect", "Apply only the plan that carries this fingerprint.",
                               {"name": "FINGERPRINT", "type": "digest", "algorithms": ["sha256"], "digits": 64},
                               requires=["--apply"])],
                       [{"kind": "requires", "options": ["--expect", "--apply"]}]))
CATALOG[-1]["outputSchema"] = {"type": "object",
                               "required": ["mode", "shell", "files", "catalog", "activate", "fingerprint"],
                               "properties": {"changed": {"type": "boolean"}}}
if BREAK == "expect-without-fingerprint":
    CATALOG[-1]["outputSchema"]["required"].remove("fingerprint")
for transaction in ("note.write", "note.commit"):
    next(item for item in CATALOG if item["id"] == transaction)["outputSchema"] = {
        "type": "object", "required": ["mode", "changed"]}

EXAMPLES = {
    "describe": [{"words": ["describe", "--summary", "--prefix", "note"], "summary": "List the note commands."},
                 {"words": ["describe", "note.write", "--format", "json"], "summary": "Describe one command."}],
    "note.write": [{"words": ["note", "write", "notes/today.txt"], "summary": "Plan the note."},
                   {"words": ["note", "write", "notes/today.txt", "--apply"], "summary": "Write the note.",
                    "x-since": "2.11.0"}],
    "completion.install": [{"words": ["completion", "install", "zsh", "--apply", "--expect", "sha256:" + "ab" * 32],
                            "summary": "Install the completion the plan showed."}],
    "tool": [{"words": ["tool", "--version"], "summary": "Ask the child its version."}],
}
if BREAK == "example-unknown-option":
    EXAMPLES["note.write"][1]["words"].append("--force")
if BREAK == "example-missing-operand":
    EXAMPLES["note.write"][0]["words"].pop()
if BREAK == "example-bad-choice":
    EXAMPLES["completion.install"][0]["words"][2] = "tcsh"
if BREAK == "example-unmet-requires":
    EXAMPLES["describe"][0]["words"].remove("--summary")
if BREAK == "example-other-command":
    EXAMPLES["note.write"][0]["words"][1] = "commit"
for item in CATALOG:
    if item["id"] in EXAMPLES:
        item["examples"] = EXAMPLES[item["id"]]

offline = command("offline", ["offline"], "offline", "Unavailable in this build.", "read")
offline.update(available=False, unavailableReason="fixture build has no offline backend")
CATALOG.append(offline)
if BREAK == "exit-codes":
    CATALOG[1]["exitCodes"] = {"0": "command completed"}
if BREAK == "extra-member":
    CATALOG[1]["repository"] = "none"
if BREAK == "delegate-stream":
    next(item for item in CATALOG if item["external"])["effect"] = "stream"
if BREAK == "delegate-protocol":
    next(item for item in CATALOG if item["external"])["protocol"] = "mcp-json-rpc"
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


def fail(command_id, code, message, fmt, compact, hint="read describe."):
    if BREAK == "code-drift" and code == "INVALID_COMMAND":
        code = "INVALID_PATH"
    if fmt == "text":
        sys.stderr.write(f"{PROGRAM}: [{code}] {message}\nHint: {hint}\n")
    else:
        sys.stderr.write(envelope(command_id, False, 1, {"code": code, "message": message, "hint": hint}, compact))
    return 1


SHELLS = ("bash", "zsh", "fish")
VERSION = "1.0.0"

DYNAMIC = {
    "bash": r"""# bash completion for @PROG@
_@FN@_complete() {
    local -a words
    words=("${COMP_WORDS[@]:1:COMP_CWORD}")
    local IFS=$'\n'
    COMPREPLY=($(@PROG@ __complete -- "${words[@]}" 2>/dev/null))
@STALE@@FALLBACK@}
complete -o filenames -F _@FN@_complete @PROG@
""",
    "zsh": r"""#compdef @PROG@
# zsh completion for @PROG@: source it after compinit
_@FN@() {
    local -a candidates
    candidates=("${(@f)$(@PROG@ __complete -- "${(@)words[2,CURRENT]}" 2>/dev/null)}")
    [[ -n ${candidates[1]} ]] || candidates=()
@STALE@@FALLBACK@}
compdef _@FN@ @PROG@
""",
    "fish": r"""# fish completion for @PROG@
function __@FN@_complete
    set -l tokens (commandline -opc)
    set -l cur (commandline -ct)
    set -l out (@PROG@ __complete -- $tokens[2..-1] "$cur" 2>/dev/null)
@STALE@@FALLBACK@end
complete -c @PROG@ -f -a '(__@FN@_complete)'
""",
}
STALE = {
    "bash": "    [ ${#COMPREPLY[@]} -eq 0 ] || COMPREPLY[${#COMPREPLY[@]}]=stale-word\n",
    "zsh": "    (( ${#candidates} )) && candidates+=(stale-word)\n",
    "fish": "    test (count $out) -gt 0; and set -a out stale-word\n",
}
FALLBACK = {
    "bash": """    if [ ${#COMPREPLY[@]} -eq 0 ]; then
        COMPREPLY=($(compgen -f -- "${COMP_WORDS[COMP_CWORD]}"))
    fi
""",
    "zsh": """    if (( ${#candidates} )); then compadd -a candidates; else _files; fi
""",
    "fish": """    if test (count $out) -gt 0
        printf '%s\\n' $out
    else
        __fish_complete_path "$cur"
    end
""",
}
NO_FALLBACK = {"bash": "", "zsh": "    compadd -a candidates\n", "fish": "    printf '%s\\n' $out\n"}

# A script that carries its candidates: one row per command, in catalog order, `words|kind|pattern|options`.
STATIC = {
    "bash": r"""# bash completion for @PROG@@STAMP@
_@FN@_complete() {
    local IFS=' ' cur="${COMP_WORDS[COMP_CWORD]}" count=$((COMP_CWORD - 1)) n kind pat longs word found=""
    local -a given words
    given=("${COMP_WORDS[@]:1:count}")
    words=("${COMP_WORDS[@]:1:COMP_CWORD}")
    COMPREPLY=()
    while IFS='|' read -r n kind pat longs; do
        [ "$count" -ge "$n" ] || continue
        [ "${given[*]:0:n}" = "$pat" ] || continue
        found=$kind
        break
    done <<'CATALOG'
@ROWS@
CATALOG
    case "$found" in
        options)
            for word in $longs; do
                case "$word" in -*) case " ${given[*]} " in *" $word "*) continue ;; esac ;; esac
                case "$word" in "$cur"*) COMPREPLY[${#COMPREPLY[@]}]=$word ;; esac
            done ;;
        none) ;;
        delegate)
            IFS=$'\n'
            COMPREPLY=($(@PROG@ __complete -- "${words[@]}" 2>/dev/null)) ;;
        *)
            for word in @TOP@; do
                case "$word" in "$cur"*) COMPREPLY[${#COMPREPLY[@]}]=$word ;; esac
            done ;;
    esac
    if [ ${#COMPREPLY[@]} -eq 0 ]; then
        IFS=$'\n'
        COMPREPLY=($(compgen -f -- "$cur"))
    fi
}
complete -o filenames -F _@FN@_complete @PROG@
""",
    "zsh": r"""#compdef @PROG@
# zsh completion for @PROG@@STAMP@: source it after compinit
_@FN@() {
    local cur=${words[CURRENT]} row n kind pat longs word found=
    local -a given candidates parts
    given=("${(@)words[2,CURRENT-1]}")
    for row in @ROWS@; do
        parts=("${(@s:|:)row}")
        n=$parts[1]
        (( ${#given} >= n )) || continue
        [[ "${(j: :)given[1,n]}" == "$parts[3]" ]] || continue
        found=$parts[2]
        longs=$parts[4]
        break
    done
    case $found in
        options)
            for word in ${=longs}; do
                [[ $word == -* ]] && (( ${given[(Ie)$word]} )) && continue
                [[ $word == "$cur"* ]] && candidates+=($word)
            done ;;
        none) ;;
        delegate)
            candidates=("${(@f)$(@PROG@ __complete -- "${(@)words[2,CURRENT]}" 2>/dev/null)}")
            [[ -n ${candidates[1]} ]] || candidates=() ;;
        *)
            for word in @TOP@; do
                [[ $word == "$cur"* ]] && candidates+=($word)
            done ;;
    esac
    if (( ${#candidates} )); then compadd -a candidates; else _files; fi
}
compdef _@FN@ @PROG@
""",
    "fish": r"""# fish completion for @PROG@@STAMP@
function __@FN@_complete
    set -l tokens (commandline -opc)
    set -l cur (commandline -ct)
    set -l given $tokens[2..-1]
    set -l found ""
    set -l longs
    set -l out
    for row in @ROWS@
        set -l parts (string split -- '|' $row)
        test (count $given) -ge $parts[1]; or continue
        test (string join -- ' ' $given[1..$parts[1]]) = "$parts[3]"; or continue
        set found $parts[2]
        set longs (string split -- ' ' $parts[4])
        break
    end
    switch "$found"
        case options
            for word in $longs
                if string match -q -- '-*' $word; and contains -- $word $given
                    continue
                end
                string match -q -- "$cur*" $word; and set -a out $word
            end
        case none
        case delegate
            set out (@PROG@ __complete -- $given "$cur" 2>/dev/null)
        case '*'
            for word in @TOP@
                string match -q -- "$cur*" $word; and set -a out $word
            end
    end
    if test (count $out) -gt 0
        printf '%s\n' $out
    else
        __fish_complete_path "$cur"
    end
end
complete -c @PROG@ -f -a '(__@FN@_complete)'
""",
}


def candidate_words(item):
    """What `__complete` offers after a command's pattern: its visible options, the global ones, and after
    `help` and `describe` the identifiers of the commands a human can be shown (section 6)."""
    words = {entry["long"] for entry in item["input"]["options"] if offered(entry)}
    words |= {entry["long"] for entry in GLOBAL_OPTIONS}
    if item["id"] in ("help", "describe"):
        words |= {entry["id"] for entry in CATALOG
                  if not entry["hidden"] and (entry["available"] or BREAK == "identifier-unavailable")}
    return words


def completion_script(shell):
    """The script of `completion SHELL`: it calls `__complete`, or carries the catalog's candidates."""
    function = PROGRAM.replace("-", "_")
    static = os.environ.get("CONFORMANT_COMPLETION") == "static" or BREAK == "completion-static-no-version"
    if not static:
        text = DYNAMIC[shell]
        text = text.replace("@STALE@", STALE[shell] if BREAK == "completion-stale-word" else "")
        text = text.replace("@FALLBACK@", NO_FALLBACK[shell] if BREAK == "completion-no-fallback" else FALLBACK[shell])
        return text.replace("@PROG@", PROGRAM).replace("@FN@", function)
    rows = []
    for item in CATALOG:
        kind = "delegate" if item["external"] else "options" if item["available"] else "none"
        longs = sorted(candidate_words(item))
        rows.append(f"{len(item['pattern'])}|{kind}|{' '.join(item['pattern'])}|{' '.join(longs)}")
    top = sorted({item["pattern"][0] for item in CATALOG if not item["hidden"] and item["available"]})
    stamp = "" if BREAK == "completion-static-no-version" else f", carrying the candidates of catalog version {VERSION}"
    text = STATIC[shell].replace("@STAMP@", stamp).replace("@TOP@", " ".join(top))
    text = text.replace("@ROWS@", "\n".join(rows) if shell == "bash" else " ".join(f"'{row}'" for row in rows))
    return text.replace("@PROG@", PROGRAM).replace("@FN@", function)


def install_completion(shell, apply):
    """`completion install SHELL`: the plan names every path and writes nothing; --apply writes."""
    home = os.environ.get("HOME") or os.path.expanduser("~")
    if shell == "fish":
        config = os.environ.get("XDG_CONFIG_HOME") or os.path.join(home, ".config")
        script_path, rc_path = os.path.join(config, "fish", "completions", f"{PROGRAM}.fish"), None
    else:
        data_home = os.environ.get("XDG_DATA_HOME") or os.path.join(home, ".local", "share")
        script_path = os.path.join(data_home, PROGRAM, f"completion.{shell}")
        rc_path = os.path.join(home, ".bashrc") if shell == "bash" \
            else os.path.join(os.environ.get("ZDOTDIR") or home, ".zshrc")

    def read(path):
        try:
            with open(path, encoding="utf-8") as stream:
                return stream.read()
        except OSError:
            return None

    def write(path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        temporary = f"{path}.{os.getpid()}.tmp"
        with open(temporary, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.replace(temporary, path)

    script = completion_script(shell)
    current = read(script_path)
    writes = [(script_path, script, "script", "create" if current is None else "unchanged" if current == script else "update")]
    if rc_path:
        begin, end = f"# >>> {PROGRAM} completion >>>\n", f"# <<< {PROGRAM} completion <<<\n"
        block = begin + f'[ -r "{script_path}" ] && . "{script_path}"\n' + end
        current = read(rc_path)
        if current is None:
            wanted, action = block, "create"
        elif begin in current and end in current:
            wanted = current[:current.index(begin)] + block + current[current.index(end) + len(end):]
            action = "unchanged" if wanted == current else "update"
        else:
            wanted, action = current + ("" if not current or current.endswith("\n") else "\n") + block, "update"
        writes.append((rc_path, wanted, "managed-block", action))
    # Section 4: the fingerprint covers what would be written and what is there, and is computed before the write.
    state = [[path, kind, action, hashlib.sha256(text.encode("utf-8")).hexdigest(),
              None if read(path) is None else hashlib.sha256(read(path).encode("utf-8")).hexdigest()]
             for path, text, kind, action in writes]
    fingerprint = "sha256:" + hashlib.sha256(json.dumps([shell, state], separators=(",", ":")).encode("utf-8")).hexdigest()
    if BREAK == "fingerprint-constant":
        fingerprint = "sha256:" + "1" * 64
    if apply or BREAK == "install-plan-writes":
        for path, text, _kind, action in writes:
            if action != "unchanged":
                write(path, text)
    files = [{"path": path, "kind": kind, "action": action} for path, _text, kind, action in writes]
    if BREAK == "install-plan-no-paths":
        files = [{key: value for key, value in entry.items() if key != "path"} for entry in files]
    return {"mode": "apply" if apply else "plan", "shell": shell, "files": files, "catalog": {"version": VERSION},
            "activate": f"source {rc_path or script_path}", "fingerprint": fingerprint,
            "changed": bool(apply) and any(action != "unchanged" for _p, _t, _k, action in writes)}


def cell(value):
    if isinstance(value, str):
        text = value.replace("\\", "\\\\").replace("\t", "\\t").replace("\r", "\\r").replace("\n", "\\n")
        return "".join(f"\\u{ord(char):04x}" if ord(char) < 32 or ord(char) == 127 else char for char in text)
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def record_text(records):
    columns = sorted(set().union(*(record.keys() for record in records)))
    return "".join("\t".join(cell(record[key]) if key in record else "" for key in columns) + "\n" for record in records)


def field_text(value):
    """Spec 2.4 section 5: the pipe rendering of one member of data, whatever its shape."""
    if isinstance(value, list):
        if value and all(isinstance(item, dict) for item in value):
            return record_text(value)
        return "".join(cell(item) + "\n" for item in value)
    if isinstance(value, dict):
        return record_text([value])
    return cell(value) + "\n"


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
    if "--field" in options and fmt == "json":
        return fail(selected["id"], "VALIDATION_FAILED", "--field is not available with --format json.", fmt, compact)
    if "--field" in options and selected["effect"] != "read" and BREAK != "field-after-write":
        # Section 5: a command that may write decides on --field before it runs, and from the catalog.
        schema = selected.get("outputSchema", {})
        accepted = schema.get("required", []) + (list(schema.get("properties", {}))
                                                 if BREAK == "field-optional-after-write" else [])
        if options["--field"] not in accepted:
            return fail(selected["id"], "VALIDATION_FAILED",
                        f"--field accepts a member '{selected['id']}' always returns: {', '.join(accepted) or 'none'}.",
                        fmt, compact)
    if selected["id"] == "describe" and "--prefix" in options:
        prefix = options["--prefix"]
        if not options.get("--summary"):
            return fail("describe", "VALIDATION_FAILED", "--prefix requires --summary.", fmt, compact)
        if operands:
            return fail("describe", "VALIDATION_FAILED", "--prefix conflicts with COMMAND_ID.", fmt, compact)
        if not isinstance(prefix, str) or not prefix:
            return fail("describe", "VALIDATION_FAILED", "--prefix requires PREFIX.", fmt, compact)
        if re.fullmatch(r"[a-z]([a-z0-9.-]*[a-z0-9-])?", prefix) is None:
            return fail("describe", "VALIDATION_FAILED", "--prefix is not a valid command prefix.", fmt, compact)
    if fmt == "jsonl" and selected["outputMode"] != "json-records" and "--field" not in options:
        return fail(selected["id"], "VALIDATION_FAILED", "jsonl is for json-records commands.", fmt, compact)
    if options.get("--help") is True and selected["id"] != "help" and not selected["input"]["passthrough"] \
            and BREAK != "help-runs":
        # Section 6: --help after a command gives its help, and the command does not run.
        operands, selected = [selected["id"]], by_id["help"]
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
            text += "".join(f"  {PROGRAM} {' '.join(shlex.quote(word) for word in example['words'])}  {example['summary']}\n"
                            for example in target.get("examples", []))
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
    elif identifier in ("completion", "completion.install"):
        shell = operands[0] if operands else ""
        if shell not in SHELLS:
            return fail(identifier, "VALIDATION_FAILED", "SHELL is bash, zsh or fish.", fmt, compact)
        if identifier == "completion":
            data = {"shell": shell, "script": completion_script(shell)}
            text = data["script"]
            if BREAK == "completion-tty-writes" and sys.stdout.isatty():
                with open(os.path.join(os.environ.get("HOME") or ".", f".{PROGRAM}-completion"), "w") as stream:
                    stream.write(text)
        else:
            applying, expected = bool(options.get("--apply")), options.get("--expect")
            if expected is not None and not applying:
                return fail(identifier, "VALIDATION_FAILED", "--expect requires --apply.", fmt, compact)
            if expected is not None and re.fullmatch(r"sha256:[0-9a-f]{64}", str(expected)) is None:
                return fail(identifier, "VALIDATION_FAILED", "--expect takes sha256:HEX, 64 digits.", fmt, compact)
            if BREAK == "expect-after-write":
                data = install_completion(shell, applying)
                stale = expected is not None and expected != install_completion(shell, False)["fingerprint"]
            else:
                stale = expected is not None and expected != install_completion(shell, False)["fingerprint"]
                data = None if stale else install_completion(shell, applying)
            if stale:
                return fail(identifier, "PRECONDITION_FAILED", "The installation is not the one this fingerprint names.",
                            fmt, compact, hint=f"plan again: {PROGRAM} completion install {shell}")
            text = "".join(f"{entry.get('action')} {entry.get('path', '')}\n" for entry in data["files"]) \
                + f"{data['mode']}: {data['activate']}\n"
    elif identifier == "complete.candidates":
        current = operands[-1] if operands else ""
        given = operands[:-1]
        target = next((item for item in CATALOG if given and given[:len(item["pattern"])] == item["pattern"]), None)
        if target is not None and target["external"]:
            # Section 9: after a delegate's pattern the words are the delegate's; this one has none.
            matching = []
        elif target is not None and target["available"]:
            matching = sorted(word for word in candidate_words(target)
                              if word.startswith(current) and not (word.startswith("-") and word in given))
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
        if BREAK == "delegate-format-drift" and target is not None and target["external"]:
            text = "a-word-only-text-mode-offers\n"
    else:
        data = {"mode": "apply" if options.get("--apply") else "plan", "changed": False}
        text = f"note: {data['mode']}\n"
    field = options.get("--field")
    if field is not None:
        if field not in data:
            if BREAK != "field-silent":
                return fail(identifier, "VALIDATION_FAILED", f"No member {field!r} in data.", fmt, compact)
            data[field] = []
        text = field_text(data[field])
        emitted = data[field] if isinstance(data[field], list) else [data[field]]
    else:
        emitted = data.get("records", [])
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
        for record in emitted:
            sys.stdout.write("not-json\n" if BREAK == "malformed-jsonl" else json.dumps(record, separators=(",", ":")) + "\n")
    else:
        sys.stdout.write(envelope(identifier, True, 0, data, compact))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
