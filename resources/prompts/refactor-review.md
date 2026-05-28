# 重构审查提示词

Phase 3 逐区重构完成后的审查清单。标记 VERIFIED 之前必须走完。

---

## 提示词

```
你刚完成了分区 P-{NNN} 的重构。在标记 VERIFIED 之前，走完以下审查。

### 基本信息

- 分区：P-{NNN} — {名称}
- 文件：{文件路径}
- C++ 标准：{CPP_STANDARD}
- 重构手法：{Extract Method / Replace Temp / ...}

### 审查清单

#### 功能正确性
- [ ] 编译通过，无新增错误
- [ ] 编译通过，无新增警告
- [ ] 所有现有测试通过
- [ ] 特征化测试通过（行为未改变）

#### C++ 专项约束
- [ ] 未引入 CPP_STANDARD 不支持的特性
- [ ] 未引入 std::shared_ptr（除非原代码是引用计数的）
- [ ] 未增加不必要的虚函数调用
- [ ] 未增加不必要的堆分配
- [ ] 保留了所有 #ifdef 条件编译路径
- [ ] 所有 const_cast / reinterpret_cast 已标注理由

#### 安全性
- [ ] 无新增迭代器失效风险
- [ ] 无新增悬空引用
- [ ] 无新增 use-after-free
- [ ] 所有动态分配有明确所有者

#### 驾车重构检查
- [ ] 无超出任务要求的代码改动
- [ ] 每行变更可追溯到分区规划
- [ ] 未引入未被要求的抽象层
- [ ] 匹配所在文件的现有代码风格
- [ ] 只清理了因本次改动产生的孤儿代码

#### 接缝影响
- [ ] Phase 1 发现的全局变量依赖关系未被破坏
- [ ] 相邻分区的接缝未被无意修改
- [ ] 修改了接口 → 所有调用方已同步更新

### 静态分析验证

clang-tidy -p . {修改过的文件}
cppcheck --enable=all --suppress=missingIncludeSystem {修改过的文件}

### MCP 验证

clang_ast_list_functions(file="新提取的文件.cpp")
codegraph_impact(symbol="{修改过的符号}")

### 判定

- 全部通过 → 更新 PARTITION_LEDGER.md 为 VERIFIED
- 有不通过项 → 列出问题，修复后重新审查
- 发现工具不足 → 登记 GAP，按 tool-gap-response.md 处理

### 存入 mempalace

mempalace_kg_add(subject="{函数A}", predicate="extracted_to", object="{文件B}", valid_from="{日期}")
mempalace_add_drawer(wing="patterns", room="cpp-refactor", content="{本次重构的可复用经验}")
```
