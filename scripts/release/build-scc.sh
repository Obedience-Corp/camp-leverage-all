#!/usr/bin/env bash
set -euo pipefail

# Build the same static helper on every target, retaining its dependency notices.
root="$(cd "$(dirname "$0")/../.." && pwd)"
stage="$root/build/release-input"
mkdir -p "$stage/bin" "$stage/licenses"
GOBIN="$stage/bin" CGO_ENABLED=0 go install -trimpath -ldflags="-s -w" github.com/boyter/scc/v3@v3.7.0
GOBIN="$stage/bin" go install github.com/google/go-licenses@v1.6.0
module_dir="$(go env GOMODCACHE)/github.com/boyter/scc/v3@v3.7.0"
(
    cd "$module_dir"
    "$stage/bin/go-licenses" save . --save_path="$stage/licenses/scc" --force
    "$stage/bin/go-licenses" report . > "$stage/licenses/scc-dependencies.csv"
)
go_root="$(go env GOROOT)"
if [[ -f "$go_root/LICENSE" ]]; then
    cp "$go_root/LICENSE" "$stage/licenses/Go-LICENSE"
else
    cp "$go_root/../LICENSE" "$stage/licenses/Go-LICENSE"
fi
"$stage/bin/scc" --version
