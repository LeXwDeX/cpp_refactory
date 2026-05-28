import { stateExists } from "../utils/state.js"
import { readStateFiles } from "../utils/state.js"

export interface ConstraintResult {
    allowed: boolean
    reasons: string[]
    warnings: string[]
}

/**
 * Check hard constraints before tool execution.
 * Returns whether the tool should be allowed to proceed.
 */
export function checkConstraints(projectDir: string): ConstraintResult {
    const reasons: string[] = []
    const warnings: string[] = []

    // Constraint 1: .cpp_refactory must exist
    if (!stateExists(projectDir)) {
        reasons.push("cpp_refactory is not installed. Run cpp-bootstrap first.")
        return { allowed: false, reasons, warnings }
    }

    // Check for open tool gaps (Constraint 2: warn but don't block)
    const state = readStateFiles(projectDir)
    if (state.toolGaps) {
        const openGaps = state.toolGaps.match(/### GAP-\d+[\s\S]*?状态.*?OPEN/g)
        if (openGaps && openGaps.length > 0) {
            warnings.push(
                `${openGaps.length} open tool gap(s) detected. Consider fixing before continuing refactoring.`
            )
        }
    }

    return { allowed: true, reasons, warnings }
}
