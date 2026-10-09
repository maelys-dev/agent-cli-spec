# Changelog

What can make a program that passed the tag before fail the kit of a tag, for
whoever moves a pin. A tag that is not listed asks nothing of a program.

| Tag | A program fails from this tag when |
| --- | --- |
| 2.14.0 | it prints nothing and exits 0 for `COMMAND --help --format jsonl`; it ignores `--version` after a command; it answers `help` of an unknown identifier with the general help; it runs an unavailable command, or refuses its rendering or its help instead of naming the cause |
| 2.13.0 | it lists every command in `data.commands` for `help COMMAND_ID` |
| 2.12.0 | it puts `examples` in `describe --summary`; under `--help` its envelope names the command asked about and not `help` |
| 2.11.0 | it runs a command when `--help` follows its words; it declares an example its own catalog refuses |
| 2.10.0 | it declares a delegate (`external: true`) with an effect other than `execute`, or with a `protocol` |
| 2.9.0 | it declares `completion.install` and refuses a `--field` only after it has written; it declares `--expect` on a transaction without the reserved shape |
| 2.8.0 | its completion script fails under a second bash, the system's 3.2 included; its completion offers a hidden or an unavailable identifier after `help` or `describe` |
| 2.7.0 | its completion script has no file fallback in a shell; its `completion` writes on a terminal; `__complete` after a delegate's pattern offers the program's own options or differs between formats |

## Unreleased

Follow-up of an independent review: the kit's own weaknesses, what the
repository says of itself, and places where the reference fixture did less
than both maelys-cli implementations.

- **`__complete` offers the next word of a command of several words**
  (section 6): `write` and `commit` after `note`. The text said "command
  words" and the fixture offered the first word of every command again, so
  that `note <Tab>` proposed `note note`. The sentence now says which words;
  the fixture's oracle and its three static scripts follow, choosing the
  longest pattern the words begin with (`completion install` before
  `completion`). The kit checks the oracle on such words and drives the
  scripts on them. **A program whose `__complete` does not offer the next
  word of its multi-word commands fails from this version.**
- **The rendering options are named** (section 9): `--format`, `--json`,
  `--compact`, `--pretty`, `--pager` and `--field`, the ones that choose or
  shape what a command writes on stdout. The term was used six times and
  never defined, so that nobody could tell whether a stream command refuses
  `--color`. It does not, nor `--verbose`, `--progress` and
  `--non-interactive`. A delegate refuses nothing, which the same sentence
  used to deny.
- **The fixture's delegate delegates and its stream command keeps its
  stdout.** `tool` parsed its line and answered with an envelope; it now
  hands every word after its pattern to a child, `--help` and `--json`
  included, and ends with the child's status. `serve` accepted every
  rendering option and printed a line of text; it refuses them and writes
  nothing.
- **The value kinds have a grammar** (section 3), agreed with maelys-cli on
  what its two parsers accept. `integer`: an optional `-` then digits, no
  `+`, within 64 bits signed. `unsigned`: digits, at most 2^64 - 1. `size`:
  digits and at most one suffix among `K`, `M`, `G`, `T`, the powers of 1024,
  the product within 64 bits. `duration`: digits and one unit among `ms`,
  `s`, `m`, `h`, `d`, nothing composed. `hex` and `sha256`: lower case, of
  the declared width, `digits` being that width or the list of the widths
  accepted. `digest`: algorithm and digits in lower case, of the algorithm's
  width. `boolean`: `true` or `false`. A digit is `0` to `9`: one
  implementation read `١M` as a megabyte. An empty text is a `string` and
  nothing else. The suffix of a `size` is in upper case only: `duration` is
  already case-sensitive, and `m` already means minutes. **A program that
  declares an example whose value is outside these grammars fails from this
  version**; the kit judges values nowhere else, the generated lines do.
- **There is no short option, and a word that starts with one dash is
  refused** (section 8). Before `--`, such a word is neither an option nor an
  operand: `VALIDATION_FAILED` at step 2, in the name of the command
  resolved, `INVALID_COMMAND` when none was. `-` alone is an operand, and so
  is anything after `--`, where a negative number goes. `note write -f`
  created a file named `-f` in one implementation; a refusal is corrected by
  the caller, the file is not. The kit checks `help -x`, which a program
  that reads the word as an operand answers with `INVALID_COMMAND`. **A
  program that takes such a word as an operand fails from this version.**
- **Two options that set the same thing: the last one written wins**
  (section 8). `--json` and `--format` set the format, `--compact` and
  `--pretty` the layout of JSON. The text called `--json` an "exact alias",
  under which `--json --format text` could be read as a duplication; both
  maelys-cli implementations let the last one win and this repository's
  fixture let `--json` win. A wrapper sets a format and its user adds another
  at the end of the line. The same option written twice is still refused.
  **A program where `--json` wins over a later `--format text`, or
  `--compact` over a later `--pretty`, fails from this version.**
- **`preview`, `apply` and `commit` exist in a transaction only**: the
  `effect` of a command is `read`, `execute`, `stream` or the object of a
  transaction. The schema allowed them alone and nothing said what such a
  command does. **`passthrough: true` goes with `external: true` only**: a
  command that reads its own line declares `false`. **An identifier is
  segments separated by single dots**, `note.` and `note..write` are none,
  and `unknown` is reserved to the envelope of a line that resolved no
  command. No catalog read by maelys-cli or here declares any of these; **a
  program that does fails the schema from this version.**
- **`__complete` offers the declared choices** (section 6 always listed
  them): of an option's value after that option, of an operand where it
  begins. The fixture offered none; the kit checks the oracle and drives the
  scripts there. **A program that declares choices and does not offer them
  fails from this version.**
- **The fixture's richest command reads its own line.** `limits` was
  `passthrough` with fourteen typed options it never applied; it now refuses
  what its catalog refuses. The fixture judges every value by the grammars
  above and every line as a whole (`requires`, `conflictsWith`, groups,
  `input.constraints`, required options) from the catalog alone, where it
  knew two commands by hand.
- The generated lines try every way a value can be wrong that the judge can
  tell: a digit of another script, a number beyond 64 bits, a digest too
  short, a suffix or a unit that is none.
- `examples/maelys-cli.contract.json` is maelys-cli's committed contract at
  its v0.6.5; it was the one of the 2.2.1 era.
- Said in so many words, with no change of meaning: in a `requires` entry of
  `input.constraints` the first option requires the others, which is how the
  kit read it; `exitCodes` are the codes of the envelope, a stream command
  and a delegate carrying the member while their process ends as the
  underlying one does; an envelope names `help` when the line asked for a
  help and got it (section 7 said only "the resolved command"); `commands`
  holds the descriptors of a prefix too.

- **One wrong descriptor no longer ends the report.** A catalog with one
  stray member got a report of two lines, and its author learned of the next
  four hundred checks only after fixing it. The descriptor is left out, the
  report says so, and the other commands are checked. A catalog that is
  wrong beyond single descriptors still ends the run, and says so.
- **An answer the kit did not foresee is a line of the report**, `the kit
  completes its run`, not a traceback.
- What depends on an envelope that failed is reported `SKIP` in so many
  words; it used to vanish from the report. The report's `scope.skipped`
  lists what this run skipped, next to `scope.notChecked`, which says what no
  run checks.
- **Two checks passed for the wrong reason.** `duplicate --field` ran with
  `--json`, which refuses `--field` whatever is repeated: a program that
  never detected a repetition passed. And a script that carries its
  candidates "carries the catalog version" when the version was a substring
  of anything, `1` of `10`. Both now test what their name says. **A program
  that does not refuse a repeated `--field`, or whose static script does not
  carry its version as a word, fails from this version.**
- The README said the kit never passes `--apply`, false since 2.9.0; it says
  when it does. Its example pinned `v2.0.0`. It presents
  `tests/invocations.py`.
- `RELEASING.md` writes down what a change of the contract consists of and
  what is run before a tag, and `make siblings-check` runs the kit and the
  generated lines on a built checkout of maelys-cli.
- The tests launch the whole kit as a program once instead of three times.

## 2.14.0 — 2026-10-09

What a line is refused for, and in what order, around `--help`, `--version`
and a command the build cannot run. Found by an independent review and by
the generated command lines below; measured on maelys-cli's two
implementations before it was written.

- **The order of the refusals is a numbered list** (section 8), and `--help`
  has its place in it. What one option says alone is judged first and names
  the command: an option the command does not have, a repeated one, a value
  of the wrong kind. Then `--help` gives the help of the command, and what
  the line lacks as a whole is not held against it: a required option, an
  operand, an option another one requires. Help is asked on incomplete
  lines. From there the line is rendered as `help` is: `--format jsonl`
  without `--field` is refused as for `help`, in the name of `help`, and
  `--field commands` renders the identifier. **A program that prints nothing
  and exits 0 for `COMMAND --help --format jsonl` fails from this version**;
  maelys-cli's two implementations did until their own correction.
- **`--version` is `version` spelled as an option, as the first word of the
  line and nowhere else** (section 6). After a command it is an option that
  command does not declare, and the line fails with `VALIDATION_FAILED`. The
  text said only "`version`, also `--version`", and this repository's fixture
  ignored it after a command: `completion install bash --apply --version`
  installed the completion, the twin of the `--help` defect of 2.11.0. **A
  program that ignores `--version` after a command fails from this version.**
- **`help` of an identifier the catalog does not have fails with
  `INVALID_COMMAND`**, as `describe` does (section 6). The fixture answered
  with the general help. **A program that does so fails from this version.**
- **Invoking a command whose `available` is `false` fails and does not run**
  (sections 2 and 8): with `UNSUPPORTED` when the function is absent from the
  build, or with the listed code that names the cause better, the message
  carrying the reason. It is the fifth step of the order: the line is read
  first, so a wrong line is told so; the rendering is never reached, so
  `--format jsonl` names the cause and not the format; and its help is given,
  as `describe` answers for it. The text declared the member and the code and
  never joined them; the fixture ran the command. **A program that runs an
  unavailable command, or refuses its rendering or its help instead of
  naming the cause, fails from this version.**
- A word after `--` is an operand whatever its spelling, so `--help` and
  `--version` there ask nothing, and `--help=false` asks no help (section 8).
  Both were already what the two maelys-cli implementations and the fixture
  did. What `--json=false` means where the environment selects `json` is
  left open: maelys-cli reads it as a choice of text, the fixture as a flag
  not given.
- The kit checks each of these on lines that are safe to run: `version` with
  an operand, `help --version`, `help` of an unknown identifier, an unknown
  option before `--help`, `completion --help` without its operand, `version
  --help --format jsonl` with and without `--field`, `describe --prefix
  version --help` where `--prefix` requires `--summary`, an unavailable
  command that reads and needs no operand (invoked, with `--format jsonl`,
  and with `--help`), and `completion install SHELL --apply --version` in a
  home the kit made. Its report says what of the order it does not check.
- **The fixture has a parser for the number of operands**, which section 8
  always listed among the refusals and the fixture never checked (`version
  extra`, `note write` without its file), and judges a `digest` value where
  every option value is judged. It follows the seven steps to the letter,
  gives the help of `help` itself, and takes a default format from
  `CONFORMANT_FORMAT`, as section 5 allows an implementation to. Seven
  defects prove the new checks (`version-ignored`, `arity-unchecked`,
  `help-checks-arity`, `help-jsonl-silent`, `unavailable-runs`,
  `unavailable-after-rendering`, `help-unknown-general`).

- **The reference program is held to generated command lines.** Two contract
  violations were found in the fixture by accident (2.9.0: it wrote before it
  refused `--field`; 2.11.0: it ran a command under `--help`). A test now
  builds about a thousand lines from the fixture's own catalog, the plain
  line of each command, each rule broken once and random mixtures, runs each
  in a home of its own, and holds the fixture to what the contract says of
  every one: exit code, envelope, an empty stdout on failure, nothing written
  without `--apply`, on a failure or under `--help`, and a refusal of
  whatever the catalog refuses. The judge is the kit's own reading of an
  example, turned around. It is a test of this repository, not a part of the
  kit: it runs `--apply`, and lines a product may not survive.
- It found the two gaps of the fixture closed above, the number of operands
  and `--version` after a command, and then a third, an option value of kind
  `digest` that the fixture judged too late. It holds the order of the
  refusals too: an unavailable command against every rendering option and
  `--help`, words after `--`, flags set to false, both spellings of a value,
  lines that name no command, and every line again with the default format
  the environment selects. `python3 tests/invocations.py PROGRAM` points it at
  another program, by whoever owns that program: delegates, `passthrough` and
  stream commands are never run, and lines carrying `--apply` only on
  request. Two of its first invariants were this repository's own habits and
  not the contract's, as maelys-cli's programs showed: that nothing the
  catalog accepts is refused, and that a success prints in text mode. Both
  now hold of the reference program only.
- **The kit read `--flag=false` as the flag given.** Found by the same lines:
  an example carrying `--strict=false` was held to what `--strict` requires,
  conflicts with or is grouped with. Section 2 says `--flag=false` is
  accepted, and a flag set to false is a flag not given; the kit now reads it
  so. No correct catalog changes verdict; one whose example spelled a flag
  false could have failed wrongly.

## 2.13.1 — 2026-10-09

- **A hidden command asked by its identifier is the one `commands` names.**
  Section 6 said of the data of `help` that "a hidden command is never among
  them", in the paragraph that also says `commands` holds the one command
  asked for `help COMMAND_ID`: for `help` of a hidden command the two
  sentences contradicted each other. The first was meant for the general
  help and now says so. A hidden command is listed by `describe` and never
  offered (section 2); answering who names it is not offering it, and an
  empty list would lose the identifier in the one case where the general help
  does not give it. Reported by maelys-cli. Its two implementations and this
  repository's fixture already answer so. No requirement, no schema and no
  kit check changes: a program conformant to 2.13.0 is conformant to this
  version.
- A test holds the fixture to that answer.

## 2.13.0 — 2026-10-09

- **In the data of `help`, `commands` names the commands the text shows**
  (section 6): every command it lists for `help`, the one asked for `help
  COMMAND_ID` and for `--help` after a command, and never a hidden one. The
  text said only `{"text": ..., "commands": [ids]}`, and this repository's
  fixture returned every command whatever was asked. Since 2.12.0 the
  envelope names `help` under `--help`, so `commands` is the only place where
  the answer says which command it is about; an agent goes from there to
  `describe COMMAND_ID` without reading `text`. Asked by maelys-cli, whose two
  implementations already answer so. The kit checks `help`, `help version`
  and `version --help`. **A program that lists every command for `help
  COMMAND_ID` fails from this version.** A help the contract does not
  describe, one for a command namespace or for a topic, follows the same
  sentence and is not checked.
- Two defects of the fixture (`help-lists-all`, `help-lists-hidden`) prove the
  checks.
- Adopts maelys-release v0.63.2: two pinned workflows, nothing asked of this
  repository.

## 2.12.0 — 2026-10-08

Two answers from maelys-cli to the points 2.11.0 left open, received after
its tag. No implementation had adopted 2.11.0 yet.

- **`describe --summary` omits `examples`**, as it omits `outputSchema` and
  `exitCodes` (sections 1 and 2); 2.11.0 put them in every form. The summary
  is the form an agent reads to choose a command, and an example serves once
  the command is chosen, in `describe COMMAND_ID`. Measured by maelys-cli on
  its example program, the summary weighs 18 kilobytes against 31 for the
  catalog; it estimates two examples per command at about a third more.
  `schemas/describe.json` forbids the member in a summary, and the kit checks
  it. **A program that put examples in its summary, as 2.11.0 said, fails
  from this version.**
- **Under `--help` after a command, the envelope names `help`** (section 6).
  2.11.0 left it open, and two implementations answered differently, one
  with `help`, one with the command asked about. `command` says how to read
  `data`, and that `data` is the help's: it would not validate against the
  `outputSchema` of the command asked about. A line that fails instead names
  the command it resolved, as any failure does. The kit checks it on `version
  --help`. **A program that names the command asked about fails from this
  version.**
- The kit's own expectation of an envelope's `command` follows: for a
  successful line that carries `--help` after a command which is neither a
  delegate nor `passthrough`, it expects `help`.
- Two defects of the fixture (`summary-examples`, `help-names-command`) prove
  the checks.

## 2.11.0 — 2026-10-08

Asked by maelys-cli, which is rebuilding the help its framework renders.

- **A command may declare examples** (section 2). `examples` is an optional
  member of the descriptor, in every form of `describe`: entries `{"words":
  [...], "summary": "..."}`, `words` being the command line without the
  program's name, one word per element, starting with the command's
  `pattern`. An example MUST be an invocation the command accepts: declared
  options, none of them hidden, values of the declared kind, operands of the
  declared arity, `requires`, `conflictsWith`, `group` and `input.constraints`
  holding, and real values, never a placeholder. Examples live in READMEs
  today and drift there; one product's README names two commands its
  installed binary does not have. `help COMMAND_ID` SHOULD show them.
- **Nothing runs an example.** The kit checks each one by reading the
  catalog: it applies to the words every rule the catalog states. Running an
  example with `--help` was considered and dropped, an example being free to
  carry `--apply`. The kit does not judge what a command checks beyond its
  declared grammar, the words after a delegate's or a `passthrough` pattern,
  a value of a kind whose grammar the contract leaves open (`size`,
  `duration`, `hex`), nor whether `help` shows an example; its report says
  so.
- **No category member.** A command namespace, the prefix `describe --summary
  --prefix` selects, is the grouping: the largest catalog measured has 15
  commands, and nothing could check a category.
- **`--help` after the words of a command gives its help, and the command
  does not run** (section 6), whatever else the line carries, `--apply`
  included. The text said `--help` is "the help of the selected command" and
  nothing more, and this repository's reference fixture ran the command:
  `completion install bash --apply --help` installed the completion. The kit
  now checks that `version --help` gives a help and not the identity of the
  product, and that `completion install SHELL --apply --help` writes nothing
  in a home the kit made. **A program that runs a command when `--help`
  follows its words fails from this version.** A `passthrough` command and a
  delegate receive `--help` verbatim, as before.
- The fixture declares examples on four commands, shows them in `help
  COMMAND_ID`, and gains six defects (`help-runs` and five `example-*`) that
  prove the checks.
- Adopts maelys-release v0.63.0: two pinned workflows, nothing asked of this
  repository.

## 2.10.0 — 2026-10-07

- **What a delegate is.** The effects table said `stream` reserves stdio "for
  a declared protocol", while sections 2 and 9 allow a command that relays a
  child's stdio and declares none; and `external` said only "hands over to
  another executable", which fits every command that starts a program. The
  text now gives the criterion maelys-cli's two implementations already
  apply: a command is a delegate, `external: true`, when the catalog does not
  own what follows its pattern, the words, the help and the completion there
  being the other executable's. A command that keeps its own grammar and
  relays the stdio of a child it starts is a `stream` command with `external:
  false`, whether it names the child or receives it as an operand. The
  effects table says so for `stream`.
- **A delegate declares the effect `execute` and no `protocol`**, and
  `schemas/describe.json` requires it. No catalog known to this repository
  moves: maelys-cli's frameworks cannot declare a delegate otherwise, and its
  example here already conforms. A program that declared a delegate with
  another effect or with a protocol fails the schema from this version, hence
  a minor. Two defects of the fixture (`delegate-stream`, `delegate-protocol`)
  prove the rule.
- A proposal to make every command that hands its stdio to another executable
  a delegate was considered and dropped: measured on maelys-cli, it would
  change what `--help`, the options and the completion of such a command do,
  and it would break a product whose `stream` command has options of its own.

## 2.9.0 — 2026-10-06

Two guarantees about what a caller may conclude from a failure, and a way to
bind an application to the plan that was reviewed. All three were raised by a
review of the contract and of maelys-cli.

- **A refusal to render no longer follows a write.** Section 5 said that
  `--field` of a name `data` does not carry fails with `VALIDATION_FAILED`,
  which is only known once the command has run: `completion install bash
  --apply --field no-such-member` installed the script, then answered with a
  failure a caller reads as "nothing changed". This repository's reference
  fixture did exactly that. On a command that may write, a transaction with
  or without `--apply` and an `execute` command, the name is now checked
  before the command runs and against the catalog: it MUST be listed in the
  top-level `required` of the command's `outputSchema`. A member the schema
  leaves optional is refused there too. A `read` command decides on `data` as
  before. A program that wants `--field` on a transaction lists the members
  it always returns in `required`; **a transaction or an `execute` command
  whose `outputSchema` requires no member accepts no `--field` from 2.9.0**,
  where it accepted any member of its result before.
- **A refusal caused by the format the environment selects is reported
  before the command runs** (section 5): it is a rendering constraint of
  section 8, whatever selected the format.
- **A failure leaves stdout empty in every format, `jsonl` included**
  (section 7). The text already said "stdout empty"; it now says that a
  command writes no record before it knows that it succeeded, and that output
  flowing while the work runs is a `protocol-stream`.
- The kit checks the first point where it can do so without risk, on the
  reserved `completion install`: in a home it made, and only when the plan
  names paths inside it, it runs `--apply` with a `--field` absent from
  `outputSchema` and with one the schema leaves optional, and requires
  `VALIDATION_FAILED` and no file written; it also requires that a `--field`
  the schema requires is rendered. **A program that passed 2.8.1 and
  declares `completion.install` fails until it checks the name first.** The
  kit does not check the rule on other commands, a format the environment
  selects, or a failure in the middle of a `jsonl` rendering; its report says
  so.
- The fixture declares what its transactions always return, and two defects
  (`field-after-write`, `field-optional-after-write`) prove the kit sees the
  difference.
- **A transaction may bind its application to the plan the caller
  reviewed** (section 4). Re-validation says that the state still allows a
  transaction, not that the action is the one that was reviewed: `--apply`
  plans again and applies that plan, so a state that moved, or an argument
  the caller changed, went through. Products had each their own remedy
  (`REVISION_CONFLICT` in Hermes, a `precondition` object elsewhere). The
  contract reserves one spelling, offered or not: the option `--expect
  FINGERPRINT` and the member `data.fingerprint`, a `sha256:HEX` the program
  computes over the action and over the state that action would touch. With
  `--apply --expect` a fingerprint that no longer matches fails with
  `PRECONDITION_FAILED` before anything is written. The product chooses how
  it computes the fingerprint; the contract says what equality means. After
  an `--apply` whose outcome is unknown, a new plan says whether the action
  is still to be done. No program has to offer this, and a caller that never
  passes `--expect` is served as before; `completion install` may carry the
  pair, and `schemas/completion-install.json` accepts `fingerprint`.
- The kit checks the binding where a catalog declares it. On every
  transaction that declares `--expect`: its shape, and `fingerprint` in the
  `required` of `outputSchema`. On `completion install`: two plans on the same
  state carry the same fingerprint, `--expect` without `--apply` is refused,
  `--apply` with another fingerprint fails with `PRECONDITION_FAILED` and
  writes nothing, and the fingerprint changes once the kit has put another
  content where the script goes. It never runs an installation that would
  succeed, and it cannot tell what a product's own fingerprint covers; its
  report says so. Three defects of the fixture (`expect-without-fingerprint`,
  `expect-after-write`, `fingerprint-constant`) prove these checks.
- `spec/extensions.md` said the kit never runs `--apply` on a reserved
  command; since the first point above it runs it with an option the program
  must refuse, and the text now says that.

## 2.8.1 — 2026-10-05

- **The kit failed a correct program on macOS when a completion script was
  longer than 4096 bytes.** `completion SHELL on a terminal prints the script
  it prints into a pipe` read the script back through a pseudo-terminal and
  turned each `\r\n` into a newline. Past 4096 bytes the macOS terminal can
  write `\r\r\n` for one newline, so a script with a line ending on that
  boundary came back one byte longer and the check failed, every time for
  that text. Reported by maelys-cli, whose static scripts are 5 to 7
  kilobytes. The pseudo-terminal now passes output through untouched and the
  comparison is byte for byte; where the terminal cannot be set that way the
  two checks are skipped. No requirement and no schema changes, and no other
  verdict moves: a program that passed 2.8.0 passes still.

## 2.8.0 — 2026-10-05

Five points reported by maelys-cli on moving its pin to 2.7.0, one of them a
regression of the kit.

- **The kit failed on a program named by a relative path.** Since 2.7.0 the
  completion scripts are driven from another directory, and `conformance/run.py
  build/bin/my-program`, the form the README shows, ended with the single
  line `FAIL program can be run`, every later check lost. The path is made
  absolute, a test runs the kit that way, and a pseudo-terminal that cannot
  be had is now a `SKIP` rather than the end of the report.
- **The kit drives every bash it finds**, the system's included. It drove
  the one on the PATH alone: on a macOS where Homebrew installed bash 5, the
  bash 3.2 defect of 2.7.0's own fixture and of both reference
  implementations was invisible, while `/bin/bash` is the one a user of the
  system shell has. A second bash gets its own checks, named after its
  version and path.
- **Section 9: the program adds no word of its own to its delegate's.** The
  text said the program's own options were not among the delegate's words,
  and the kit intersected names. A delegate built on the same trunk has the
  same global options and accepts them: `--format` after its pattern is its
  own, spelled like the program's, and a program relaying it faithfully
  would have failed. The check is removed; the rule cannot be told from
  names, and the report says so. The equality of formats stays checked.
- **Section 6: a hidden or an unavailable command is never offered, as a
  word or as an identifier.** "Never an unavailable command" left the
  identifiers after `help` and `describe` undecided, and the two reference
  implementations had decided differently. `describe` still answers for
  such a command; completion does not propose it. The kit now checks the
  identifiers after `help` and `describe`, which it never had, and this
  repository's fixture, which offered none, offers them.
- Section 6 says what it left open: whether options are offered before a `-`
  is typed is the implementation's choice. A script is compared with its own
  `__complete`, never with another implementation's.
- **A minor, not a patch**: two changes can alter a verdict. A script that
  fails under a second bash, and a program that offers a hidden or an
  unavailable identifier after `help` or `describe`, passed the 2.7.1 kit
  and fail this one. A program that does neither moves its pin and nothing
  else.

## 2.7.1 — 2026-10-04

- The sentence naming the implementations, in section 0 and in the README,
  said the Python implementation was `maelys-release`. It is maelys-cli's
  Python module, `maelys_cli.py`, the counterpart of `libmaelys_cli`;
  `maelys-release` is a product built on it. Hermes is unchanged: it is
  TypeScript, as the text said. No requirement, no schema and no kit check
  changes: a program conformant to 2.7.0 is conformant to 2.7.1.

## 2.7.0 — 2026-10-04

- Section 6: a completion script may carry its candidates instead of calling
  the program at each completion. The text said the script "calls `PROGRAM
  __complete`", and the kit looked for those characters in it, which a
  comment satisfied and which proved nothing about what a Tab offers. The
  rule is now behavioral: for every word list a script offers the words
  `__complete` returns, no others, and falls back to the shell's file
  completion when that list is empty. `__complete` is the oracle and the
  script a rendering of it, dynamic or static. A script that carries its
  candidates MUST carry the `version` of the catalog they come from, and
  calls `__complete` after a delegate's pattern, whose words no catalog
  holds. Decision: the gain is a Python program's start-up at each Tab, a
  compiled one answers fast, so static is permitted and never required. Not
  in the contract, on purpose: caches, file dates, catalog digests, the
  number of processes per Tab. How staleness is detected is the
  implementation's business; a rule on file dates fails under Nix, Homebrew
  bottles, pip launchers and downgrades.
- Section 4: a terminal never changes an effect. It changes presentation,
  never whether a command writes; a `read` that writes when stdout is a
  terminal is not a `read`. This was a consequence of the effects table that
  no sentence spelled out and no check could see, the kit running without a
  terminal. Reported with a product that installed its completion when its
  `completion` command met a terminal.
- `completion.install` is reserved: `completion install SHELL [--apply]`, a
  transaction whose plan names every file and writes nothing. A program
  offers it or not; one that does declares exactly this shape, for the
  reason `--apply` has one spelling. `schemas/completion-install.json` gives
  its `data`. Decision: installation is not mandatory, writing into a
  startup file is intrusive and packaged programs install their completion
  through their package; but two products spelling it two ways is what the
  contract exists to prevent. `spec/extensions.md` says a product MUST NOT
  declare another command for the same intent.
- Section 9: `__complete` after a delegate's pattern returns the delegate's
  words, the same in every format, or none, and never the program's own
  options. The two reference implementations disagreed: one forwarded to the
  delegate in text mode and returned nothing in JSON, the other offered the
  global options a delegate refuses.
- The kit drives the script in each of bash, zsh and fish that is installed
  and compares it with `__complete`; an absent shell is `SKIP`. It runs
  `completion SHELL` on a pseudo-terminal in an empty home and checks that
  nothing is written and the same script is printed. Where a catalog
  declares `completion.install` it checks the shape, runs the plan in an
  empty home and checks that nothing is written; it never passes `--apply`.
  The fixture prints real scripts for the three shells, dynamic or carrying
  their candidates, and seven defects prove the checks fail.
- **This is a minor and not a patch**: a program conformant to 2.6.0 fails
  this kit when its script has no file fallback in a shell, when its
  `completion` writes on a terminal, or when `__complete` after a delegate's
  pattern offers its own options or differs between formats.
- Adopts maelys-release v0.62.3: two pinned workflows, nothing asked of this
  repository. `dependencies/packages` declares zsh and fish for the Linux
  runners, so the tests exercise the three shells.

Migration: whoever writes the trunk keeps its completion scripts, provided
each falls back to file completion in its shell, `completion` writes nothing
on a terminal, and `__complete` after a delegate's pattern returns the same
records in every format without the program's own options. A static script
and `completion install` are declared as section 6 says by an implementation
that offers them. A product built on a framework declares nothing of this
and moves with its framework's release (section 11).

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
