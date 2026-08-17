#!/usr/bin/env bash
# Bump every version-pinning reference in README and the documentation tree.
#
# Patterns rewritten:
#   uvx.sh/confluence-markdown-exporter/<version>/install.sh
#   uvx.sh/confluence-markdown-exporter/<version>/install.ps1
#   confluence-markdown-exporter==<version>
#   spenhouet/confluence-markdown-exporter:<version>    (Docker pin; :latest left alone)
#
# Auto-discovers any file under README.md or docs/ that contains one of the
# patterns above, so no explicit file list needs maintaining as docs change.
#
# Usage: scripts/bump-docs-version.sh <new-version>
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <new-version>" >&2
  exit 1
fi
NEW="$1"

# Validate: tolerate "1.2.3", "1.2.3a4", "1.2.3rc1" etc. (anything pip accepts).
if [[ ! "$NEW" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z]+)*$ ]]; then
  echo "error: '$NEW' does not look like a valid version" >&2
  exit 1
fi

PATTERN='(uvx\.sh/confluence-markdown-exporter/[^/[:space:]]+/install\.(sh|ps1)|confluence-markdown-exporter==[0-9]|spenhouet/confluence-markdown-exporter:[0-9])'

mapfile -t files < <(
  for root in README.md docs; do
    [[ -e "$root" ]] || continue
    if [[ -f "$root" ]]; then
      echo "$root"
    else
      find "$root" -type f \( -name '*.md' -o -name '*.mdx' \)
    fi
  done | xargs -r grep -lE "$PATTERN" 2>/dev/null
)

if [[ ${#files[@]} -eq 0 ]]; then
  echo "No files contain version-pin patterns; nothing to update."
  exit 0
fi

for f in "${files[@]}"; do
  sed -i \
    -e "s|uvx\.sh/confluence-markdown-exporter/[^/[:space:]]*/install\.sh|uvx.sh/confluence-markdown-exporter/${NEW}/install.sh|g" \
    -e "s|uvx\.sh/confluence-markdown-exporter/[^/[:space:]]*/install\.ps1|uvx.sh/confluence-markdown-exporter/${NEW}/install.ps1|g" \
    -e "s|confluence-markdown-exporter==[0-9A-Za-z.\\-]*|confluence-markdown-exporter==${NEW}|g" \
    -e "s|spenhouet/confluence-markdown-exporter:[0-9][0-9A-Za-z.\\-]*|spenhouet/confluence-markdown-exporter:${NEW}|g" \
    "$f"
  echo "updated: $f"
done
