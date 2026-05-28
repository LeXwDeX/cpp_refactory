# 接缝发现提示词

Phase 1 接缝发现阶段的任务清单。

---

## 提示词

```
你正在对 {目标文件} 执行 Phase 1 接缝发现。

### 背景

- C++ 标准：{CPP_STANDARD}
- 文件行数：{N} 行
- 架构角色：{来自侦察报告的描述}

### 任务清单

1. AST 精确扫描（主路径）：
   clang_ast_load(file="{目标文件}")
   clang_ast_list_functions(file="{目标文件}", min_lines=50)
   clang_ast_globals(file="{目标文件}")
   clang_ast_virtual_calls(file="{目标文件}")
   clang_ast_macro_jungle(file="{目标文件}")

2. 结构上下文：
   codegraph_context(task="{高复杂度符号} 的调用者、被调者")
   codegraph_impact(symbol="{高复杂度符号}")

3. 降级路径（MCP 不可用时）：
   bash .cpp_refactory/tools/cpp-seam-finder.sh {目标文件}

4. 构建决策表：

   | 函数名 | 行数 | 圈复杂度 | 全局依赖 | 虚调用 | 宏复杂度 | 切分优先级 |
   |--------|------|----------|----------|--------|----------|-----------|

5. 使用 templates/seam-analysis.md 模板整理接缝报告

6. 更新 state/REFACTOR_STATE.md "关键接缝"部分

7. 存入 mempalace：
   mempalace_add_drawer(wing="architecture", room="{项目名}", content="{接缝分析结果}")
   mempalace_kg_add(subject="{高风险符号}", predicate="risk_level", object="HIGH")

### 工具不足信号

- 误报率超过 30%：记录 GAP（类型 E）
- 漏掉明显接缝：记录 GAP（类型 B）
- 无法分析特定模式：记录 GAP（类型 A）

按 AGENTS.md 约束 2 处理。
```
