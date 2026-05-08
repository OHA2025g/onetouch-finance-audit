#!/usr/bin/env bash
# Create a distributable zip of this repository.
# Default: all files under the repo except dependency trees, VCS, and common caches.
# Use --git for a smaller archive of only git-tracked files at HEAD (no large untracked artifacts).
#
# If this folder lives on Desktop/Documents with iCloud sync, archiving can take a long time
# because every file read may wait on cloud download. Clone or copy the repo to a local path
# (for example under your home directory on the built-in disk) and run this script there.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="workspace"
OUT=""

usage() {
  sed -n '1,120p' <<'EOF'
Usage: make-project-zip.sh [options] [OUTPUT.zip]

  OUTPUT.zip   Destination (default: ../onetouch-audit-ai-complete.zip next to repo folder)

Options:
  --git        Use git archive HEAD (tracked files only; requires a clean-enough git state)
  --workspace  Walk the working tree excluding node_modules, .git, caches (default)

Examples:
  ./scripts/make-project-zip.sh
  ./scripts/make-project-zip.sh /tmp/onetouch-audit-ai-complete.zip
  ./scripts/make-project-zip.sh --git ./onetouch-audit-ai-git.zip
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --git) MODE="git"; shift ;;
    --workspace) MODE="workspace"; shift ;;
    -*)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      OUT="$1"
      shift
      ;;
  esac
done

if [[ -z "$OUT" ]]; then
  OUT="$(dirname "$REPO_ROOT")/onetouch-audit-ai-complete.zip"
fi

OUT="$(cd "$(dirname "$OUT")" && pwd)/$(basename "$OUT")"
PREFIX="$(basename "$REPO_ROOT")"

if [[ "$MODE" == "git" ]]; then
  (cd "$REPO_ROOT" && git archive --format=zip --prefix="${PREFIX}/" -o "$OUT" HEAD)
  echo "Wrote $OUT (git archive HEAD, prefix ${PREFIX}/)"
  exit 0
fi

tmp_zip="/tmp/${PREFIX}.zip.$$"
rm -f "$tmp_zip"
cleanup() { rm -f "$tmp_zip"; }
trap cleanup EXIT

python3 - "$REPO_ROOT" "$tmp_zip" "$PREFIX" <<'PY'
import subprocess, sys, zipfile
from pathlib import Path

root = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2])
prefix = sys.argv[3]

prune = (
    "node_modules", ".git", ".pytest_cache", "__pycache__", ".ruff_cache",
    ".next", ".turbo", "dist", "build", "coverage", ".venv", "venv",
)
parts = ["find", ".", "("]
for i, n in enumerate(prune):
    parts += ["-o", "-name", n] if i else ["-name", n]
parts += [")", "-prune", "-o", "-type", "f", "-print"]

raw = subprocess.check_output(parts, cwd=root)
paths = sorted(
    p[2:] if p.startswith("./") else p
    for p in raw.decode().strip().split("\n")
    if p
)

out.unlink(missing_ok=True)
n = 0
with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for rel in paths:
        if rel.endswith(".DS_Store"):
            continue
        fp = root / rel
        if fp.is_file():
            z.write(fp, f"{prefix}/{rel}")
            n += 1
print(f"files={n} bytes={out.stat().st_size}")
PY

mv -f "$tmp_zip" "$OUT"
trap - EXIT
echo "Wrote $OUT"
