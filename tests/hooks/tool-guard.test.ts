import { describe, it, beforeEach, afterEach } from "node:test"
import assert from "node:assert/strict"
import fs from "node:fs"
import path from "node:path"
import os from "node:os"
import { checkConstraints, type ConstraintResult } from "../../lib/hooks/tool-guard.js"

describe("tool-guard", () => {
    let tmpDir: string

    beforeEach(() => {
        tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "cpp-refactory-guard-"))
    })

    afterEach(() => {
        fs.rmSync(tmpDir, { recursive: true, force: true })
    })

    describe("checkConstraints", () => {
        it("returns blocked when .cpp_refactory does not exist", () => {
            const result = checkConstraints(tmpDir)
            assert.equal(result.allowed, false)
            assert.ok(result.reasons.some((r) => r.includes("not installed")))
        })

        it("returns allowed when state files exist", () => {
            const stateDir = path.join(tmpDir, ".cpp_refactory", "state")
            fs.mkdirSync(stateDir, { recursive: true })
            fs.writeFileSync(path.join(stateDir, "REFACTOR_STATE.md"), "# State")
            fs.writeFileSync(path.join(stateDir, "PARTITION_LEDGER.md"), "# Ledger")
            fs.writeFileSync(path.join(stateDir, "TOOL_GAPS.md"), "# Gaps")

            const result = checkConstraints(tmpDir)
            assert.equal(result.allowed, true)
            assert.equal(result.reasons.length, 0)
        })

        it("warns about open tool gaps", () => {
            const stateDir = path.join(tmpDir, ".cpp_refactory", "state")
            fs.mkdirSync(stateDir, { recursive: true })
            fs.writeFileSync(path.join(stateDir, "REFACTOR_STATE.md"), "# State")
            fs.writeFileSync(path.join(stateDir, "PARTITION_LEDGER.md"), "# Ledger")
            fs.writeFileSync(
                path.join(stateDir, "TOOL_GAPS.md"),
                "# Gaps\n\n### GAP-001: test\n- **状态**：OPEN"
            )

            const result = checkConstraints(tmpDir)
            assert.equal(result.allowed, true) // Still allowed, but warns
            assert.ok(result.warnings.some((w) => w.includes("open tool gap")))
        })
    })
})
