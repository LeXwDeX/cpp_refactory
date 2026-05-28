# 项目侦察约束 — project-recon

对 C++ 项目执行任何代码变更（重构或新功能开发）之前，必须建立项目基线认知。

---

## 硬约束

1. **未侦察不动手** — 对项目执行任何代码修改工具之前，必须先完成侦察。违反即停止当前操作，回到侦察。
2. **C++ 标准是天花板** — `CPP_STANDARD` 由 `cpp-scan.sh` 检测，后续所有代码变更不得使用该标准不支持的特性。
3. **compile_commands.json 是必需品** — 不存在则不执行 AST 分析。用 `bear -- make`（或对应构建命令）生成。
4. **经验先检索** — 侦察开始时查询持久记忆，避免重复踩坑。

---

## 输出契约

侦察完成后产出 `state/REFACTOR_STATE.md`，必须包含以下字段：

| 字段 | 内容 | 不可为空 |
|------|------|----------|
| `cpp_standard` | 检测到的 C++ 标准版本 | ✅ |
| `file_count` | .cpp/.h 文件总数 | ✅ |
| `top5_files` | 行数最大的 5 个文件 | ✅ |
| `top5_functions` | 行数/复杂度最大的 5 个函数 | ✅ |
| `include_hotspot` | 被 include 次数最多的 10 个头文件 | ✅ |
| `ifdef_jungle` | 条件编译嵌套深度 ≥3 的文件数 | ✅ |
| `compile_db` | compile_commands.json 路径 | ✅ |
| `recon_date` | 侦察完成日期 | ✅ |

---

## 记忆写入

侦察完成后写入持久记忆，格式统一：

```
subject = "{项目名}"
predicate = "recon"
object = "{cpp_standard}|{file_count}|{top1_file}|{recon_date}"
```

追加一条原子事实到持久记忆抽屉：
- wing = "cpp-projects"
- room = "{项目名}"
- content = 侦察摘要（一段话，包含标准版本、最大文件、最大函数、主要风险点）

---

## 纠错规则

- **cpp-scan.sh 报错** → 检查脚本路径和权限，不跳过侦察继续。
- **compile_commands.json 生成失败** → 停止，记录工具缺口（GAP），不降级到无 AST 模式。
- **持久记忆查询无结果** → 正常（新项目），继续侦察，不视为错误。

---

## 适用场景

| 场景 | 触发条件 |
|------|----------|
| 遗留代码重构 | 首次接触项目 |
| 新功能开发 | 首次接触项目 |
| 跨 session 恢复 | session 开头读 state/ 发现侦察已完成 → 跳过 |
