# Security policy

## Reporting a vulnerability

Report a suspected vulnerability privately, through the GitHub advisory form
of this repository (`Security` tab, `Report a vulnerability`). Do not open a
public issue for it, and do not describe it in a pull request.

Expect an acknowledgement within a few days. A confirmed report gets a fix,
a released version and a credit in `CHANGELOG.md` unless the reporter asks
otherwise.

## Supported versions

The latest released `vX.Y.Z` receives fixes. Older versions do not: the fix
lands in a new release, and an implementation moves the tag it pins to it.

## Scope

agent-cli-spec as published from this repository: the normative text, the
schemas and the conformance kit. The kit runs a program the reporter names
and only its read commands; a defect that lets it run anything else belongs
here. A defect in a program the kit checks belongs to that program's
repository, and a defect in a Maelys dependency to that repository.
