#!/bin/zsh
# 把 dist/ 强推到 gh-pages 分支（GitHub Pages 从该分支发布）
set -e
cd "$(dirname "$0")/.."
REMOTE=$(git remote get-url origin)
cd dist
rm -rf .git
git init -q -b gh-pages
git add -A
git commit -qm "deploy $(date '+%F %T')"
git push -qf "$REMOTE" gh-pages
rm -rf .git
