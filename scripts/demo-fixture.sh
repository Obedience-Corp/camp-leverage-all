#!/usr/bin/env bash
set -euo pipefail

fixture="$(mktemp -d "${TMPDIR:-/tmp}/campaign-leverage-demo.XXXXXX")"
fixture="$(cd "$fixture" && pwd -P)"
mkdir -p \
    "$fixture/bin" \
    "$fixture/home" \
    "$fixture/campaign-studio/projects" \
    "$fixture/campaign-client/projects"

git_config="$fixture/home/.gitconfig"
cat > "$git_config" <<'GITCONFIG'
[user]
    name = Example Developer
    email = developer@example.com
GITCONFIG

write_module() {
    destination=$1
    prefix=$2
    functions=$3
    python3 - "$destination" "$prefix" "$functions" <<'PY'
from pathlib import Path
import sys

destination, prefix, count = sys.argv[1], sys.argv[2], int(sys.argv[3])
lines = [
    '"""Deterministic source used by the Campaign Leverage terminal demo."""',
    "",
]
for index in range(1, count + 1):
    lines.extend((
        f"def {prefix}_{index:04d}(value: int) -> int:",
        f"    return value + {index}",
        "",
    ))
Path(destination).write_text("\n".join(lines))
PY
}

new_repo() {
    path=$1
    remote=$2
    mkdir -p "$path"
    git -C "$path" init --quiet --initial-branch main
    git -C "$path" remote add origin "$remote"
}

commit_module() {
    repo=$1
    file=$2
    prefix=$3
    functions=$4
    name=$5
    email=$6
    stamp=$7
    write_module "$repo/$file" "$prefix" "$functions"
    git -C "$repo" add "$file"
    GIT_AUTHOR_DATE="$stamp" GIT_COMMITTER_DATE="$stamp" \
        git -C "$repo" \
        -c "user.name=$name" \
        -c "user.email=$email" \
        commit --quiet -m "Add $file"
}

shared_a="$fixture/shared-platform-a"
shared_b="$fixture/shared-platform-b"
toolkit="$fixture/automation-toolkit"
portal="$fixture/client-portal"

new_repo "$shared_a" "https://github.com/example/shared-platform.git"
commit_module "$shared_a" core.py core 900 \
    "Example Developer" developer@example.com "2026-01-05T09:00:00+00:00"
commit_module "$shared_a" core.py core 820 \
    "Example Developer" developer@example.com "2026-01-20T09:00:00+00:00"
commit_module "$shared_a" agents.py agent 420 \
    "Demo Agent" automation@example.com "2026-02-10T09:00:00+00:00"
commit_module "$shared_a" community.py community 240 \
    "Community Contributor" contributor@example.com "2026-02-15T09:00:00+00:00"
git clone --quiet "$shared_a" "$shared_b"
git -C "$shared_b" remote set-url origin "https://github.com/example/shared-platform.git"

new_repo "$toolkit" "https://github.com/example/automation-toolkit.git"
commit_module "$toolkit" toolkit.py toolkit 720 \
    "Demo Agent" automation@example.com "2026-01-25T09:00:00+00:00"

new_repo "$portal" "https://github.com/example/client-portal.git"
commit_module "$portal" portal.py portal 780 \
    "Example Developer" developer@example.com "2026-02-10T09:00:00+00:00"
commit_module "$portal" integrations.py integration 360 \
    "Community Contributor" contributor@example.com "2026-02-15T09:00:00+00:00"

ln -s "$shared_a" "$fixture/campaign-studio/projects/shared-platform"
ln -s "$toolkit" "$fixture/campaign-studio/projects/automation-toolkit"
ln -s "$shared_b" "$fixture/campaign-client/projects/shared-platform"
ln -s "$portal" "$fixture/campaign-client/projects/client-portal"

for campaign in campaign-studio campaign-client; do
    mkdir -p "$fixture/$campaign/.campaign/leverage"
    cat > "$fixture/$campaign/.campaign/leverage/authors.json" <<'JSON'
{
  "authors": {
    "example-developer": {
      "name": "Example Developer",
      "emails": ["developer@example.com"]
    },
    "demo-agent": {
      "name": "Demo Agent",
      "emails": ["automation@example.com"]
    }
  }
}
JSON
done

cat > "$fixture/bin/camp" <<'CAMP'
#!/usr/bin/env bash
set -euo pipefail

fixture="${CAMPAIGN_LEVERAGE_DEMO_ROOT:?}"
if [[ "$*" == "list --format json" ]]; then
    cat <<JSON
[
  {"id": "studio", "name": "Studio", "path": "$fixture/campaign-studio"},
  {"id": "client", "name": "Client Work", "path": "$fixture/campaign-client"}
]
JSON
elif [[ "$*" == "project list --json" ]]; then
    current_dir="$(pwd -P)"
    case "$current_dir" in
        "$fixture/campaign-studio")
            cat <<JSON
[
  {
    "Name": "shared-platform",
    "Path": "projects/shared-platform",
    "Source": "linked",
    "URL": "https://github.com/example/shared-platform.git"
  },
  {
    "Name": "automation-toolkit",
    "Path": "projects/automation-toolkit",
    "Source": "linked",
    "URL": "https://github.com/example/automation-toolkit.git"
  }
]
JSON
            ;;
        "$fixture/campaign-client")
            cat <<JSON
[
  {
    "Name": "shared-platform",
    "Path": "projects/shared-platform",
    "Source": "linked",
    "URL": "https://github.com/example/shared-platform.git"
  },
  {
    "Name": "client-portal",
    "Path": "projects/client-portal",
    "Source": "linked",
    "URL": "https://github.com/example/client-portal.git"
  }
]
JSON
            ;;
        *)
            echo "unexpected campaign directory" >&2
            exit 64
            ;;
    esac
else
    echo "unexpected camp arguments: $*" >&2
    exit 64
fi
CAMP
chmod +x "$fixture/bin/camp"

printf 'export CAMPAIGN_LEVERAGE_DEMO_ROOT=%q\n' "$fixture"
printf 'export HOME=%q\n' "$fixture/home"
printf 'export PATH=%q:$PATH\n' "$fixture/bin"
printf 'export GIT_CONFIG_NOSYSTEM=1\n'
