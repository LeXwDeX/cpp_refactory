import { execFile } from "node:child_process"
import { promisify } from "node:util"

const execFileAsync = promisify(execFile)

export interface ToolCheckResult {
    name: string
    available: boolean
    path: string | null
    version?: string
}

/**
 * Check if a command-line tool is available.
 */
export async function checkTool(name: string): Promise<ToolCheckResult> {
    try {
        const { stdout } = await execFileAsync("which", [name])
        const toolPath = stdout.trim()
        if (!toolPath) {
            return { name, available: false, path: null }
        }

        // Try to get version
        let version: string | undefined
        try {
            const { stdout: versionOut } = await execFileAsync(name, ["--version"], {
                timeout: 5000,
            })
            version = versionOut.trim().split("\n")[0]
        } catch {
            // Version flag not supported, that's fine
        }

        return { name, available: true, path: toolPath, version }
    } catch {
        return { name, available: false, path: null }
    }
}

/**
 * Check all required tools for cpp_refactory.
 */
export async function checkEnvironment(): Promise<ToolCheckResult[]> {
    const tools = ["rg", "clang-tidy", "cppcheck", "bear", "clang-format", "cmake"]
    return Promise.all(tools.map(checkTool))
}
