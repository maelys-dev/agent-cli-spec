<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->
# Extending agent-cli/v2

The contract is deliberately closed: closed effects, closed value kinds,
closed descriptor members, closed exit codes. A product that needs more
extends the contract in the open rather than bending it, so that a generic
agent still reads the trunk and a product-aware agent reads the rest.

## Members

Any object of a `describe` document (the catalog, a descriptor, an operand,
an option) MAY carry members whose name starts with `x-`. The conformance
kit accepts them and checks nothing about their content; the product's
documentation defines them. A member without the prefix that the contract
does not define is a conformance failure.

Examples of what belongs there:

- an availability that depends on state rather than on the build
  (`"x-availability": ["draft", "approved"]`): `available` stays a boolean
  describing this build, the state rule lives in the extension;
- an idempotency class (`"x-idempotency": "guarded-retry"`);
- a repository context (`"x-repository": "required"`).

## Data

`data` of a success envelope is governed by the descriptor's `outputSchema`,
so a product shapes it freely; the trunk only fixes `mode` for transactions
and `count`/`records` for `json-records` commands.

## Error codes

A product MAY add error codes for boundaries of its own domain. It MUST
document them and MUST NOT reuse a listed code for another meaning. A
generic agent treats an unknown code as a failure it cannot retry blindly.

## Effects and output modes

Effects and output modes are not extensible. A command that runs a
non-transactional action is `execute`; one that hands its stdio to a
protocol is `stream` with `outputMode: "protocol-stream"` and a `protocol`
name (`mcp-json-rpc`, `git-smart`, ...). A human gate before a durable write
is a transaction whose `--apply` the human runs; a remote effect is
`execute`. Splitting a command into a plan and an `--apply` is always
preferable to a new effect.

## Global options

A product MAY accept more transport options on every command (a repository
path, an identity, a receipt). They MUST be listed in `globalOptions` of the
catalog with the same shape as the trunk's, and MUST NOT be spelled like a
trunk option with another meaning.

An implementation SHOULD offer a product an entry point that adds such an
option to `globalOptions` and accepts it on every command. Until it does, a
product that declares the same option, with one spelling and one shape, in
`input.options` of every command that accepts it implements this clause
conformantly: `describe` lists the option wherever it applies, and an agent
builds its invocation from `input` as always. The kit checks that the
trunk's options are in `globalOptions`; it accepts any product option listed
next to them and any repetition in `input.options`.
