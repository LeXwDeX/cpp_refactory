import { describe, it, beforeEach, afterEach } from "node:test"
import assert from "node:assert/strict"
import fs from "node:fs"
import path from "node:path"
import os from "node:os"
import { buildSessionContext, type SessionContext } from "../../lib/hooks/session-lifecycle.js"

describe("session-lifecycle", () => {
    let tmpDir: string

    beforeEach(() => {
        tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "cpp-refactory-session-"))
    })

    afterEach(() => {
        fs.rmSync(tmpDir, { recursive: true, force: true })
    })

    describe("buildSessionContext", () => {
        it("returns notInstalled when .cpp_refactory does not exist", () => {
            const ctx = buildSessionContext(tmpDir)
            assert.equal(ctx.status, "notInstalled")
            assert.equal(ctx.stateFiles.refactorState, null)
        })

        it("returns ready when state files exist", () => {
            const stateDir = path.join(tmpDir, ".cpp_refactory", "state")
            fs.mkdirSync(stateDir, { recursive: true })
            fs.writeFileSync(path.join(stateDir, "REFACTOR_STATE.md"), "# State")
            fs.writeFileSync(path.join(stateDir, "PARTITION_LEDGER.md"), "# Ledger")
            fs.writeFileSync(path.join(stateDir, "TOOL_GAPS.md"), "# Gaps")

            const ctx = buildSessionContext(tmpDir)
            assert.equal(ctx.status, "ready")
            assert.equal(ctx.stateFiles.refactorState, "# State")
            assert.equal(ctx.stateFiles.partitionLedger, "# Ledger")
            assert.equal(ctx.stateFiles.toolGaps, "# Gaps")
        })

        it("returns ready even with partial state files", () => {
            const stateDir = path.join(tmpDir, ".cpp_refactory", "state")
            fs.mkdirSync(stateDir, { recursive: true })
            fs.writeFileSync(path.join(stateDir, "REFACTOR_STATE.md"), "# Only state")

            const ctx = buildSessionContext(tmpDir)
            assert.equal(ctx.status, "ready")
            assert.equal(ctx.stateFiles.refactorState, "# Only state")
            assert.equal(ctx.stateFiles.partitionLedger, null)
        })

        it("includes projectDir in context", () => {
            const ctx = buildSessionContext(tmpDir)
            assert.equal(ctx.projectDir, tmpDir)
        })
    })
})
