#!/usr/bin/env bash
# tool-gap-report.sh — 从 state/TOOL_GAPS.md 生成工具缺口摘要报告
# 用途：快速查看当前工具缺口状态
# 依赖：rg (可选，降级为 grep)
#
# 用法：bash tool-gap-report.sh <目标项目路径>

set -euo pipefail

# CRLF 自愈
if file "$0" | grep -q CRLF 2>/dev/null; then
    tr -d '\r' < "$0" > "$0.tmp" && mv "$0.tmp" "$0" && chmod +x "$0"
    exec bash "$0" "$@"
fi

TARGET="${1:-.}"
GAPS_FILE="$TARGET/state/TOOL_GAPS.md"

if [[ ! -f "$GAPS_FILE" ]]; then
    echo "错误：$GAPS_FILE 不存在" >&2
    echo "请先运行 bootstrap-project.sh 初始化项目" >&2
    exit 1
fi

# 用 rg 或 grep
SEARCH="grep"
command -v rg &>/dev/null && SEARCH="rg"

echo "╔══════════════════════════════════════════════════════════╗"
echo "║         工具缺口状态报告                                 ║"
echo "║         项目：$(basename "$TARGET")"
echo "║         时间：$(date '+%Y-%m-%d %H:%M:%S')"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# 统计各状态数量
OPEN=$($SEARCH -c '^\- \*\*状态\*\*：OPEN' "$GAPS_FILE" 2>/dev/null || echo "0")
IN_PROG=$($SEARCH -c '^\- \*\*状态\*\*：IN_PROGRESS' "$GAPS_FILE" 2>/dev/null || echo "0")
CLOSED=$($SEARCH -c '^\- \*\*状态\*\*：CLOSED' "$GAPS_FILE" 2>/dev/null || echo "0")
ESCALATED=$($SEARCH -c '^\- \*\*状态\*\*：ESCALATED' "$GAPS_FILE" 2>/dev/null || echo "0")
TOTAL=$((OPEN + IN_PROG + CLOSED + ESCALATED))

echo "  总览："
echo "  ├── 总缺口数：$TOTAL"
echo "  ├── OPEN：$OPEN"
echo "  ├── IN_PROGRESS：$IN_PROG"
echo "  ├── CLOSED：$CLOSED"
echo "  └── ESCALATED：$ESCALATED"
echo ""

# 列出 OPEN 缺口
if [[ "$OPEN" -gt 0 || "$IN_PROG" -gt 0 ]]; then
    echo "  ── 活跃缺口 ──"
    echo ""
    $SEARCH -A 5 '### GAP-' "$GAPS_FILE" 2>/dev/null | \
        $SEARCH -B 1 'OPEN\|IN_PROGRESS' 2>/dev/null || true
    echo ""
fi

# 列出 ESCALATED 缺口
if [[ "$ESCALATED" -gt 0 ]]; then
    echo "  ── 已升级（需人工决策） ──"
    echo ""
    $SEARCH -A 5 '### GAP-' "$GAPS_FILE" 2>/dev/null | \
        $SEARCH -B 1 'ESCALATED' 2>/dev/null || true
    echo ""
fi

# 建议
echo "  ── 建议 ──"
if [[ "$OPEN" -gt 0 || "$IN_PROG" -gt 0 ]]; then
    echo "  有 $((OPEN + IN_PROG)) 个活跃缺口，建议优先处理后再继续重构"
else
    echo "  无活跃缺口，可以继续重构"
fi

if [[ "$ESCALATED" -gt 0 ]]; then
    echo "  有 $ESCALATED 个已升级缺口，需要人工决策"
fi
