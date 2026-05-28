#!/usr/bin/env bash
# fix-crlf.sh — 递归修复目录下所有 shell 脚本的 CRLF 行尾
# 用途：解决 Windows 产出的 .sh 文件在 Linux 上报 $'\r': command not found
# 依赖：file, tr, find
#
# 用法：bash fix-crlf.sh <目标目录>
# 默认只处理 *.sh 文件。加 --all 处理所有文本文件。

set -euo pipefail

TARGET="${1:-.}"
ALL_TEXT=false
[[ "${2:-}" == "--all" ]] && ALL_TEXT=true

if [[ ! -d "$TARGET" ]]; then
    echo "错误：目标目录 '$TARGET' 不存在" >&2
    exit 1
fi

FIXED=0
SKIPPED=0
ERRORS=0

fix_file() {
    local f="$1"
    if file "$f" | grep -q CRLF; then
        if tr -d '\r' < "$f" > "${f}.tmp" && mv "${f}.tmp" "$f"; then
            echo "  FIXED: $f"
            ((FIXED++))
        else
            echo "  ERROR: $f" >&2
            rm -f "${f}.tmp"
            ((ERRORS++))
        fi
    else
        ((SKIPPED++))
    fi
}

echo "═══════════════════════════════════════════"
echo "  CRLF 修复工具"
echo "  目标：$TARGET"
echo "  模式：$( [[ "$ALL_TEXT" == "true" ]] && echo "所有文本文件" || echo "仅 *.sh 文件" )"
echo "═══════════════════════════════════════════"
echo ""

if [[ "$ALL_TEXT" == "true" ]]; then
    while IFS= read -r -d '' f; do
        if file "$f" | grep -q "text"; then
            fix_file "$f"
        fi
    done < <(find "$TARGET" -type f -not -path "*/.git/*" -print0)
else
    while IFS= read -r -d '' f; do
        fix_file "$f"
    done < <(find "$TARGET" -type f -name "*.sh" -not -path "*/.git/*" -print0)
fi

echo ""
echo "═══════════════════════════════════════════"
echo "  结果：修复 $FIXED 个，跳过 $SKIPPED 个，错误 $ERRORS 个"
echo "═══════════════════════════════════════════"

exit "$ERRORS"
