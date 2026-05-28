# 分区台账 (Partition Ledger)

> 三层结构：**Wave**（战役，跨周/月）→ **Batch**（批次，单会话）→ **Partition**（最小执行单元，≤4小时）
>
> 适用：5万行级 C++ 屎山。普通项目（≤5k 行）可只用单层 Partition。
>
> 每个 Partition 完成后必须更新此文件。状态变化必须立即落盘。

## 状态说明

| 状态 | 含义 | 允许的下一状态 |
|------|------|----------------|
| `PLANNED` | 已规划，未开始 | `IN_PROGRESS`, `BLOCKED` |
| `IN_PROGRESS` | 正在重构中 | `VERIFIED`, `FAILED`, `BLOCKED` |
| `VERIFIED` | 单区验证通过（编译+特征化测试+impact校验） | `DONE`, `FAILED` |
| `DONE` | 集成验证通过，已合入主线 | （终态） |
| `BLOCKED` | 被工具缺口阻塞，已记入 TOOL_GAPS | `PLANNED` |
| `FAILED` | 重构失败（保留以供回溯） | `PLANNED`（重新规划） |
| `ESCALATED` | 连续 3 次失败，需人工介入 | （终态） |

---

## 全局总览

| 指标 | 数值 |
|------|------|
| Active Wave | `{填写或 -}` |
| Total Waves | 0 |
| Total Batches | 0 |
| Total Partitions | 0 |
| DONE / VERIFIED / IN_PROGRESS / BLOCKED / FAILED | 0 / 0 / 0 / 0 / 0 |

---

## Wave 索引

| Wave ID | 目标 | Batches | 状态 | 启动 | 完成 |
|---------|------|---------|------|------|------|
| `{Phase 2 后填写}` | | | | | |

---

## Wave 详情

> 新增 Wave 后，本节会出现 `### W-XXX: ...` 条目。模板示例已抽离到
> `_template/EXAMPLES.md`，避免被 ledger.sh 误识别。

---

## Batch 详情

> 新增 Batch 后，本节会出现 `### B-XXX (W-XXX): ...` 条目。

---

## Partition 详情

> 新增 Partition 后，本节会出现 `### P-XXX (B-XXX / W-XXX): ...` 条目。
> 每条 Partition 必须以 `最后更新：YYYY-MM-DD` 行结尾（ledger.sh 用作锚点）。

---

## 平铺总览（所有 Partition，按 ID 排序）

> 兼容旧版 P-NNN 平铺视图。由 ledger CLI 自动维护。

| ID | Wave | Batch | 文件 | 行范围 | 状态 | 风险 | 最后更新 |
|----|------|-------|------|--------|------|------|----------|
| {auto-filled} | | | | | | | |
