#!/usr/bin/env sh
# install.sh — install @dtm/basis into the local Typst package tree.
#
# Load-bearing, not dev convenience: `typst query` (used by the Latent Library
# collector and Nucleus ingest to read the report envelope) resolves `@dtm/basis`
# from the data-dir package tree, so every host that renders or ingests house
# reports needs this installed.
#
# Idempotent. Default is a dev symlink (edits reflect immediately); `--copy`
# materializes a release snapshot instead.
#
#   ./install.sh            # dev symlink into $XDG_DATA_HOME/typst/packages/dtm/basis/<ver>
#   ./install.sh --copy     # copy instead of symlink
#   DATA_HOME=/tmp/x ./install.sh   # override the target root (for hermetic tests)
set -eu

here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
mode="symlink"
[ "${1:-}" = "--copy" ] && mode="copy"

version="$(sed -n 's/^version *= *"\(.*\)"/\1/p' "$here/typst.toml" | head -1)"
if [ -z "$version" ]; then
  echo "install.sh: could not read version from typst.toml" >&2
  exit 1
fi

data_root="${DATA_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}}"
dest="$data_root/typst/packages/dtm/basis/$version"

mkdir -p "$(dirname "$dest")"
rm -rf "$dest"

if [ "$mode" = "copy" ]; then
  # Copy the package files only (skip VCS, tests, and generated artifacts).
  mkdir -p "$dest"
  for f in typst.toml lib.typ theme.typ callouts.typ report.typ problem-space.typ packages.typ README.md LICENSE; do
    [ -e "$here/$f" ] && cp "$here/$f" "$dest/"
  done
  echo "installed (copy) @dtm/basis:$version -> $dest"
else
  ln -s "$here" "$dest"
  echo "installed (symlink) @dtm/basis:$version -> $dest -> $here"
fi
