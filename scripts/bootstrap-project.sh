#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CPP_REFACTORY_DIR="$(dirname "$SCRIPT_DIR")"

# --- 参数校验 ---
if [[ $# -lt 1 ]]; then
    echo "用法: $0 <目标项目路径>"
    echo "示例: $0 /path/to/my-cpp-project"
    exit 1
fi

TARGET_DIR="$1"

if [[ ! -d "$TARGET_DIR" ]]; then
    echo "错误: 目标目录不存在: $TARGET_DIR"
    exit 1
fi

TARGET_DIR="$(cd "$TARGET_DIR" && pwd)"

CREATED=()
SKIPPED=()

# --- 1. 创建 state/ 目录 ---
STATE_DIR="$TARGET_DIR/state"
mkdir -p "$STATE_DIR"

# --- 2. 拷贝状态模板 ---
TEMPLATE_DIR="$CPP_REFACTORY_DIR/state/_template"
for FILE in REFACTOR_STATE.md PARTITION_LEDGER.md TOOL_GAPS.md; do
    DEST="$STATE_DIR/$FILE"
    SRC="$TEMPLATE_DIR/$FILE"
    if [[ -f "$DEST" ]]; then
        echo "跳过: state/$FILE（已存在）"
        SKIPPED+=("state/$FILE")
    elif [[ ! -f "$SRC" ]]; then
        echo "警告: 模板不存在: $SRC"
    else
        cp "$SRC" "$DEST"
        echo "创建: state/$FILE"
        CREATED+=("state/$FILE")
    fi
done

# --- 3. 拷贝配置文件 ---
CONFIGS_DIR="$CPP_REFACTORY_DIR/configs"
declare -A CONFIG_MAP=(
    ["clangd.yaml"]=".clangd"
    ["clang-tidy.yaml"]=".clang-tidy"
    ["clang-format.yaml"]=".clang-format"
    ["gitattributes"]=".gitattributes"
    ["editorconfig"]=".editorconfig"
)

for SRC_NAME in "${!CONFIG_MAP[@]}"; do
    DEST_NAME="${CONFIG_MAP[$SRC_NAME]}"
    DEST="$TARGET_DIR/$DEST_NAME"
    SRC="$CONFIGS_DIR/$SRC_NAME"
    if [[ -f "$DEST" ]]; then
        echo "跳过: $DEST_NAME（已存在）"
        SKIPPED+=("$DEST_NAME")
    elif [[ ! -f "$SRC" ]]; then
        echo "警告: 配置模板不存在: $SRC"
    else
        cp "$SRC" "$DEST"
        echo "创建: $DEST_NAME"
        CREATED+=("$DEST_NAME")
    fi
done

# --- 4. 检查 compile_commands.json ---
echo ""
if [[ -f "$TARGET_DIR/compile_commands.json" ]]; then
    echo "✓ compile_commands.json 已存在"
else
    echo "⚠ compile_commands.json 不存在"
    echo "  建议生成方式："
    echo "    bear -- make"
    echo "    bear -- cmake --build build/"
fi

# --- 5. 尝试运行 cpp-scan.sh ---
CPP_SCAN="$SCRIPT_DIR/cpp-scan.sh"
if [[ -x "$CPP_SCAN" ]]; then
    echo ""
    echo "--- cpp-scan.sh 输出 ---"
    "$CPP_SCAN" "$TARGET_DIR" 2>/dev/null || true
    echo "--- 结束 ---"
fi

# --- 6. 打印摘要 ---
echo ""
echo "========== 初始化摘要 =========="
echo "项目路径: $TARGET_DIR"
echo ""
if [[ ${#CREATED[@]} -gt 0 ]]; then
    echo "已创建 (${#CREATED[@]}):"
    for F in "${CREATED[@]}"; do
        echo "  + $F"
    done
else
    echo "已创建: 无"
fi
echo ""
if [[ ${#SKIPPED[@]} -gt 0 ]]; then
    echo "已跳过 (${#SKIPPED[@]}):"
    for F in "${SKIPPED[@]}"; do
        echo "  - $F（已存在）"
    done
else
    echo "已跳过: 无"
fi
echo ""
echo "下一步建议:"
echo "  1. 确保 compile_commands.json 已生成"
echo "  2. 查看 state/REFACTOR_STATE.md 了解重构状态追踪"
echo "  3. 运行 cpp-scan.sh 扫描项目结构"
echo "================================"
