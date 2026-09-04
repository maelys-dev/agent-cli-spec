#!/bin/sh
# SPDX-License-Identifier: MPL-2.0
# usage: scripts/package-release.sh TARGET   (linux-x86_64 | linux-arm64 | macos-arm64)
# Runs the tests, then leaves agent-cli-spec-VERSION-TARGET.tar.gz with its
# .sha256 in dist/: the specification, the schemas and the conformance kit.
# The content does not depend on the target; the socle builds one archive
# per target and the name keeps them apart.
set -eu
root=$(CDPATH='' cd -- "$(dirname "$0")/.." && pwd)
cd "$root"
target=${1:?TARGET}
case $target in linux-x86_64|linux-arm64|macos-arm64) ;; *) echo "unsupported target: $target" >&2; exit 64 ;; esac
version=$(cat VERSION)
python3 -W error -m unittest discover -s tests >/dev/null
work=$(mktemp -d "${TMPDIR:-/tmp}/agent-cli-spec-package.XXXXXX")
trap 'rm -rf "$work"' EXIT HUP INT TERM
stage="$work/agent-cli-spec-$version"
mkdir -p "$stage"
cp -R spec schemas conformance examples VERSION CHANGELOG.md LICENSE README.md "$stage/"
rm -rf "$stage/conformance/__pycache__"
mkdir -p dist
name="agent-cli-spec-$version-$target.tar.gz"
COPYFILE_DISABLE=1 tar -czf "dist/$name" -C "$work" "agent-cli-spec-$version"
if command -v sha256sum >/dev/null 2>&1; then (cd dist && sha256sum "$name" >"$name.sha256")
else (cd dist && shasum -a 256 "$name" >"$name.sha256"); fi
printf '%s\n' "dist/$name"
