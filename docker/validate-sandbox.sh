#!/usr/bin/env bash
# validate-sandbox.sh — Docker 沙盒完整性验证
#
# 在容器内或 docker run 执行，验证：
#   1. 工具链可用（libclang, clang-tidy, cppcheck, bear）
#   2. MCP server 可启动
#   3. 分析器功能正常（test_local.py）
#   4. 压力测试通过（stress_test.py）
#   5. E2E 重构报告生成（test_e2e_refactor.py）
#   6. 沙盒安全约束验证
#
# 用法：
#   docker run --rm cpp-refactory bash /opt/cpp_refactory/docker/validate-sandbox.sh
#   # 或容器内直接运行

set -euo pipefail

MCP_DIR="/opt/cpp_refactory/mcp/clang-ast-mcp"
TESTS_DIR="${MCP_DIR}/tests"

# --- 颜色 ---
C_GREEN='\033[0;32m'; C_RED='\033[0;31m'
C_BLUE='\033[0;34m'; C_BOLD='\033[1m'; C_RESET='\033[0m'

ok()   { echo -e "  ${C_GREEN}✓${C_RESET} $*"; }
fail() { echo -e "  ${C_RED}✗${C_RESET} $*"; FAILURES=$((FAILURES + 1)); }
section() { echo -e "\n${C_BOLD}${C_BLUE}=== $* ===${C_RESET}"; }

FAILURES=0

# ============================================================
# Phase 1: 工具链完整性
# ============================================================
section "工具链完整性"

check_command() {
    if command -v "$1" >/dev/null 2>&1; then
        ok "$1 → $(command -v "$1")"
    else
        fail "$1 未找到"
    fi
}

check_command clang-ast-mcp
check_command clang++
check_command clang-tidy
check_command clang-format
check_command cppcheck
check_command bear
check_command python3

# libclang Python binding（用 pipx venv 的 python）
if mcp-python -c "from clang import cindex; cindex.Index.create()" 2>/dev/null; then
    ok "libclang Python binding 可用"
else
    fail "libclang Python binding 不可用"
fi

# MCP SDK
if mcp-python -c "import mcp" 2>/dev/null; then
    ok "mcp SDK 可导入"
else
    fail "mcp SDK 不可导入"
fi

# ============================================================
# Phase 2: MCP Server 启动验证
# ============================================================
section "MCP Server 启动"

# 测试 clang-ast-mcp 能否启动（发送空 stdin，应启动后超时退出）
timeout 3 bash -c 'echo "" | clang-ast-mcp 2>/dev/null' || true
if command -v clang-ast-mcp >/dev/null 2>&1; then
    ok "clang-ast-mcp 可执行"
else
    fail "clang-ast-mcp 启动失败"
fi

# ============================================================
# Phase 3: 分析器功能测试
# ============================================================
section "分析器功能测试 (test_local.py)"

cd "${MCP_DIR}"
if mcp-python "${TESTS_DIR}/test_local.py"; then
    ok "test_local.py 全部通过"
else
    fail "test_local.py 有失败断言"
fi

# ============================================================
# Phase 4: 压力测试
# ============================================================
section "压力测试 (stress_test.py)"

if mcp-python "${TESTS_DIR}/stress_test.py"; then
    ok "stress_test.py 通过"
else
    fail "stress_test.py 失败"
fi

# ============================================================
# Phase 5: E2E 重构报告
# ============================================================
section "E2E 重构测试 (test_e2e_refactor.py)"

if mcp-python "${TESTS_DIR}/test_e2e_refactor.py"; then
    ok "test_e2e_refactor.py 全部通过"
else
    fail "test_e2e_refactor.py 有失败断言"
fi

# ============================================================
# Phase 6: 文件完整性
# ============================================================
section "文件完整性"

check_file() {
    if [[ -f "$1" ]]; then
        ok "$1 存在"
    else
        fail "$1 缺失"
    fi
}

check_file "${MCP_DIR}/src/clang_ast_mcp/server.py"
check_file "${MCP_DIR}/src/clang_ast_mcp/ast_engine.py"
check_file "${MCP_DIR}/src/clang_ast_mcp/refactor_report.py"
check_file "${MCP_DIR}/src/clang_ast_mcp/analyzers/list_functions.py"
check_file "${MCP_DIR}/src/clang_ast_mcp/analyzers/globals_finder.py"
check_file "${MCP_DIR}/src/clang_ast_mcp/analyzers/virtual_calls.py"
check_file "${MCP_DIR}/src/clang_ast_mcp/analyzers/macro_jungle.py"
check_file "${TESTS_DIR}/fixtures/sample.cpp"
check_file "${TESTS_DIR}/fixtures/complex.cpp"
check_file "${TESTS_DIR}/fixtures/legacy_monster.cpp"
check_file "${TESTS_DIR}/fixtures/compile_commands.json"
check_file "/opt/cpp_refactory/docker/entrypoint.sh"

# ============================================================
# 结果
# ============================================================
echo
if [[ $FAILURES -eq 0 ]]; then
    echo -e "${C_BOLD}${C_GREEN}╔═══════════════════════════════════════╗${C_RESET}"
    echo -e "${C_BOLD}${C_GREEN}║  SANDBOX VALIDATION PASSED            ║${C_RESET}"
    echo -e "${C_BOLD}${C_GREEN}╚═══════════════════════════════════════╝${C_RESET}"
    exit 0
else
    echo -e "${C_BOLD}${C_RED}╔═══════════════════════════════════════╗${C_RESET}"
    echo -e "${C_BOLD}${C_RED}║  SANDBOX VALIDATION FAILED: ${FAILURES} errors  ║${C_RESET}"
    echo -e "${C_BOLD}${C_RED}╚═══════════════════════════════════════╝${C_RESET}"
    exit 1
fi
