<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->
# agent-cli/v2

The contract of a command-line program that humans and agents drive the same
way: one catalog describes every command, the program answers `describe`
with that catalog, success is one JSON envelope on stdout, failure one on
stderr, and the exit code says whether the work completed, failed, or
validated something that turned out invalid.

This document is normative. Its identifier is `agent-cli/v2`, carried by
every envelope. The words MUST, MUST NOT, SHOULD and MAY are used as in
RFC 2119. Implementations exist in TypeScript (Hermes, where the contract
was born), C (`libmaelys_cli`, the framework) and Python (`maelys-release`);
the [conformance kit](../conformance/run.py) checks any of them from the
outside, and the [schemas](../schemas/) are the machine-readable form of
what follows.

## 1. Discovery

A program MUST answer these invocations with a success envelope:

```sh
PROGRAM describe --format json                  # the catalog
PROGRAM describe --summary --format json        # every descriptor, without schemas
PROGRAM describe --summary --prefix PREFIX --format json
                                                # one command namespace, without schemas
PROGRAM describe COMMAND_ID --format json       # one descriptor
```

`data` of a `describe` envelope is a document of `schemas/describe.json`:

| Member | Value |
| --- | --- |
| `schemaVersion` | `1`, the version of the catalog document |
| `kind` | `catalog`, `summary` or `command` |
| `program` | the executable name |
| `product` | the human product name |
| `version` | the product version |
| `contract` | `agent-cli/v2` |
| `cliApi` | `1`, the dispatcher API the program accepts |
| `framework` | the implementation and its version, free text |
| `commands` | the descriptors: all of them, or the one asked |
| `globalOptions`, `invariants`, `output` | the catalog form only |
| `filter` | the filtered-summary selection, present only with `--summary --prefix PREFIX` |

`describe --summary` omits `outputSchema` and `exitCodes` from each
descriptor. `describe COMMAND_ID` returns exactly the catalog's descriptor of
that identifier, and fails with `INVALID_COMMAND` for an unknown one. The
catalog form carries `globalOptions`, `invariants` and `output`, and every
descriptor of the catalog and of the command form carries `outputSchema` and
`exitCodes`; the summary and command forms MUST NOT carry the three catalog
members.

`describe --summary --prefix PREFIX` is the token-efficient discovery form
for a command namespace. `PREFIX` has the command-identifier grammar of
section 2 without a trailing dot, that is `^[a-z](?:[a-z0-9.-]*[a-z0-9-])?$`.
It selects the command whose identifier equals `PREFIX`, if
one exists, and every command whose identifier starts with `PREFIX.`; it does
not perform an arbitrary string-prefix match. The response has `kind:
"summary"`, carries `filter: {"kind": "command-prefix", "value": PREFIX}`
and otherwise follows the summary rules above. Catalog order is preserved,
including hidden and unavailable descriptors. No match fails with
`INVALID_COMMAND`. `--prefix` requires `--summary` and conflicts with the
`COMMAND_ID` operand; either misuse fails with `VALIDATION_FAILED`. The
prefix is resolved inside the command, after option validation: a misuse
fails with `VALIDATION_FAILED` even when the prefix is unknown, and only a
well-formed `describe --summary --prefix PREFIX` without a match fails with
`INVALID_COMMAND`. An agent checks that the `describe` descriptor declares
`--prefix` before using it, and falls back to `describe --summary` when it
does not: a program pinned to an earlier tag of this contract does not have
this form.

An agent identifies a command by `id`, never by its human label, and builds
an invocation from `input`, never from help text.

## 2. Command descriptor

| Member | Value |
| --- | --- |
| `id` | stable identifier, `[a-z][a-z0-9.-]*`, unique in the catalog |
| `pattern` | the words that select the command, in order |
| `usage` | the human synopsis; MUST equal `input.synopsis` |
| `purpose` | one sentence |
| `effect` | one effect of section 4, or `{"plan": "preview", "apply": "apply"}` / `{"plan": "preview", "apply": "commit"}` for a transaction |
| `outputMode` | `json-envelope`, `json-records` or `protocol-stream` |
| `protocol` | the named protocol owning stdio (`git-smart`, `mcp-json-rpc`), when a `protocol-stream` command declares one; a command that merely relays a child's stdio declares none |
| `external` | `true` when the command hands over to another executable |
| `hidden` | `true` when the command is not shown to humans |
| `available` | `false` when this build cannot run the command; then `unavailableReason` says why |
| `input` | `synopsis`, `operands`, `options`, `constraints`, `passthrough` |
| `outputSchema` | a JSON Schema of `data` on success |
| `exitCodes` | exactly `{"0": "command completed", "1": "execution failed", "2": "valid report with violations"}` |

A descriptor MAY carry members whose name starts with `x-`; a generic agent
ignores them (see [extensions](extensions.md)). It MUST NOT carry other
undeclared members.

### Operands

`name`, `required`, `variadic`, `summary`; optionally `type` with the value
kinds of section 3, `choices`, `minimum`, `maximum`. At most one operand is
variadic, and it is the last one. `passthrough: true` means every argument
after the pattern reaches the command verbatim, including `--help`.

### Options

`long` (`--name`), `required`, `repeatable`, `summary`, `requires` (options
that MUST accompany this one), `conflictsWith` (what cannot accompany this
one: an entry starting with `--` names an option, any other entry names an
operand of `input.operands`); optionally `argument`
(`name`, `type`, and `choices`, `minimum`, `maximum`, `algorithms`, `pattern`
as the kind needs), `default` (the single source of the default, as text),
`group` (all-or-none with the options of the same group), `hidden` (boolean,
absent means false). An option without `argument` is a flag; `--flag=false`
is accepted. Every entry of `requires` and `conflictsWith` MUST resolve to an
option of the same command or a global option, or for `conflictsWith` to an
operand of the same command.

`hidden: true` marks an option that is not shown to humans. A hidden option
is parsed, validated and constrained like any other option: `requires`,
`conflictsWith`, `group` and `input.constraints` may name it. It MUST appear
in `input.options` of every `describe` form, with `hidden: true`. It MUST NOT
appear in `usage` and `input.synopsis`, in the text of `help COMMAND_ID`,
nor among the candidates of `__complete`. `help` and the completion are for
humans; `describe` is for agents and stays complete. This is the symmetry of
the hidden command: listed by `describe`, never offered. An implementation
SHOULD emit the member only when it is `true`, so that generated references
committed by products do not change.

### Constraints

`input.constraints` repeats the cross-option rules as entries `{"kind":
..., "options": [...]}` with `kind` among `requires`, `at-most-one`,
`exactly-one`, `all-or-none`.

## 3. Value kinds

`boolean`, `string`, `integer`, `unsigned`, `size` (K/M/G/T suffix),
`duration` (unit required: ms, s, m, h, d), `path` (non-empty),
`absolute-path`, `choice` (with `choices`), `hex`, `digest`
(`ALGORITHM:HEX`, `algorithms` declared), `sha256`. Ranges and choices are
declared in the catalog and enforced by the parser before the command runs.
An option value that starts with `--` is still a value.

`pattern`, on a `string` or `path` value, is the regular expression the value
MUST match; the implementation enforces it by the means of its choice, a
regex engine or code, and refuses a mismatch with `VALIDATION_FAILED`. It is
written in the common subset of ECMA-262 and POSIX ERE: literals, ASCII
character classes and ranges, `.`, the quantifiers `*`, `+`, `?` and `{m,n}`,
alternation, unnamed groups, the anchors `^` and `$`; no named group, no
`\p{...}` class, no lookaround, no back-reference. Written so, the same motif
reads the same for an agent, which MAY check a value against it before
invoking, for the conformance kit, and for an implementation that checks it
by hand.

## 4. Effects

| Effect | Meaning | Durable write |
| --- | --- | --- |
| `read` | Inspects or validates state. | No |
| `preview` | Builds an exact plan. | No |
| `apply` | Applies a reviewed transaction. | Yes |
| `commit` | Records a reviewed version-control commit. | Yes |
| `execute` | Deliberately runs a non-transactional action. | Per action |
| `stream` | Reserves stdio for a declared protocol. | Per protocol |

A transaction declares the two-phase effect and an `--apply` option. Without
`--apply` it returns `data.mode: "plan"` and writes nothing; with `--apply` it
re-validates its preconditions and returns `data.mode: "apply"`. A plan MUST
carry enough identity (revision, digest, paths) for the caller to review the
exact later action. `--dry-run` and `--plan` MUST be refused with
`VALIDATION_FAILED` and a hint naming `--apply`: one spelling of the intent
across products is what the contract exists for.

## 5. Global options

Every program accepts, on every command:

| Option | Meaning |
| --- | --- |
| `--format text\|json\|jsonl` | text for humans, json for one envelope, jsonl for records (default `text`) |
| `--json` | exact alias of `--format json` |
| `--compact` | JSON on a single line |
| `--pretty` | `--pretty=false` selects compact JSON |
| `--non-interactive` | never prompt; fail with `VALIDATION_FAILED` instead of asking |
| `--color auto\|always\|never` | ANSI colors on terminals (default `auto`) |
| `--progress auto\|always\|never` | progress of a long run on stderr, in text mode, when stderr is a terminal (default `auto`) |
| `--verbose` | details of the run on stderr, in text mode only (default silent) |
| `--pager auto\|always\|never` | pager for the text rendering when stdout is a terminal (default `auto`) |
| `--help` | the help of the selected command |

None of these options is repeatable; a duplicate fails with
`VALIDATION_FAILED`, even when both occurrences have the same value. An
option with a value takes exactly the choices shown, whatever name the
catalog gives its argument. `--flag=false` disables the flag, including
`--non-interactive=false`; a false flag does not activate its implied behavior.

Progress and details follow the example of git's progress and of `--color
auto`. In text mode a program MAY show the progress of a long run on stderr:
with `--progress auto`, the default, only when stderr is a terminal, so that
a human sees it and a pipe or a log does not; `always` forces it, `never`
suppresses it. Progress is transient: the program finishes or erases it
before it exits, and never writes it to stdout. `--verbose` adds the details
of the run on stderr, what the program does, waits for and skips, one line
each, default silent, whatever stderr is; a detail line SHOULD carry a
distinct prefix (`PROGRAM: `, as git's `remote: `). Under `--format json` or
`jsonl` both options are accepted and write nothing, so that an agent's
envelope stays alone on its stream. A program that has nothing to show
accepts both and produces nothing more, never an error. A progress or detail
line is never an envelope and never starts with `PROGRAM: [`, the rendering
of a failure; both are colored under the same rule as that rendering
(`--color`, `NO_COLOR`, `TERM=dumb`). Neither is a rendering option: a
`protocol-stream` command accepts them and keeps its diagnostics on stderr
as section 9 requires, and a delegate receives them verbatim with the rest
of its arguments. One spelling across products, as for `--apply`: a product
MUST NOT declare another option for the same intents; a finer diagnostic
(`--debug`, a trace) is a product option with its own meaning. An agent
checks that `globalOptions` lists them before passing them: a program pinned
to an earlier tag of this contract does not have them.

A pager follows git too. In text mode, with `--pager auto`, the default, a
program MAY send its rendering through a pager when stdout is a terminal, so
that a human browses a long rendering as `git log` is browsed. A pager is
never started when stdout is not a terminal, as git never does; `always`
pages whenever stdout is a terminal, even where a product setting would
disable it; `never` disables it. `--non-interactive` implies `--pager never`:
a pager waits for a human, and the option promises none. The pager is the
executable and arguments named by `PAGER`, split using POSIX shell quoting
and backslash rules, without shell expansion, pipelines or redirections.
An empty or whitespace-only `PAGER` disables it; when it is unset the
program runs `less` and sets `LESS=FRX` unless `LESS` is set, as git does, so
that a short rendering passes through and colors survive. When the pager
cannot be started, or its command cannot be parsed, the rendering goes to
stdout unchanged. The pager receives
the rendering that would have gone to stdout, colored as `--color` decided
on that stdout, not on the pager's pipe; it changes neither the exit code
nor the failure rendering, which stays on stderr. Under `--format json` or
`jsonl` the option is accepted and nothing is paged. `--pager` is a
rendering option: a `protocol-stream` command refuses it when given, as
section 9 says, and a delegate receives it verbatim. A program without a
pager accepts the option and writes to stdout as before.

`--format jsonl` is accepted only by `json-records` commands. A
`protocol-stream` command refuses every rendering option. An implementation
MAY honor an environment variable that selects the default format
(`MAELYS_CLI_FORMAT` in the Maelys implementations), so that an agent obtains
a JSON failure envelope from a stream command whose stdout it cannot touch.

## 6. Built-in commands

| Identifier | Pattern | Data |
| --- | --- | --- |
| `help` | `help [COMMAND_ID]`, also `--help` | `{"text": ..., "commands": [ids]}` |
| `version` | `version`, also `--version` | `product`, `program`, `version`, `contract`, `cliApi`, `framework` |
| `describe` | `describe [COMMAND_ID] [--summary] [--prefix PREFIX]` | section 1 |
| `completion` | `completion bash\|zsh\|fish` | `{"shell": ..., "script": ...}`; text mode prints the script |
| `complete.candidates` | `__complete -- WORDS...`, hidden, `json-records` | `{"count": N, "records": [{"word": ...}]}` |

The completion script calls `PROGRAM __complete -- WORDS...` and falls back to
the shell's file completion when no candidate is returned. Candidates come
from the catalog: command words, options not yet given with hidden options
excluded, choices; command identifiers after `help` and `describe`; never an
unavailable command.

## 7. Envelopes

Success, on stdout only:

```json
{"schemaVersion": 2, "contract": "agent-cli/v2", "command": "note.write",
 "ok": true, "exitCode": 0, "data": {}}
```

Failure, on stderr only, stdout empty:

```json
{"schemaVersion": 2, "contract": "agent-cli/v2", "command": "note.write",
 "ok": false, "exitCode": 1,
 "error": {"code": "VALIDATION_FAILED", "message": "Stable causal diagnostic.",
           "hint": "Next safe action."}}
```

`command` is the identifier of the resolved command, or `unknown` when
resolution failed. `error.message` states the first causal failure in plain
language; `error.hint` gives the next safe action and SHOULD be present;
`error.issues` MAY list `{"code", "path", "message"}` entries for schema
failures. `data` is governed by the descriptor's `outputSchema`. A
`json-records` command renders `{"count": N, "records": [...]}` in the
envelope, `count` being the number of `records` in that envelope (a total
beyond it is an `x-` member), one compact record per line with `--format
jsonl`, and in text one
row per record plus, when stdout is a terminal, an optional header; there it
MAY align columns and color, and pages as section 5 says. Into a pipe it
renders one plain line per record, with fields separated by tabs. The columns
are the union of the records' top-level member names, sorted lexicographically
by Unicode code point; every row uses those same columns. A missing member
is an empty field; a string is printed without JSON quotes, escaping
backslash, tab, carriage return and newline as `\\`, `\t`, `\r` and `\n`.
Other ASCII control characters (U+0000 to U+001F, and U+007F) use `\uXXXX`.
Every other value, including `null`, a boolean, an array or an object, is
compact JSON. An empty object still has a row; zero records produce no lines.
Each row ends with a newline, with no header or terminal escape sequences.
Column order does not depend on `outputSchema`, whose job is validation.
Thus `wc -l`, `cut` and `grep` see records and nothing else. The stable machine
form is `jsonl`: the columns in text can vary with the members present in a
result. Text is not a lossless interchange format (an absent member and an
empty string both render as an empty field).

Text rendering of a failure is `PROGRAM: [CODE] message` on stderr, followed
by `Hint: ...` when present, colored on a terminal unless `--color never`,
`NO_COLOR` or `TERM=dumb` applies. Nothing else is ever written to a
protocol stream's stdout.

The format selects the rendering, never the stream. In text mode as in JSON,
the rendering of a success goes to stdout and the rendering of a failure to
stderr. A validation that found violations (exit `2`, section 8) is a
success: its verdict is data, on stdout in every format. stderr carries what
accompanies the run, failure envelopes and, in text mode, the progress and
the details of `--progress` and `--verbose` (section 5), never the result.

## 8. Exit codes and error codes

Exit codes: `0` completed, `1` execution failure, `2` a validation correctly
executed that found violations (the envelope has `ok: true` and reports them
in `data`). A negative authorization decision is a successful read, never
exit 1. A stream command or a delegate propagates the exit status of the
underlying process, `128 + signal` on signal termination.

Errors are reported in this causal order: command resolution
(`INVALID_COMMAND`); option spelling, support by the command, duplication;
option value kind, range, choice; option dependencies and conflicts;
required options; operand arity and kinds; rendering constraints; then,
inside the command, file type and permissions, syntax, schema, policy, state
and concurrency preconditions.

| Code | Boundary |
| --- | --- |
| `INVALID_COMMAND` | Command not found. |
| `VALIDATION_FAILED` | Input shape, option, type or limit invalid. |
| `PRECONDITION_FAILED` | State changed or does not allow the transaction. |
| `POLICY_FAILED` | Policy could not be loaded or evaluated. |
| `ACCESS_DENIED` | Negative security decision, untrusted file or binary. |
| `NOT_FOUND` | Required resource absent. |
| `IO_FAILED` | System read or write failed. |
| `PROCESS_FAILED` | Subprocess or external command failed. |
| `PROTOCOL_FAILED` | Message or manifest violates its protocol. |
| `UNSUPPORTED` | Function absent from this build or version. |
| `UNEXPECTED` | Unclassified defect to fix in the implementation. |

A product MAY add codes for boundaries of its own domain
(`REVISION_CONFLICT` in Hermes); it MUST document them and MUST NOT reuse a
listed code for another meaning.

## 9. Protocol streams and delegates

`stream` commands and delegates (`external: true`) are the only exceptions
to the envelope. They refuse rendering options, keep diagnostics on stderr,
never inject banners, progress or JSON into their stdout, and declare
`outputMode: "protocol-stream"`. A command implementing a named protocol
identifies it through `protocol`; a command merely relaying a child's stdio
declares none, as section 2 says. A delegate receives every argument after its pattern
verbatim, including `--help`, and owns its exit code.

## 10. Proof of implementation

The catalog is the executable source of truth: the parser, `help`,
`describe`, the tests and any generated reference derive from it; nothing
maintains a second usage string. Any command change updates, in the same
change, the catalog entry, the handler, the output schema, the tests and the
generated reference. The conformance kit is run in the implementation's
continuous integration against its own binaries.

## 11. Versions of this contract

`agent-cli/v2` is the identifier of this document. A compatible clarification
or addition (a new optional member, a new value kind, a new invocation that
leaves existing invocation semantics and machine documents unchanged) is a new tag of this
repository and keeps the identifier. Such an addition may be mandatory in the
text of the tag that introduces it: an implementation is conformant to the
tag it pins, and takes the addition on when it moves its pin. An agent that
reads `agent-cli/v2` therefore relies on the catalog, not on the identifier,
to know which forms a program accepts. An incompatible change (a member
removed, a meaning changed, a required member added to an existing document)
changes the identifier to `agent-cli/v3` and starts a new document.

These compatibility guarantees cover invocation semantics, exit codes and
machine forms (`json`, `jsonl`, and protocol streams). Human text layout and
terminal presentation may evolve within v2, subject to the rules of the
pinned tag; the changelog records changes to the pipe rendering as well.
Consumers that need stable fields use `json` or `jsonl`.
