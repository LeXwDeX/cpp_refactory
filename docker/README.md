# Docker 沙盒 — clang-ast-mcp 完整工具链

容器化的 C++ 遗留代码重构分析沙盒。MCP server 运行在 Docker 容器内，通过 stdio 与宿主的 opencode/AI agent 通信。

## 架构

```
┌─────────────────────────────────────────────────────────────┐
│  宿主 (opencode / AI agent)                                  │
│                                                              │
│  opencode.json:                                              │
│    "clang-ast": {                                           │
│      "command": ["docker", "run", "--rm", "-i",             │
│                  "-v", "/project:/work",                     │
│                  "cpp-refactory"]                            │
│    }                                                        │
└──────────────────┬──────────────────────────────────────────┘
                   │ stdio (JSON-RPC 2.0)
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  Docker 容器 (cpp-refactory)                                 │
│                                                              │
│  entrypoint.sh → clang-ast-mcp (MCP server)                 │
│       │                                                      │
│       ├─ ASTEngine (libclang-18 + LRU cache)                │
│       │                                                      │
│       ├─ analyzers/                                          │
│       │   ├─ list_functions (god function 检测)             │
│       │   ├─ globals_finder (SIOF 风险识别)                 │
│       │   ├─ virtual_calls (多态热点分析)                   │
│       │   └─ macro_jungle (预处理复杂度)                    │
│       │                                                      │
│       └─ refactor_report (聚合报告生成)                     │
│                                                              │
│  /work (只读挂载) ← 宿主 C++ 项目                           │
│  安全隔离：read_only root, no-new-privileges, cap_drop ALL  │
└─────────────────────────────────────────────────────────────┘
```

## 包含组件

| 组件 | 版本来源 | 用途 |
|---|---|---|
| LLVM/Clang 18 | Ubuntu 24.04 官方 apt | C++ 编译/AST 分析 |
| libclang-18-dev | Ubuntu 24.04 官方 apt | Python binding |
| clang-tidy / clang-format | Ubuntu 24.04 官方 apt | 静态检查 / 格式化 |
| cppcheck | Ubuntu 24.04 官方 apt | 互补静态分析 |
| bear | Ubuntu 24.04 官方 apt | 生成 compile_commands.json |
| pipx | Ubuntu 24.04 官方 apt | Python 应用隔离 |
| **clang-ast-mcp** | 本仓库 | MCP server，5 工具 + 重构报告 |

## 快速开始

### 构建镜像

```bash
# 在仓库根目录执行
docker build -t cpp-refactory -f docker/Dockerfile .
```

构建末尾自动运行测试套件（test_local 42 断言 + E2E 重构 31 断言），**任何失败 build 即终止**。

### 运行模式

```bash
# 1. MCP 模式（默认，供 AI agent 通过 stdio 调用）
docker run --rm -i -v /path/to/project:/work cpp-refactory

# 2. 交互调试
docker run --rm -it -v /path/to/project:/work cpp-refactory shell

# 3. 运行测试
docker run --rm cpp-refactory test --all

# 4. 完整沙盒验证
docker run --rm cpp-refactory bash /opt/cpp_refactory/docker/validate-sandbox.sh
```

### Docker Compose（推荐）

```bash
# 设置项目路径
export CPP_PROJECT_PATH=/path/to/your/cpp/repo

# 启动 MCP server
docker compose -f docker/docker-compose.yml run --rm -T mcp-server

# 运行测试
docker compose -f docker/docker-compose.yml run --rm test

# 交互 shell
docker compose -f docker/docker-compose.yml run --rm shell
```

## 与 opencode 集成

在 `~/.config/opencode/opencode.json` 中注册：

```json
{
  "mcp": {
    "clang-ast": {
      "type": "local",
      "command": [
        "docker", "run", "--rm", "-i",
        "-v", "/path/to/your/cpp/repo:/work",
        "cpp-refactory"
      ],
      "enabled": true
    }
  }
}
```

## 安全隔离（docker-compose.yml）

| 措施 | 说明 |
|---|---|
| `read_only: true` | 容器根文件系统只读 |
| `no-new-privileges` | 禁止提权 |
| `cap_drop: ALL` | 移除所有 Linux capabilities |
| `cap_add: DAC_READ_SEARCH` | 仅保留读权限 |
| `networks: internal` | 无外网访问 |
| `memory: 4G` | 内存限制 |
| `cpus: 4.0` | CPU 限制 |
| `/work:ro` | 宿主项目只读挂载 |

## 性能基线

| 文件规模 | cold parse | warm (LRU) | list_functions | virtual_calls | macro_jungle |
|---|---|---|---|---|---|
| 4.5K 行 / 500 funcs | ~190 ms | ~0.12 ms | ~405 ms | ~766 ms | ~789 ms |
| 45K 行 / 5000 funcs | ~440 ms | ~0.17 ms | ~1.9 s | ~1.9 s | ~2.1 s |
| legacy_monster (484 行) | ~170 ms | cached | ~3.2 s (full pipeline) | — | — |

## MCP 工具列表

| 工具 | 描述 |
|---|---|
| `clang_ast_load` | 预热 AST 缓存 |
| `clang_ast_list_functions` | 列出函数 + 圈复杂度 + 行边界 |
| `clang_ast_globals` | 全局变量分析（SIOF 风险） |
| `clang_ast_virtual_calls` | 虚调用站点 + 覆写候选 |
| `clang_ast_macro_jungle` | 预处理复杂度报告 |

## 测试套件

| 测试文件 | 断言数 | 覆盖范围 |
|---|---|---|
| `test_local.py` | 42 | 4 分析器 × 2 fixture + 错误路径 + 缓存 |
| `test_e2e_refactor.py` | 31 | 完整重构报告生成 + 真实屎山检测 |
| `stress_test.py` | 12 | 4543 行 / 500 函数性能基线 |
| `test_mcp_protocol.py` | ~30 | JSON-RPC 协议层验证 |

## 故障排查

- **`libclang.so.1` not found**：`apt list --installed | grep libclang-18-dev`
- **pipx install 失败**：`pipx install --force /opt/cpp_refactory/mcp/clang-ast-mcp`
- **MCP 无响应**：确保 `docker run -i`（必须有 stdin）
- **性能下降**：检查 Docker Desktop 内存限制 ≥ 4G
- **compile_commands.json 缺失**：先在项目内运行 `bear -- make`
