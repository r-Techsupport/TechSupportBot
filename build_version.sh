#!/usr/bin/env bash

repository=$(git remote get-url origin | sed 's|.*github.com[:/]||; s|\.git$||')
branch=$(git branch --show-current)
commit=$(git rev-parse HEAD)
subject=$(git log -1 --format=%s)

dirty=false
if [[ -n $(git status --porcelain) ]]; then
    dirty=true
fi

mkdir -p resources/dynamic
subject=${subject//\\/\\\\}
subject=${subject//\"/\\\"}
cat > resources/dynamic/version.json <<EOF
{
    "upstream": "$repository/$branch",
    "commit": "$commit",
    "subject": "$subject",
    "dirty": $dirty
}
EOF
