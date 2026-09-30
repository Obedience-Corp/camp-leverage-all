#!/bin/sh
set -eu

fixture=/fixture
bin_dir="$fixture/bin"
mkdir -p "$bin_dir" "$fixture/camp-a/projects" "$fixture/camp-b/projects"

cat > "$bin_dir/camp" <<'CAMP'
#!/bin/sh
set -eu

if [ "${1:-}" = "leverage-all" ]; then
    shift
    exec camp-leverage-all "$@"
elif [ "$#" -eq 3 ] && [ "$1" = "list" ] && [ "$2" = "--format" ] && [ "$3" = "json" ]; then
    cat <<'JSON'
[
  {"id": "camp-a", "name": "Camp A", "path": "/fixture/camp-a"},
  {"id": "camp-b", "name": "Camp B", "path": "/fixture/camp-b"}
]
JSON
elif [ "$#" -eq 3 ] && [ "$1" = "project" ] && [ "$2" = "list" ] && [ "$3" = "--json" ]; then
    if [ "${CAMP_ROOT:-}" != "$(pwd -P)" ]; then
        echo "CAMP_ROOT does not match the Camp being scanned" >&2
        exit 64
    fi
    cat <<'JSON'
[
  {
    "Name": "shared-project",
    "Path": "projects/shared",
    "Source": "linked",
    "URL": "https://github.com/example/shared-project.git"
  }
]
JSON
else
    echo "unexpected camp arguments: $*" >&2
    exit 64
fi
CAMP
chmod +x "$bin_dir/camp"

create_checkout() {
    path=$1
    stamp=$2
    mkdir -p "$path"
    git -C "$path" init --quiet --initial-branch main
    cat > "$path/app.py" <<'PY'
def greeting(name: str) -> str:
    words = ["hello", name]
    return " ".join(words)


if __name__ == "__main__":
    print(greeting("world"))
PY
    git -C "$path" add app.py
    GIT_AUTHOR_DATE="$stamp" GIT_COMMITTER_DATE="$stamp" \
        git -C "$path" \
        -c user.name="Example Developer" \
        -c user.email="developer@example.com" \
        commit --quiet -m "Add example"
    git -C "$path" remote add origin https://github.com/example/shared-project.git
}

create_checkout "$fixture/checkout-a" "2026-01-01T00:00:00+00:00"
create_checkout "$fixture/checkout-b" "2026-01-02T00:00:00+00:00"
ln -s "$fixture/checkout-a" "$fixture/camp-a/projects/shared"
ln -s "$fixture/checkout-b" "$fixture/camp-b/projects/shared"

CAMP_ROOT="$fixture/camp-a" PATH="$bin_dir:$PATH" camp leverage-all \
    --author-email developer@example.com \
    --json > "$fixture/report.json"

CAMP_ROOT="$fixture/camp-a" PATH="$bin_dir:$PATH" camp leverage-all \
    --author-email developer@example.com --annual-wage 120000 --overhead 1.5 \
    --json > "$fixture/custom-cost.json"
CAMP_ROOT="$fixture/camp-a" PATH="$bin_dir:$PATH" camp leverage-all \
    --author-email developer@example.com --camp camp-a --json > "$fixture/single-camp.json"
scc --format json2 --cocomo-project-type organic --avg-wage 120000 --overhead 1.5 \
    "$fixture/checkout-b" > "$fixture/scc.json"

python - "$fixture/report.json" <<'PY'
import json
import math
from pathlib import Path
import sys

report = json.loads(Path(sys.argv[1]).read_text())
assert report["complete"] is True, report["errors"]
assert report["camp_count"] == 2
assert report["discovered_repository_count"] == 1
assert report["unique_repository_count"] == 1
assert report["author_emails"] == ["developer@example.com"]
assert report["repositories"][0]["camps"] == ["Camp A", "Camp B"]
assert report["repositories"][0]["commit_count"] == 1
assert report["summary"]["full_leverage"] > 0
assert report["timeline"]["historical_snapshot"] is False
assert report["timeline"]["periods"][-1]["cumulative_leverage"] == report["summary"]["full_leverage"]
summary = report["summary"]
assert summary["estimated_cost_usd"] > 0
assert math.isclose(summary["estimated_cost_usd"], report["repositories"][0]["estimated_cost_usd"])
assert math.isclose(summary["estimated_cost_usd"], sum(
    p["estimated_cost_usd"] for p in report["timeline"]["periods"]
))
assert math.isclose(summary["estimated_cost_usd"],
                    report["timeline"]["periods"][-1]["cumulative_estimated_cost_usd"])
custom = json.loads(Path("/fixture/custom-cost.json").read_text())
single = json.loads(Path("/fixture/single-camp.json").read_text())
scc = json.loads(Path("/fixture/scc.json").read_text())
assert math.isclose(summary["estimated_cost_usd"], single["summary"]["estimated_cost_usd"])
assert math.isclose(custom["summary"]["estimated_cost_usd"], scc["estimatedCost"])
assert custom["summary"]["full_leverage"] == summary["full_leverage"]
assert custom["cost_model"]["annual_wage_usd"] == 120000
assert custom["cost_model"]["overhead_multiplier"] == 1.5
print("integration: cost matches scc, counted once, custom assumptions preserve leverage")
print("integration: duplicate remote scored once across two Camps")
PY
