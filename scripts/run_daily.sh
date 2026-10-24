#!/bin/zsh
# launchd 每天调用：写文章 + 配图 + 构建 + 推送
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
cd "$(dirname "$0")/.." || exit 1
git pull -q --rebase 2>/dev/null
uv run --with pillow --with pyyaml scripts/daily.py "$@" >> logs/launchd.log 2>&1
