# Changelog

## Unreleased

- Specify token-efficient namespace discovery with `describe --summary
  --prefix PREFIX`. A filtered summary preserves catalog order, identifies its
  `command-prefix` filter, and rejects an unknown prefix with
  `INVALID_COMMAND`. The option is incompatible with `COMMAND_ID` and requires
  `--summary`.
- Extend `schemas/describe.json`, the conformant fixture and the external
  conformance kit with the filtered-summary contract. This is a compatible
  addition to `agent-cli/v2`; existing invocations and documents are
  unchanged.

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
