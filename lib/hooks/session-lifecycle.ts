import { readStateFiles, stateExists, type StateFiles } from "../utils/state.js"

export type SessionStatus = "notInstalled" | "ready"

export interface SessionContext {
    projectDir: string
    status: SessionStatus
    stateFiles: StateFiles
}

/**
 * Build session context by reading state files from the project directory.
 * Called on session.created to inject context into the conversation.
 */
export function buildSessionContext(projectDir: string): SessionContext {
    if (!stateExists(projectDir)) {
        return {
            projectDir,
            status: "notInstalled",
            stateFiles: {
                refactorState: null,
                partitionLedger: null,
                toolGaps: null,
            },
        }
    }

    return {
        projectDir,
        status: "ready",
        stateFiles: readStateFiles(projectDir),
    }
}

// ── Methodology injection ───────────────────────────────────────────
// This is the core reasoning framework. Not rules — a way of thinking.
// Injected into every session so the AI internalizes multi-source
// triangulation as its default approach to understanding C++ code.

const METHODOLOGY = `
[cpp-refactory] 多源交叉验证方法论（Multi-source Triangulation）

你对 C++ 代码的每一个判断都应该由多个信息源支撑。单一来源会骗你。

信息源及其盲区：
- grep/Bash 搜索 → 看到的是文本模式，不懂语义（模板特化、宏展开、虚函数分发、命名空间别名都会漏掉或误报）
- Read 原始代码 → 大文件（>500行）会超出注意力窗口，丢失结构感
- AST 工具（clang_ast_*） → 精确的语义理解，但依赖 compile_commands.json
- codegraph（callers/callees/impact/context） → 符号级关系图谱，看到跨文件的调用链和影响范围
- cpp-scan / cpp-seam-finder / cpp-bigfile-map → 项目级和文件级的结构化概览
- clang-tidy / cppcheck → 质量信号，但既有告警可能成百上千，需要增量对比

推理模式：
1. 先明确"我想知道什么"（函数边界？影响范围？全局依赖？风险等级？）
2. 找到能回答这个问题的 2-3 个工具，组合使用
3. 交叉比对结果 — 一致则可信度高，不一致则需要第三个来源仲裁

典型组合：
- 找函数边界 → codegraph callees + clang_ast_list_functions（AST 精确行号）+ cpp-bigfile-map（段落上下文）
- 评估爆炸半径 → codegraph impact（跨文件影响）+ clang_ast_virtual_calls（虚函数分发）+ cpp-seam-finder（接缝分类）
- 理解大文件 → cpp-bigfile-map（结构地图，先看全貌）→ 只 Read 需要的段落 → codegraph callers（这个函数被谁调用）
- 确认全局状态 → clang_ast_globals（AST 精确分类）+ cpp-seam-finder（启发式补充）+ codegraph context（上下游依赖）
- 验证变更安全 → cpp-pipeline（编译+测试+静态分析）+ cpp-quality-gate check（只看新增问题）

关键原则：
- 不要用一个 grep 就下结论 — 它可能漏掉 80% 的真实情况
- 不要 Read 整个大文件 — 用地图导航到需要的段落
- 不确定时，问另一个工具来验证
- 工具之间结论矛盾时，优先信任 AST > codegraph > 正则 > grep
`

/**
 * Format session context for injection into conversation.
 */
export function formatSessionContext(ctx: SessionContext): string {
    const parts: string[] = [METHODOLOGY.trim()]

    if (ctx.status === "notInstalled") {
        parts.push(`\n[cpp-refactory] cpp_refactory not installed in this project. Call cpp-bootstrap tool to initialize.`)
        return parts.join("\n")
    }

    parts.push(`\n[cpp-refactory] Session context loaded.`)

    if (ctx.stateFiles.refactorState) {
        parts.push(`\n## REFACTOR_STATE\n${ctx.stateFiles.refactorState}`)
    }
    if (ctx.stateFiles.partitionLedger) {
        parts.push(`\n## PARTITION_LEDGER\n${ctx.stateFiles.partitionLedger}`)
    }
    if (ctx.stateFiles.toolGaps) {
        parts.push(`\n## TOOL_GAPS\n${ctx.stateFiles.toolGaps}`)
    }

    return parts.join("\n")
}
