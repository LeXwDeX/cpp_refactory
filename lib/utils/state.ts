import path from "node:path"
import fs from "node:fs"

export interface StateFiles {
    refactorState: string | null
    partitionLedger: string | null
    toolGaps: string | null
}

/**
 * Get the .cpp_refactory directory path for a project.
 */
export function getCppRefactoryDir(projectDir: string): string {
    return path.join(projectDir, ".cpp_refactory")
}

/**
 * Check if cpp_refactory state exists in a project directory.
 */
export function stateExists(projectDir: string): boolean {
    const stateDir = path.join(getCppRefactoryDir(projectDir), "state")
    return fs.existsSync(stateDir)
}

/**
 * Read the three state files from a project directory.
 * Returns null for any file that doesn't exist.
 */
export function readStateFiles(projectDir: string): StateFiles {
    const stateDir = path.join(getCppRefactoryDir(projectDir), "state")

    const readFile = (name: string): string | null => {
        const filePath = path.join(stateDir, name)
        if (!fs.existsSync(filePath)) return null
        return fs.readFileSync(filePath, "utf-8")
    }

    return {
        refactorState: readFile("REFACTOR_STATE.md"),
        partitionLedger: readFile("PARTITION_LEDGER.md"),
        toolGaps: readFile("TOOL_GAPS.md"),
    }
}
