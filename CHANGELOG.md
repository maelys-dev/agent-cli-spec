# Changelog

## 2.3.0 — 2026-09-05

- Add `--progress auto|always|never` and `--verbose` to the trunk. Progress
  follows stderr's terminal status by default; verbose details are explicit.
  Both stay on stderr in text mode, never resemble failure renderings, and
  remain silent in JSON and JSONL. A program with nothing to show accepts
  them without producing diagnostics. Protocol streams keep diagnostics on
  stderr and delegates receive the options verbatim. An agent discovers
  support in `globalOptions` before passing them. This gives products one
  spelling for progress and details while preserving parseable machine
  streams; adding diagnostics beside JSON failure envelopes was rejected.
- Add `--pager auto|always|never`. Text may be paged when stdout is a
  terminal; a pager never starts in a pipe, in JSON/JSONL, or under an active
  `--non-interactive`. `PAGER` is an executable with arguments using POSIX
  quoting, without shell expansion; empty or whitespace-only disables it.
  Unset runs `less` with `LESS=FRX` unless `LESS` is already set. An invalid
  pager command or a binary that cannot start falls back to stdout. Color
  follows the original stdout. A protocol-stream command refuses this
  rendering option; a delegate receives it verbatim. Programs without a
  pager accept the option and render directly.
- None of the trunk options is repeatable. Duplicates fail before execution
  with `VALIDATION_FAILED`, even with the same value, as section 8 already
  classed duplication; flags with `=false` do not activate their implied
  behavior. The kit checks the declarations, the duplicate and invalid-value
  refusals, the unchanged stdout and the diagnostic silence.
- Product transport options may be declared in `globalOptions` or repeated
  in `input.options` wherever accepted, with one spelling and shape.
  Implementations should offer the global declaration form; options repeated
  only at command level still require product tests of their common
  transport semantics. The kit checks trunk collisions.
- Clarify text records: a terminal may display aligned columns and a header.
  A pipe has one plain, tab-separated line per record. Columns are the union
  of member names in the result, sorted by Unicode code point and shared by
  every row. Missing fields are empty; strings escape backslashes, tabs,
  line breaks and ASCII controls; other values use compact JSON. This order
  does not depend on JSON Schema property ordering. Text layout can evolve
  within v2; invocation semantics and machine forms remain the compatibility
  boundary. Products adopting this tag may need to change their pipe text;
  consumers requiring stable fields continue to use JSON or JSONL. The kit
  checks the pipe form against the records of the JSON envelope.

Migration: an implementation pinned to 2.2.1 declares and accepts the three
new options, implements their documented behavior where supported, and
adapts its text records when necessary. No new effect or value kind is added.
The committed maelys-cli example still represents its own 2.2.1 pin.

## 2.2.1 — 2026-09-05

- Clarify section 7: the format selects the rendering, never the stream. In
  text mode as in JSON, a success renders on stdout and a failure on stderr;
  a validation that found violations (exit 2) is a success whose verdict is
  data on stdout in every format. The kit checks that the text rendering of
  `version`, `help` and `describe --summary` leaves stderr empty. No
  behavior of a conformant implementation changes.

## 2.2.0 — 2026-09-05

- Add `hidden` on option descriptors: a hidden option is parsed, validated
  and constrained like any other, appears in `input.options` of every
  `describe` form with `hidden: true`, and is absent from `usage`,
  `input.synopsis`, the text of `help COMMAND_ID` and the candidates of
  `__complete`. Absent means false; implementations emit the member only
  when true. `schemas/describe.json`, the conformant fixture and the kit
  carry the contract: the kit checks every hidden option of a catalog. This
  is a compatible addition to `agent-cli/v2`; existing documents are
  unchanged.

## 2.1.0 — 2026-09-04

- Specify token-efficient namespace discovery with `describe --summary
  --prefix PREFIX`. A filtered summary preserves catalog order, identifies its
  `command-prefix` filter, and rejects an unknown prefix with
  `INVALID_COMMAND`. The option is incompatible with `COMMAND_ID` and requires
  `--summary`.
- Extend `schemas/describe.json`, the conformant fixture and the external
  conformance kit with the filtered-summary contract. This is a compatible
  addition to `agent-cli/v2`; existing invocations and documents are
  unchanged.
- `conflictsWith` of an option may name an operand of the same command, not
  only an option: an entry starting with `--` names an option, any other
  entry names an operand of `input.operands`. Every entry of `requires` and
  `conflictsWith` resolves to a declaration of the same command or to a
  global option; the kit verifies it for every command of the catalog.
- Section 11 states how a mandatory addition stays compatible: an
  implementation is conformant to the tag it pins and takes the addition on
  when it moves its pin; an agent relies on the catalog, not on
  `agent-cli/v2`, to know which forms a program accepts. Section 1 applies
  it to `--prefix`: an agent checks the `describe` descriptor before using
  it and falls back to `describe --summary`.

## 2.0.1 — 2026-09-04

- The specification and the schemas are licensed CC BY-SA 4.0
  (`LICENSE-SPEC`) instead of CC0: attribution to this repository and
  share-alike on derived specifications. The code stays MPL-2.0. Nothing
  else changes; implementations pinned at v2.0.0 need not move.

## 2.0.0 — 2026-09-04

First written form of `agent-cli/v2`, until now split between the
`command-conventions.md` and `agent-cli.md` of Hermes and of maelys-cli,
which had diverged (342 lines apart), and implemented three times.

- `spec/agent-cli.md`: the trunk the three implementations share, in the
  state maelys-cli 0.5.6 and maelys-release 0.5.0 implement it: discovery
  by `describe` in its three forms, the descriptor and its input contract,
  value kinds, the six effects and the plan/`--apply` transaction, the seven
  global options, the five built-in commands, the envelopes, the exit codes
  and the eleven stable error codes, protocol streams, versioning of the
  contract itself.
- `spec/extensions.md`: `x-` members, domain error codes and transport
  options are the extension points; effects, output modes and exit codes
  are closed.
- `schemas/`: `describe.json`, `envelope.json`, `version.json`,
  `records.json`.
- `conformance/run.py`: sixty-odd checks driven from the outside, with a
  standard-library JSON Schema validator for the subset the schemas use.
  Passes on `maelys-hello` (C) and `maelys-release` (Python); reports the
  distance of Hermes 0.19.0, which predates the trunk (catalog
  `schemaVersion` 3, no `program`, `cliApi` nor `framework`, no global
  options in the catalog, descriptors without `external`, `hidden`,
  `available`, an undeclared `repository` member, exit codes reduced to
  `0`, `mcp-json-rpc-stream` as an output mode, `INVALID_PATH` for an
  unknown command, no completion).
