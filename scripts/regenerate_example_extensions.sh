#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
dest_dir="${1:-$HOME/Library/Application Support/Sublime Text/Installed Packages}"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required: https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi

bespokeasm=(uv run --locked --project "$root_dir" bespokeasm)

if [[ ! -d "$dest_dir" ]]; then
  echo "Destination does not exist: $dest_dir" >&2
  exit 1
fi

configs=()
while IFS= read -r -d '' config; do
  configs+=("$config")
done < <(find "$root_dir/examples" -name '*.yaml' -print0)

if [[ ${#configs[@]} -eq 0 ]]; then
  echo "No ISA config files found under $root_dir/examples" >&2
  exit 1
fi

for config in "${configs[@]}"; do
  echo "Generating Sublime package for: $config"
  "${bespokeasm[@]}" generate-extension sublime -vvv -c "$config" -d "$dest_dir"
  echo "Generating VSCode package for: $config"
  "${bespokeasm[@]}" generate-extension vscode -vvv -c "$config"
  echo "Generating VIM package for: $config"
  "${bespokeasm[@]}" generate-extension vim -vvv -c "$config"
done
