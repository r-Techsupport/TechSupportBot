#!/usr/bin/env bash

set -e

cd -- "$(dirname -- "${BASH_SOURCE[0]}")" || exit 0

mkdir -p resources/dynamic
rm -f resources/dynamic/version.json

origin=$(git remote get-url origin 2>/dev/null) || exit 0
[[ $origin =~ github\.com[:/]([^/]+)/([^/]+)/?$ ]] || exit 0
repository="${BASH_REMATCH[1]}/${BASH_REMATCH[2]%.git}"

branch=$(git branch --show-current 2>/dev/null) || exit 0
branch=${branch:-detached HEAD}
commit=$(git rev-parse HEAD 2>/dev/null) || exit 0
subject=$(git show -s --format=%s HEAD 2>/dev/null) || exit 0
changes=$(git status --porcelain --untracked-files=normal 2>/dev/null) || exit 0

dirty=false
if [[ -n $changes ]]; then
    dirty=true
fi

json_string() {
    local value=$1 character index
    local LC_ALL=C
    printf '"'
    for ((index = 0; index < ${#value}; index++)); do
        character=${value:index:1}
        case "$character" in
            \"|\\) printf '\\%s' "$character" ;;
            [[:cntrl:]]) printf '\\u%04x' "'$character" ;;
            *) printf '%s' "$character" ;;
        esac
    done
    printf '"'
}

{
    printf '{"upstream":'
    json_string "$repository/$branch"
    printf ',"commit":'
    json_string "$commit"
    printf ',"subject":'
    json_string "$subject"
    printf ',"dirty":%s}\n' "$dirty"
} > resources/dynamic/version.json
