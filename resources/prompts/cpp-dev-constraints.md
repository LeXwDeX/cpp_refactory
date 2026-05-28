# C++ 开发决策指南

本文档帮助你在 C++ 项目中做出合理决策。核心原则：**工具能告诉你的，不要自己猜。**

---

## 拿到一个 C++ 项目时

**你想知道的** → **怎么知道**

| 问题 | 自己猜的风险 | 工具给你的答案 |
|------|-------------|---------------|
| 这个项目用什么 C++ 标准？ | CMakeLists 可能撒谎，代码可能混用 | `cpp-scan` 检测实际使用的特性 |
| 哪些文件最大？ | 要 `find + wc` 几十次 | `cpp-scan` 直接给 TOP 20 排行 |
| 哪些函数是上帝函数？ | 要逐文件 awk 大括号计数 | `cpp-scan` 启发式检测 + `cpp-bigfile-map` 精确边界 |
| 条件编译有多复杂？ | 肉眼扫一遍会漏嵌套 | `cpp-scan` 给出每文件 #ifdef 密度 |
| 有哪些全局状态？ | grep 会漏掉匿名命名空间 | `clang_ast_globals`（AST 精确）或 `cpp-seam-finder`（正则降级） |
| 改一个函数会影响谁？ | 要 grep 全项目，还会漏虚函数 | `codegraph impact` 给出完整调用链 |

---

## 修改代码之前

问自己三个问题：

1. **我知道这个函数的精确边界吗？**
   - 大文件（>500 行）→ 先跑 `cpp-bigfile-map`，别直接 Read 全文
   - 有 compile_commands.json → 用 `clang_ast_list_functions` 拿精确行范围和圈复杂度
   - 没有 → `cpp-bigfile-map` 的启发式边界够用

2. **我知道改这个符号会影响多少调用方吗？**
   - 有 .codegraph 索引 → `codegraph impact <symbol>` 直接告诉你
   - 没有 → 至少 grep 一下，但要知道 grep 会漏掉虚函数调用和函数指针

3. **我有测试锁定现有行为吗？**
   - 没有 → 先跑 `cpp-characterize` 生成特征化测试骨架
   - 有了 → 改完跑测试验证行为没变

---

## 版本兼容性

`cpp-scan` 会告诉你项目实际使用的 C++ 标准（`CPP_STANDARD`）。这是天花板。

常见降级：

| 想用 | 最低标准 | 项目不够新时用 |
|------|----------|---------------|
| `auto` | C++11 | 显式类型 |
| `nullptr` | C++11 | `0`（标注风险） |
| `std::unique_ptr` | C++11 | RAII wrapper |
| `std::optional` | C++17 | 哨兵值 + bool |
| `std::string_view` | C++17 | `const std::string&` |
| `if constexpr` | C++17 | SFINAE |
| `std::span` | C++20 | 指针 + 长度 |

---

## 所有权和内存

- 优先 `std::unique_ptr`（C++11+），C++03 用 RAII wrapper
- 不引入 `std::shared_ptr` 除非原代码本身就是引用计数
- 每个 `new` 必须有明确所有者，不允许"谁最后用谁释放"

---

## 宏处理

- `#ifdef` 条件编译路径不删除——你不理解的那个 `#ifdef` 可能是某个平台的救命稻草
- 不确定宏展开结果 → 先用 `clang_ast_macro_jungle` 看复杂度，或用 `clang -E` 看展开
- 带副作用的宏标注 `// MACRO-SIDE-EFFECT:`

---

## 验证变更

改完代码后：

1. `cpp-pipeline` — 编译 + 测试 + 静态分析一条龙
2. `cpp-quality-gate check` — 只看新增的警告/错误，忽略既有的几千个
3. 如果 `cpp-quality-gate baseline` 还没跑过 → 先跑一次记录当前状态

---

## 什么时候停下来

- 同一个文件分析了 3 次还不完整 → 记录工具缺口，问用户
- `codegraph impact` 返回空 → 可能是新符号或索引没更新，跑 `codegraph status` 确认
- MCP 工具报错 `NoCompileEntry` → compile_commands.json 不包含这个文件，需要重新生成
