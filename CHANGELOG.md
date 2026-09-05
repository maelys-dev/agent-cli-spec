# Changelog

## 2.3.0 — 2026-09-05

- Add `--verbose` to the trunk of global options: diagnostics of the run on
  stderr, in text mode only, default silent. Under `--format json` or `jsonl`
  the option is accepted and writes nothing, so an agent's envelope stays
  alone on its stream; a program with nothing to say accepts it and produces
  nothing more. Decision: several products need a progress diagnostic for
  humans during long network work, and one spelling across products is what
  the contract exists for, as for `--apply`; leaving the name to each product
  would have cost that consistency for no gain. The alternative, diagnostics
  on stderr in JSON mode too, was rejected: a failure envelope lives on
  stderr, so any diagnostic there would break the parsing of stderr on
  failure unless a framing rule changed every consumer; an agent that wants
  machine progress has `jsonl` records. A `protocol-stream` command accepts
  the option and keeps its diagnostics on stderr; a delegate receives it
  verbatim. An agent checks `globalOptions` before passing `--verbose`. A
  program conformant to 2.2.1 moves to 2.3.0 by declaring `--verbose` in
  `globalOptions` and accepting it. The kit checks the declaration and its
  shape, the silence in JSON and jsonl modes on success and on failure, the
  unchanged stdout in text mode, `--verbose=false`, and that no command
  borrows a trunk spelling with another shape.
- `spec/extensions.md`, "Global options": the MUST lands on one spelling
  and one shape wherever a product option appears, never a trunk spelling
  with another shape or meaning; the option is declared in `globalOptions`
  or in `input.options` of every command that accepts it, and an
  implementation SHOULD offer the first form. Decision: this documents what
  the reference implementations allow today instead of requiring two
  frameworks to change before the clause is usable again, and gives the kit
  the one part it can verify, the shape of trunk spellings in every command.

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
