#!/usr/bin/env bash
# entrypoint.sh — Docker 容器入口点
#
# 两种运行模式：
#   1. MCP stdio 模式（默认）：容器启动后直接接管 stdin/stdout 作为 MCP server
#      用法：docker run --rm -i -v /project:/work cpp-refactory
#
#   2. 交互 shell 模式：传入 "shell" 或 "bash" 参数
#      用法：docker run --rm -it -v /project:/work cpp-refactory shell
#
#   3. 任意命令模式：传入其他命令
#      用法：docker run --rm cpp-refactory python3 tests/test_local.py
#
# 环境变量：
#   CLANG_AST_MCP_COMPILE_DB — compile_commands.json 路径（默认自动搜索）
#   CLANG_AST_MCP_LOG        — 日志级别 (DEBUG/INFO/WARNING)
#   MCP_WORK_DIR             — 挂载的项目目录（默认 /work）

set -euo pipefail

MCP_WORK_DIR="${MCP_WORK_DIR:-/work}"
CLANG_AST_MCP_LOG="${CLANG_AST_MCP_LOG:-INFO}"
export CLANG_AST_MCP_LOG

# --- 健康检查辅助 ---
_health_check() {
    # 验证 libclang 可用（用 pipx venv 的 python，clang.cindex 在那里）
    mcp-python -c "from clang import cindex; cindex.Index.create()" 2>/dev/null || {
        echo "[FATAL] libclang Python binding 不可用" >&2
        exit 1
    }
    # 验证 clang-ast-mcp 可执行
    command -v clang-ast-mcp >/dev/null 2>&1 || {
        echo "[FATAL] clang-ast-mcp 未安装" >&2
        exit 1
    }
    echo "[OK] Health check passed" >&2
}

# --- 自动检测 compile_commands.json ---
_find_compile_db() {
    if [[ -n "${CLANG_AST_MCP_COMPILE_DB:-}" ]]; then
        return 0
    fi
    if [[ -f "${MCP_WORK_DIR}/compile_commands.json" ]]; then
        export CLANG_AST_MCP_COMPILE_DB="${MCP_WORK_DIR}/compile_commands.json"
        echo "[i] Auto-detected compile_commands.json at ${MCP_WORK_DIR}" >&2
    elif [[ -f "${MCP_WORK_DIR}/build/compile_commands.json" ]]; then
        export CLANG_AST_MCP_COMPILE_DB="${MCP_WORK_DIR}/build/compile_commands.json"
        echo "[i] Auto-detected compile_commands.json at ${MCP_WORK_DIR}/build" >&2
    fi
}

# --- 主逻辑 ---
case "${1:-mcp}" in
    mcp|"")
        # MCP stdio 模式：进程的 stdin/stdout 就是 JSON-RPC 通道
        _health_check
        _find_compile_db
        if [[ -d "${MCP_WORK_DIR}" ]]; then
            cd "${MCP_WORK_DIR}"
        fi
        echo "[i] Starting clang-ast-mcp (stdio transport)" >&2
        echo "[i] Work dir: $(pwd)" >&2
        echo "[i] Compile DB: ${CLANG_AST_MCP_COMPILE_DB:-auto-search}" >&2
        exec clang-ast-mcp
        ;;
    shell|sh)
        # 交互 shell 模式
        _health_check
        _find_compile_db
        if [[ -d "${MCP_WORK_DIR}" ]]; then
            cd "${MCP_WORK_DIR}"
        fi
        echo "[i] Interactive shell mode. Work dir: $(pwd)" >&2
        echo "[i] Available tools: clang-ast-mcp, clang-tidy, clang-format, cppcheck, bear" >&2
        exec /bin/bash
        ;;
    bash)
        # bash + 参数 → 透传执行（用于跑 validate-sandbox.sh 等脚本）
        # 无参数时进入交互 shell
        shift
        if [[ $# -eq 0 ]]; then
            exec /bin/bash
        else
            exec /bin/bash "$@"
        fi
        ;;
    health|healthcheck)
        # 健康检查（供 docker-compose healthcheck 调用）
        _health_check
        ;;
    test)
        # 运行测试套件（用 pipx venv 的 python，清理 pyc 避免 read-only fs 问题）
        shift
        echo "[i] Running test suite..." >&2
        cd /opt/cpp_refactory/mcp/clang-ast-mcp
        export PYTHONDONTWRITEBYTECODE=1
        mcp-python tests/test_local.py
        if [[ "${1:-}" == "--stress" ]]; then
            mcp-python tests/stress_test.py
        fi
        if [[ "${1:-}" == "--all" || "${1:-}" == "--e2e" ]]; then
            mcp-python tests/test_mcp_protocol.py
            mcp-python tests/test_e2e_refactor.py
        fi
        ;;
    *)
        # 任意命令透传
        exec "$@"
        ;;
esac
