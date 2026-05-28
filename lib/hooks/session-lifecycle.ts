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

/**
 * Format session context for injection into conversation.
 */
export function formatSessionContext(ctx: SessionContext): string {
    if (ctx.status === "notInstalled") {
        return `[cpp-refactory] cpp_refactory not installed in this project. Call cpp-bootstrap tool to initialize.`
    }

    const parts: string[] = [`[cpp-refactory] Session context loaded.`]

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
