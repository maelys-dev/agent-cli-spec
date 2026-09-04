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
conformance/run.py      the kit: drives any program and reports every violation
examples/               maelys-cli's committed contract, as an illustration
```

## Checking a program

```sh
conformance/run.py /path/to/PROGRAM               # one line per check, exit 1 on any failure
conformance/run.py node dist/cli.js --json        # the report as JSON
conformance/run.py PROGRAM --report report.json   # keep the report, print the lines
```

The kit needs `python3` and nothing else. It only runs read commands and
invocations the contract says must be refused; it never passes `--apply`.
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

Code is MPL-2.0; the text of the specification and the schemas are CC0-1.0.
