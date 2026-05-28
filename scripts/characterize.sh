#!/usr/bin/env bash
# characterize.sh — 特征化测试生成辅助
# 用途：为指定的 C++ 源文件生成特征化测试的骨架代码
# 依赖：rg (ripgrep), awk
#
# 用法：bash characterize.sh <源文件> [--output <输出文件>]
#
# 注意：此脚本生成的是骨架代码，需要人工补充断言

set -euo pipefail

# CRLF 自愈
if file "$0" | grep -q CRLF 2>/dev/null; then
    tr -d '\r' < "$0" > "$0.tmp" && mv "$0.tmp" "$0" && chmod +x "$0"
    exec bash "$0" "$@"
fi

SOURCE_FILE="${1:-}"
OUTPUT_FILE=""

if [[ -z "$SOURCE_FILE" ]]; then
    echo "用法：bash characterize.sh <源文件> [--output <输出文件>]" >&2
    exit 1
fi

if [[ ! -f "$SOURCE_FILE" ]]; then
    echo "错误：源文件 '$SOURCE_FILE' 不存在" >&2
    exit 1
fi

# 解析 --output 参数
shift
while [[ $# -gt 0 ]]; do
    case "$1" in
        --output) OUTPUT_FILE="$2"; shift 2 ;;
        *) echo "未知参数：$1" >&2; exit 1 ;;
    esac
done

BASENAME="$(basename "$SOURCE_FILE" | sed 's/\.[^.]*$//')"
if [[ -z "$OUTPUT_FILE" ]]; then
    OUTPUT_FILE="test_characterize_${BASENAME}.cpp"
fi

# 提取函数签名（启发式）
extract_functions() {
    # 匹配 "返回类型 函数名(参数列表)" 模式
    rg -n '^[a-zA-Z_][\w:<>*& ]+\s+([a-zA-Z_]\w*)\s*\([^)]*\)\s*\{?\s*$' "$SOURCE_FILE" 2>/dev/null | \
        grep -v '^\s*(if|else|for|while|switch|case|return|class|struct|enum|namespace|template|typedef|using)\b' | \
        head -30 || true
}

# 提取类名
extract_classes() {
    rg -n '^\s*(class|struct)\s+(\w+)' "$SOURCE_FILE" 2>/dev/null | head -20 || true
}

# 提取 include 的头文件
extract_includes() {
    rg -o '#include\s*[<"]([^>"]+)[>"]' --replace '$1' "$SOURCE_FILE" 2>/dev/null | sort -u || true
}

echo "═══════════════════════════════════════════"
echo "  特征化测试骨架生成"
echo "  源文件：$SOURCE_FILE"
echo "  输出到：$OUTPUT_FILE"
echo "═══════════════════════════════════════════"
echo ""

# 生成测试骨架
cat > "$OUTPUT_FILE" << TESTEOF
// 特征化测试 — ${BASENAME}
// 自动生成骨架，需要人工补充断言
// 编译：g++ -std=c++14 -I/usr/local/include -o ${OUTPUT_FILE%.cpp} ${OUTPUT_FILE} ${SOURCE_FILE} -L/usr/local/lib -lgtest -lgtest_main -pthread
//
// 注意：特征化测试记录"实际行为"，不是"期望行为"
//       测试失败 = 重构改变了语义

#include <gtest/gtest.h>

// === 被测头文件 ===
// TODO: 替换为正确的头文件路径
TESTEOF

# 添加 includes
while IFS= read -r inc; do
    if [[ -n "$inc" && "$inc" != *.cpp && "$inc" != *.cxx && "$inc" != *.cc ]]; then
        echo "#include \"$inc\"" >> "$OUTPUT_FILE"
    fi
done < <(extract_includes)

cat >> "$OUTPUT_FILE" << 'TESTEOF'

// === Fixture（保存/恢复全局状态） ===
class CharacterizeFixture : public ::testing::Test {
protected:
    void SetUp() override {
        // TODO: 保存被测代码依赖的全局变量
    }
    void TearDown() override {
        // TODO: 恢复全局变量
    }
};

TESTEOF

# 为每个函数生成测试桩
echo "  发现的函数签名："
while IFS= read -r line; do
    if [[ -z "$line" ]]; then continue; fi

    LINE_NUM=$(echo "$line" | cut -d: -f1)
    FUNC_SIG=$(echo "$line" | cut -d: -f2- | sed 's/[[:space:]]*{.*//')
    FUNC_NAME=$(echo "$FUNC_SIG" | rg -o '\b([a-zA-Z_]\w*)\s*\(' --replace '$1' 2>/dev/null | head -1 || echo "unknown")

    echo "  L${LINE_NUM}: ${FUNC_NAME}"

    cat >> "$OUTPUT_FILE" << FUNCEOF

// 特征化测试：${FUNC_NAME}（L${LINE_NUM}）
// 原始签名：${FUNC_SIG}
TEST_F(CharacterizeFixture, ${FUNC_NAME}_BasicBehavior) {
    // Arrange: 设置前置条件
    // TODO

    // Act: 调用被测函数
    // auto result = ${FUNC_NAME}(/* 参数 */);

    // Assert: 记录当前实际输出
    // EXPECT_EQ(result, /* 实际值 */);
    GTEST_SKIP() << "需要人工补充断言";
}

FUNCEOF
done < <(extract_functions)

echo ""
echo "  生成完成：$OUTPUT_FILE"
echo ""
echo "  下一步："
echo "  1. 编辑 $OUTPUT_FILE，替换 TODO 为实际代码"
echo "  2. 补充断言（运行被测函数，记录实际输出作为 EXPECT_EQ 的期望值）"
echo "  3. 编译运行确认所有测试通过"
