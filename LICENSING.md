# Licensing

Copyright 2026 David Bromberg.

This repository carries two licences, one for what it says and one for what
it runs.

## The specification and the schemas: CC BY-SA 4.0

`spec/` and `schemas/` are licensed CC BY-SA 4.0, whose terms are in
[`LICENSE-SPEC`](LICENSE-SPEC). Reuse and derive freely, credit
maelys-dev/agent-cli-spec, and publish any derived specification under the
same terms. Each file of `spec/` carries the identifier in an HTML comment;
the schemas carry none, JSON having no comment, and are covered by this
statement and by the `README`.

## Source code: MPL-2.0

`conformance/`, `tests/` and `scripts/` are available under the Mozilla Public
License 2.0. The complete terms are in [`LICENSE`](LICENSE). Every file
carries `SPDX-License-Identifier: MPL-2.0`.

The MPL applies file by file. A program that links this code, statically or
otherwise, keeps its own license (section 3.3 of the MPL); only a modified
covered file must remain available in Source Code Form under MPL-2.0.

## Installed agent texts: CC-BY-4.0

The managed blocks of `AGENTS.md` and `CLAUDE.md` are installed from the
Maelys distributions' `share/agents/` texts under CC-BY-4.0, with attribution
to David Bromberg. Their notices identify the source and link to the license:
https://creativecommons.org/licenses/by/4.0/. Retain attribution and indicate
changes when sharing adaptations. This applies to the installed blocks,
not unrelated product-specific content outside them. When adopting another
distribution, check the actual notices of the texts it installs.

## Redistributed material

None. This repository declares no dependency, links nothing, and its released
archives carry only its own files. The conformance kit and its validator use
the Python standard library alone.

## Documents engaged publicly

The released archive carries `spec/`, `schemas/`, `conformance/`, `examples/`,
`VERSION`, `CHANGELOG.md`, `README.md`, `LICENSE` and `LICENSE-SPEC`. Those
documents stay in this repository: an implementation pins a tag and reads them
from the archive. `RELEASING.md`, `SECURITY.md` and this file are engaged by
the repository itself and stay here too.
