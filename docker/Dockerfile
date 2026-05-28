# cpp_refactory — 完整工具链 Docker 沙盒
#
# 多阶段构建：
#   Stage 1: 安装系统依赖 + pipx install clang-ast-mcp
#   Stage 2: 运行全套测试验证（test_local + stress + E2E）
#   Stage 3: 最终镜像（带 entrypoint，支持 MCP stdio / shell 模式）
#
# 按官方文档方式安装：
#   - LLVM/Clang:  Ubuntu 24.04 官方仓库（libclang-18, clang-tidy-18, cppcheck）
#   - bear:        Ubuntu 官方仓库（用于生成 compile_commands.json）
#   - pipx:        Ubuntu 官方仓库（PEP 668 推荐方式）
#   - clang-ast-mcp (本仓库): pipx install（MCP 官方文档推荐 stdio 部署）
#
# 构建：
#   docker build -t cpp-refactory -f docker/Dockerfile .
#
# 验证：
#   docker run --rm cpp-refactory test
#   docker run --rm cpp-refactory bash /opt/cpp_refactory/docker/validate-sandbox.sh
#
# MCP 模式（供 opencode 通过 stdio 调用）：
#   docker run --rm -i -v /path/to/project:/work cpp-refactory
#
# 交互调试：
#   docker run --rm -it -v /path/to/project:/work cpp-refactory shell

FROM ubuntu:24.04 AS base

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    PYTHONIOENCODING=utf-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIPX_HOME=/opt/pipx \
    PIPX_BIN_DIR=/usr/local/bin

# --- 系统依赖（官方 apt 仓库） ---
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        build-essential \
        cmake \
        git \
        rsync \
        ripgrep \
        clang-18 \
        clang-tidy-18 \
        clang-format-18 \
        libclang-18-dev \
        cppcheck \
        bear \
        python3 \
        python3-venv \
        python3-pip \
        pipx \
    && rm -rf /var/lib/apt/lists/*

# --- 把 clang-18 暴露为无版本号别名（官方推荐 update-alternatives） ---
RUN update-alternatives --install /usr/bin/clang        clang        /usr/bin/clang-18        100 \
 && update-alternatives --install /usr/bin/clang++      clang++      /usr/bin/clang++-18      100 \
 && update-alternatives --install /usr/bin/clang-tidy   clang-tidy   /usr/bin/clang-tidy-18   100 \
 && update-alternatives --install /usr/bin/clang-format clang-format /usr/bin/clang-format-18 100

# --- 拷贝整个 cpp_refactory 工具包到镜像 ---
WORKDIR /opt/cpp_refactory
COPY . /opt/cpp_refactory

# --- 设置脚本可执行权限 ---
ARG CACHE_BUST=1
RUN echo "cache_bust=${CACHE_BUST}" > /tmp/cache_bust && chmod +x /opt/cpp_refactory/docker/entrypoint.sh \
 && chmod +x /opt/cpp_refactory/docker/validate-sandbox.sh \
 && find /opt/cpp_refactory/tools -name '*.sh' -exec chmod +x {} \; 2>/dev/null || true

# --- 安装 clang-ast-mcp（pipx，官方 MCP server 部署方式） ---
RUN pipx install /opt/cpp_refactory/mcp/clang-ast-mcp \
 && pipx ensurepath \
 && clang-ast-mcp --help >/dev/null 2>&1 || echo "[i] clang-ast-mcp 安装完成（stdio server，无 --help）"

# --- 暴露 pipx venv 的 python 为 mcp-python（测试和健康检查用） ---
# pipx 把 clang-ast-mcp 安装到 /opt/pipx/venvs/clang-ast-mcp，clang/mcp 等依赖也在该 venv
# 注意：必须用 wrapper 脚本而不是 symlink——Python 通过 argv[0] 实际路径定位 pyvenv.cfg，
# 经 symlink 调用会被解释成系统 python，丢失 venv 的 site-packages
RUN printf '#!/bin/sh\nexec /opt/pipx/venvs/clang-ast-mcp/bin/python3 "$@"\n' > /usr/local/bin/mcp-python \
 && chmod +x /usr/local/bin/mcp-python

# --- 重写 fixtures 中的 compile_commands.json directory 字段 ---
# fixtures 原本硬编码 /root/cpp_refactory/...，但镜像内项目位于 /opt/cpp_refactory/...
# 用 sed 替换为容器内实际路径，避免 ast_engine 路径匹配失败
RUN sed -i 's|/root/cpp_refactory|/opt/cpp_refactory|g' \
        /opt/cpp_refactory/mcp/clang-ast-mcp/tests/fixtures/compile_commands.json

# --- 镜像内自检：跑测试套件（任何失败立即终止 build） ---
# Phase 1: 原有本地测试（42 断言 + 压力测试）
RUN mcp-python /opt/cpp_refactory/mcp/clang-ast-mcp/tests/test_local.py

# Phase 2: E2E 重构报告测试
RUN mcp-python /opt/cpp_refactory/mcp/clang-ast-mcp/tests/test_e2e_refactor.py

# --- 创建工作目录（挂载点） ---
RUN mkdir -p /work

# --- 健康检查 ---
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=5s \
    CMD mcp-python -c "from clang import cindex; cindex.Index.create()" || exit 1

# --- 入口点 ---
ENTRYPOINT ["/opt/cpp_refactory/docker/entrypoint.sh"]
CMD ["mcp"]

# --- 元数据 ---
LABEL org.opencontainers.image.title="cpp-refactory" \
      org.opencontainers.image.description="C++ legacy code refactoring sandbox with MCP AST analysis" \
      org.opencontainers.image.version="0.2.0"
