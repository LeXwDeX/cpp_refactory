# 侦察阶段提示词

Phase 0 侦察阶段的任务清单。

---

## 提示词

```
你正在对 {项目路径} 执行 Phase 0 侦察。

### 任务清单

1. 读取 state/REFACTOR_STATE.md 确认项目基本信息

2. 经验检索：
   mempalace_search(query="C++ 重构 遗留代码 {项目名}")
   mempalace_kg_query(entity="{项目名}")

3. 项目预扫描：
   bash .cpp_refactory/tools/cpp-scan.sh {项目路径}

   记录：CPP_STANDARD、巨型文件 TOP 5、上帝函数 TOP 5、include 热度 TOP 10、#ifdef 丛林指数

4. 确认 compile_commands.json 存在。不存在则：
   bear -- make（或对应的构建命令）

5. 结构探索：
   codegraph_files(path=".")
   codegraph_context(task="项目入口点、核心数据结构、全局状态")

6. 更新 state/REFACTOR_STATE.md：
   - 填写"侦察摘要"
   - 更新"当前 Phase"为 1
   - 追加 Session 日志

7. 存入 mempalace：
   mempalace_kg_add(subject="{项目名}", predicate="cpp_standard", object="{版本}")
   mempalace_kg_add(subject="{项目名}", predicate="top_files", object="{文件列表}")
```
