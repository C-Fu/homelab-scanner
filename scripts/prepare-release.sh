#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BIN="$ROOT/homelab-scanner"
OUT="$ROOT/release"

if [[ ! -x "$BIN" ]]; then
    echo "error: $BIN is missing or not executable" >&2
    exit 1
fi

VERSION="$("$BIN" --version | awk '{print $2}')"
SOURCE_VERSION="$(sed -n 's/^VERSION = "\(.*\)"/\1/p' homelab-scanner.py)"
if [[ -z "$VERSION" || "$VERSION" != "$SOURCE_VERSION" ]]; then
    echo "error: binary version '$VERSION' does not match source version '$SOURCE_VERSION'" >&2
    exit 1
fi

NAME="homelab-scanner-v${VERSION}-linux-amd64"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

DEST="$STAGE/$NAME"
mkdir -p "$DEST"
install -m 0755 "$BIN" "$DEST/homelab-scanner"
install -m 0644 \
    README.md \
    README.ms-MY.md \
    RELEASE_NOTES.md \
    homelab-scanner.py \
    homelab-sample-report-yyyymmdd-hhmmdd.md \
    "$DEST/"

rm -rf "$OUT"
mkdir -p "$OUT"
install -m 0755 "$BIN" "$OUT/$NAME"

STAMP="$(git log -1 --format=%cI 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ)"
tar --sort=name --mtime="$STAMP" --owner=0 --group=0 --numeric-owner \
    -C "$STAGE" -cf - "$NAME" | gzip -n > "$OUT/$NAME.tar.gz"

(
    cd "$OUT"
    sha256sum "$NAME" "$NAME.tar.gz" > SHA256SUMS
)

echo "Release assets written to $OUT"
echo
cat "$OUT/SHA256SUMS"
