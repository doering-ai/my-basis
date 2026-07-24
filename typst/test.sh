#!/usr/bin/env sh
# Hermetic compile and envelope test for @dtm/basis.
set -eu

here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
test_root=$(mktemp -d "${TMPDIR:-/tmp}/typst-basis-test.XXXXXX")
trap 'rm -rf "$test_root"' EXIT HUP INT TERM

DATA_HOME="$test_root" "$here/install.sh" --copy
export XDG_DATA_HOME="$test_root"

package_root="$test_root/typst/packages/dtm/basis/0.1.0"
test -f "$package_root/LICENSE"

typst compile "$here/tests/components.typ" "$test_root/components.pdf"
typst compile "$here/tests/report-sample.typ" "$test_root/report-sample.pdf"
test -s "$test_root/components.pdf"
test -s "$test_root/report-sample.pdf"

envelope=$(
  typst eval 'query(<dtm-report>).first().value' \
    --in "$here/tests/report-sample.typ" \
    --format json
)
case "$envelope" in
  *'"schema":"dtm-report/1"'*'"genre":"reference"'*'"sid":"MEMY-599"'*) ;;
  *)
    printf '%s\n' "unexpected report envelope: $envelope" >&2
    exit 1
    ;;
esac

printf '%s\n' "@dtm/basis:0.1.0 passed compile and envelope gates"
