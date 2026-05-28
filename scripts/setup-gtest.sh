#!/usr/bin/env bash
set -euo pipefail

# --- 权限检查 ---
if [[ $EUID -ne 0 ]]; then
    echo "错误: 此脚本需要 root 权限"
    echo "用法: sudo $0"
    exit 1
fi

GTEST_SRC="/usr/src/googletest"
BUILD_DIR="/tmp/gtest_build"

# --- 1. 检查源码是否存在 ---
if [[ ! -d "$GTEST_SRC" ]]; then
    echo "错误: $GTEST_SRC 不存在"
    echo "请先安装: apt install libgtest-dev"
    exit 1
fi

# --- 2. 幂等检查 ---
if [[ -f /usr/local/lib/libgtest.a && -f /usr/local/lib/libgtest_main.a ]]; then
    echo "gtest 静态库已存在，跳过编译"
    ls -la /usr/local/lib/libgtest.a
    ls -la /usr/local/lib/libgtest_main.a
    exit 0
fi

# --- 3. 编译 ---
echo "开始编译 gtest..."
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"
cmake "$GTEST_SRC" -DCMAKE_BUILD_TYPE=Release
make -j"$(nproc)"

# --- 4. 安装到系统路径 ---
echo "安装静态库到 /usr/local/lib/ ..."
cp lib/libgtest*.a /usr/local/lib/
cp lib/libgmock*.a /usr/local/lib/ 2>/dev/null || true

# --- 5. 验证 ---
echo ""
echo "验证安装:"
ls -la /usr/local/lib/libgtest.a
ls -la /usr/local/lib/libgtest_main.a

# --- 6. 清理 ---
rm -rf "$BUILD_DIR"

# --- 7. 完成 ---
echo ""
echo "========== gtest 安装成功 =========="
echo ""
echo "编译命令示例："
echo "  g++ -std=c++14 -I/usr/local/include -o test test.cpp \\"
echo "      -L/usr/local/lib -lgtest -lgtest_main -pthread"
echo ""
echo "===================================="
