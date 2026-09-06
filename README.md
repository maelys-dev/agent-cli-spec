# agent-cli-spec

The `agent-cli/v2` contract: how a command-line program is driven the same
way by a human and by an agent. One catalog describes every command, the
program answers `describe` with it, success is one JSON envelope on stdout,
failure one on stderr, and the exit code says whether the work completed,
failed, or validated something that turned out invalid.

The contract was born in Hermes (TypeScript), was made a framework by
maelys-cli (C, `libmaelys_cli`) and is implemented again by maelys-release
(Python). This repository is the one place where it is written down, in a
form that any language can be checked against:

```text
spec/agent-cli.md       the normative text
spec/extensions.md      how a product extends it without bending it
schemas/*.json          the machine-readable form: describe document, envelope, version, records
conformance/run.py      the kit: drives a program and reports detected violations
examples/               maelys-cli's committed contract, as an illustration
```

## Checking a program

```sh
conformance/run.py /path/to/PROGRAM               # one line per check, exit 1 on any failure
conformance/run.py node dist/cli.js --json        # the report as JSON
conformance/run.py PROGRAM --report report.json   # keep the report, print the lines
conformance/run.py PROGRAM --timeout 20           # seconds per invocation (default 10)
```

Large catalogs can be inspected without transferring every descriptor:

```sh
PROGRAM describe --summary --prefix content --format json
```

This returns the compact descriptors whose identifier is `content` or starts
with `content.`. Use `describe COMMAND_ID` afterwards for one full descriptor.

The kit needs `python3` and nothing else. It only runs read commands and
invocations the contract says must be refused; it never passes `--apply`.
Each invocation has closed stdin and a timeout; on POSIX, timeout cleanup
kills its process group, including children holding stdout or stderr open.
Malformed JSON, invalid UTF-8 and timeouts are failures in the report.

The report covers catalog structure, built-ins and safe hidden-option
probes. Responses are checked against their declared `outputSchema` when
the kit supports its keywords and references (a subset of Draft 2020-12,
with local JSON Pointers and no embedded schema resources). Otherwise the report names
the unsupported schema as `SKIP` (`passed: null` in JSON); `counts` separates
passed, failed and skipped checks. A passing report means the executed
checks passed, not that the entire specification has been proved. The
`coverage` member names the scope and the remaining implementation tests:
business behavior, writes, protocol streams, delegates and terminal rendering.
The fixture's own terminal behavior is exercised by the repository's tests.

An implementation runs it in its own continuous integration on its own
binaries, pinned to a tag of this repository:

```sh
git clone https://github.com/maelys-dev/agent-cli-spec && git -C agent-cli-spec checkout v2.0.0
agent-cli-spec/conformance/run.py build/bin/my-program
```

## Reading the contract

[spec/agent-cli.md](spec/agent-cli.md) is normative; the schemas restate
it for machines, and where they disagree the text wins and the schema is a
defect to fix here. [spec/extensions.md](spec/extensions.md) says what a
product may add (`x-` members, domain error codes, transport options) and
what it may not (effects, output modes, exit codes).

## Versions

`agent-cli/v2` is the identifier every envelope carries. A compatible
clarification or addition is a new tag here (`v2.1.0`) and keeps the
identifier; an incompatible change starts `agent-cli/v3`. The changelog
names, for each tag, what an implementation has to change.

## Releasing

This repository releases through the maelys-release socle: a signed tag
`vX.Y.Z` publishes a tarball of the spec, the schemas and the kit, with a
provenance attestation. See `RELEASING.md`.

The specification (`spec/`) and the schemas (`schemas/`) are licensed
CC BY-SA 4.0 (`LICENSE-SPEC`): reuse and derive freely, credit
maelys-dev/agent-cli-spec, and publish any derived specification under the
same terms. The code (`conformance/`, `tests/`, `scripts/`) is MPL-2.0
(`LICENSE`).
