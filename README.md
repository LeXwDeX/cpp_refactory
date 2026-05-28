# opencode-cpp-refactory

OpenCode plugin for AI-assisted C++ legacy code refactoring with MCP-driven safety nets.

## What it does

Turns OpenCode into a C++ legacy code surgery suite:

- **14 custom tools** wrapping battle-tested bash scripts (project scanning, seam discovery, partition ledger, verification)
- **Event hooks** that enforce 5 hard constraints automatically (read state before acting, one partition at a time, verify after changes)
- **Shell env injection** so scripts find their resources regardless of working directory
- **MCP integration** with clang-ast (AST-precise analysis), codegraph (structural queries), and mempalace (persistent memory)

## Install

```bash
npm install opencode-cpp-refactory
```

Add to your `opencode.json`:

```json
{
  "plugin": ["opencode-cpp-refactory"]
}
```

## Quick Start

1. Open a C++ project in OpenCode
2. Call the `cpp-bootstrap` tool to initialize `.cpp_refactory/` workspace
3. Call `cpp-scan` to scan the project
4. Follow the 6-phase workflow: Reconnaissance → Seam Discovery → Partition Planning → Refactoring → Verification → Archive

## Tools

| Tool | Description |
|------|-------------|
| `cpp-scan` | Project pre-scan: C++ standard, file hotspots, god functions, #ifdef jungle index |
| `cpp-seam-finder` | Seam discovery via regex heuristics (fallback path, >30% false positive rate) |
| `cpp-bigfile-map` | Large file navigation map: Section Map + Function Index + Cut Points |
| `cpp-verify-tools` | Verify toolchain completeness (clang-tidy, cppcheck, bear, ccache) |
| `cpp-bootstrap` | Initialize cpp_refactory workspace in target project |
| `cpp-characterize` | Characterization test generation helper |
| `cpp-ast-cache` | AST disk cache management (stats/clean/list) |
| `ledger-init` | Initialize three-layer ledger (Wave/Batch/Partition) |
| `ledger-wave-add` | Create Wave (campaign-level goal) |
| `ledger-batch-add` | Create Batch (single-session goal) |
| `ledger-partition-add` | Create Partition (minimum execution unit, ~4h) |
| `ledger-promote` | Advance partition status (PLANNED→IN_PROGRESS→VERIFIED→DONE) |
| `ledger-status` | View current ledger overview |
| `ledger-list` | List all partition details |

## Hooks

### session.created
Automatically reads `state/` files and injects them into conversation context. Warns if cpp_refactory is not initialized.

### tool.execute.before
Blocks cpp-refactory tools (except `cpp-bootstrap`) if `.cpp_refactory/` doesn't exist. Warns about open tool gaps.

### shell.env
Injects `CPP_REFACTORY_ROOT`, `CPP_REFACTORY_SCRIPTS`, `CPP_REFACTORY_RESOURCES` into all shell sessions.

## MCP Dependencies

This plugin works best with these MCP servers configured:

- **clang-ast-mcp** — AST-precise C++ analysis (function boundaries, cyclomatic complexity, globals, virtual calls)
- **codegraph** — Tree-sitter structural queries (impact analysis, call graph, symbol search)
- **mempalace** — Persistent semantic memory + knowledge graph (cross-session learning)

All three are optional — the plugin degrades gracefully when they're unavailable.

## Architecture

```
OpenCode Runtime
├── Plugin (this package)
│   ├── Custom tools → wrap bash scripts via Bun.$
│   └── Event hooks → enforce constraints automatically
├── MCP: clang-ast-mcp (compiler-grade AST)
├── MCP: codegraph (tree-sitter structural queries)
└── MCP: mempalace (persistent memory)
```

## Development

```bash
npm install
npm test          # 38 tests, node:test + tsx
npm run build     # tsup → dist/index.js
npm run typecheck # tsc --noEmit
```

## License

AGPL-3.0-or-later. See [LICENSE](LICENSE).
