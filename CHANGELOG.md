# Changelog

## 2.6.0 — 2026-09-14

- An operand may declare `algorithms`, `digits` and `pattern`, which only an
  option's `argument` could carry before. The schema was narrower than the
  text: section 2 let an operand take "`type` with the value kinds of section
  3", section 3 says a `digest` is `ALGORITHM:HEX` with "`algorithms`
  declared" and that `pattern` constrains a `string` or `path` value, and the
  `operand` definition admitted neither. A `digest` operand could therefore
  not be described conformantly at all, and a `hex` operand could not state
  its width while an option's argument could. Section 2 now says an operand
  describes its value exactly as an argument does, and a test holds the two
  definitions to the same value-describing members so they cannot drift
  apart again. Reported by maelys-git-core, reading the framework's hex
  operands against the 2.4.0 schema.
- Nothing is required of an implementation: the three members are optional
  and a document valid under 2.5.1 stays valid. A program that avoided
  digest operands because it could not describe them may now declare them.
  The fixture carries one of each and the committed reference catalog
  carries them too.

## 2.5.1 — 2026-09-14

- Section 11 says who a migration note addresses. An implementation is a
  program, or a framework that programs are built on, and a framework owns
  the trunk of section 5 for its products: such a product declares none of it
  and reaches a tag only once its framework has. The notes of 2.3.0, 2.4.0
  and 2.5.0 read as though every implementation were independent, so a
  product built on a framework had to discover by pinning that the move was
  not its to make. Reported by a product of the fleet, which could declare
  nothing of `--field` until its framework had shipped it.
- Section 10 says what a framework owes the kit. Its products exercise only
  the declarations they happen to use, and a declaration nothing exercises is
  a declaration nothing has judged, so a framework runs the kit against a
  program of its own declaring every form it offers. This is the lesson of
  the two members 2.5.0 answered, found by a property test and not by the
  kit; the kit's report has named the blind spot since 2.5.0, and the text
  now names the remedy.

## 2.5.0 — 2026-09-14

- Section 2, constraints: `input.constraints` **states** the cross-option
  rules rather than repeating them. The former word was false for one kind
  of four: `requires`, `at-most-one` and `all-or-none` have an option-level
  form, `exactly-one` has none, so for it `input.constraints` is the only
  site. An entry's `options` is the whole rule, so two all-or-none groups are
  two entries and no entry needs a name. `all-or-none` is the one kind that
  MUST agree with the options, `group` being its option-level form: the
  options of an entry are exactly the options sharing one `group`, and every
  `group` of a command has its entry. The kit checks that agreement, which
  is why this is a minor and not a patch: a program that declared a `group`
  without its entry passed the 2.4.0 kit and fails this one. The other kinds
  keep restating an option-level rule or not, as they do today.
- `spec/extensions.md` names every object a `describe` document may extend
  with `x-`. Its list stopped at the catalog, a descriptor, an operand and
  an option, while the schemas have always opened `x-` on `input`, an
  argument, a constraint, a transaction effect and the filter of a filtered
  summary as well. The schema was wider than the text, the inverse of the
  defect this repository usually guards against, and the text now matches.
  Section 2 points at that list instead of naming descriptors alone.
- Ship `examples/reference.describe.json`: one catalog carrying every member
  and every enumerated value the contract allows, generated from the
  conformant fixture and held equal to it by a test, so an implementer reads
  in one document what a `describe` may contain. The fixture gained the
  declarations it lacked: a grouped pair, all four constraint kinds, every
  value kind, a protocol stream, a delegate, a `commit` transaction,
  passthrough and `x-` members on each object. Two tests walk the schema and
  assert that no member name and no enumerated value is missing from the
  fixture's output, so the claim cannot rot.
- The kit's report names one more thing it does not check: declarations a
  program never emits. A kit sees what a program chooses to show, so a
  framework whose macros exceed what its products use checks its own output
  over every declaration it offers. Reported by maelys-cli, whose property
  test over 29 declaration macros found two members this contract refuses.

## 2.4.0 — 2026-09-11

- Add `--field NAME` to the trunk of global options: it renders one
  top-level member of `data` instead of the whole result, so that a human
  reads a member without a query tool. Never a path, because a path language
  is the trade of `jq` and half of one is worse than none. A name `data` does
  not carry fails with `VALIDATION_FAILED`, never an empty output, a silent
  empty result in a pipe being the costliest failure mode. In text mode the
  member follows the pipe rules of section 7, extended to the shapes that
  section did not cover: an array of objects gives one row per object, any
  other array one value per line, an object one row with its members as
  columns, any other value its escaped value on one line. In `jsonl` mode an
  array gives one compact JSON value per line and any other member exactly
  one line, so `--format jsonl` is now accepted by a `json-records` command
  and by any command together with `--field`. Decision: five implementations
  needed the same thing at once, and one spelling across products is what the
  contract exists for. The alternative, making `jsonl` valid on a
  `json-envelope` command when the data happens to hold an array, was
  rejected: the validity of a format must follow the command's declared mode
  and never the shape of the data, else `describe` no longer tells an agent
  which formats work. `--field` with `--format json` fails with
  `VALIDATION_FAILED`, since `data` is governed by the descriptor's
  `outputSchema` and a filtered envelope would no longer validate. `--field`
  is a rendering option, refused by a `protocol-stream` command and received
  verbatim by a delegate; it pages like any text rendering, changes no exit
  code and leaves the failure rendering alone. A program conformant to 2.3.1
  moves to 2.4.0 by declaring `--field` in `globalOptions` and accepting it.
  The kit checks the declaration and its shape, the rendering of a scalar, an
  array, an array of objects and an object in both formats, the two refusals
  and the duplicate refusal.

## 2.3.1 — 2026-09-06

- The motif of `--prefix` in section 1, the schema and the fixture is
  written `^[a-z]([a-z0-9.-]*[a-z0-9-])?$`, with a plain group: the earlier
  `(?:...)` is a non-capturing group that POSIX ERE lacks and that section 3
  excludes from the common dialect, so the specification contradicted
  itself. Section 3 now names `(?:...)` among the excluded constructs. The
  two spellings match the same values; the kit accepts either in a catalog,
  so an implementation that published the earlier one stays conformant. A
  C implementation that rewrote `(?:` as `(` did the right thing.

## 2.3.0 — 2026-09-06

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
- None of the trunk options is repeatable. Duplicates fail before execution;
  flags with `=false` do not activate their implied behavior. The kit checks
  declarations, duplicate and invalid-value refusals, JSONL record content,
  unchanged stdout and diagnostic silence. Pager sentinels detect forbidden
  process creation even when the pager would copy its input unchanged. The
  fixture is also tested on pseudo-terminals, including false flags, missing
  or malformed pagers, default LESS settings and machine output modes.
- Product transport options may be declared in `globalOptions` or repeated
  in `input.options` wherever accepted, with one spelling and shape.
  Implementations should offer the global declaration form; options repeated
  only at command level still require product tests of their common
  transport semantics. The kit checks trunk collisions and command
  declarations that repeat a declared product global option.
- Section 1 says which form of `describe` carries which members: the catalog
  carries `globalOptions`, `invariants` and `output` and full descriptors,
  the command form full descriptors, the summary neither. Section 3 gives
  `pattern` its status and its dialect: the value MUST match it, the
  implementation enforces it by regex engine or by code, and it is written in
  the common subset of ECMA-262 and POSIX ERE so that an agent, the kit and
  an implementation read the same motif. Section 7 defines `count` as the
  number of `records` in the envelope.
- Clarify text records: a terminal may display aligned columns and a header.
  A pipe has one plain, tab-separated line per record. Columns are the union
  of member names in the result, sorted by Unicode code point and shared by
  every row. Missing fields are empty; strings escape backslashes, tabs,
  line breaks and ASCII controls; other values use compact JSON. This order
  does not depend on JSON Schema property ordering. Text layout can evolve
  within v2; invocation semantics and machine forms remain the compatibility
  boundary. Products adopting this tag may need to change their pipe text;
  consumers requiring stable fields continue to use JSON or JSONL.
- Harden the kit: JSON equality distinguishes booleans and numbers, integer
  values include `1.0`, and string lengths are enforced. Conditional schemas
  distinguish catalogs, summaries and single descriptors, require complete
  output contracts and unavailable reasons, and preserve `x-` transaction
  extensions. `cliApi` is fixed to 1, a failure exit code is at least 1, a
  delegate is a protocol stream, and a schema whose regex this kit cannot
  compile is skipped, never failed.
  Successful responses are checked against declared output schemas; schemas
  outside the supported subset are explicitly skipped. Reports carry
  `reportVersion` 1 and their scope, and count skipped checks separately
  from failures; the redundant "stable codes" check is gone.
- Invalid response structures, malformed JSONL, invalid UTF-8 and timed-out
  probes produce failures instead of tracebacks or indefinite waits. The
  per-invocation timeout is configurable with `--timeout` (10 seconds by
  default); stdin is closed, and POSIX timeout cleanup kills the process
  group. Completion expectations exclude unavailable and hidden commands.
  Regression tests include the counterexamples that previously passed the
  kit despite violating the contract.
- Include `LICENSE-SPEC` alongside `LICENSE` in release archives. Correct the
  release instructions to reflect that this repository publishes archives
  and does not currently declare a Homebrew formula.

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
