import { describe, it, beforeEach, afterEach } from "node:test"
import assert from "node:assert/strict"
import fs from "node:fs"
import path from "node:path"
import os from "node:os"
import { readStateFiles, stateExists, getCppRefactoryDir } from "../../lib/utils/state.js"

describe("state", () => {
    let tmpDir: string

    beforeEach(() => {
        tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "cpp-refactory-test-"))
    })

    afterEach(() => {
        fs.rmSync(tmpDir, { recursive: true, force: true })
    })

    describe("getCppRefactoryDir", () => {
        it("returns .cpp_refactory path under project directory", () => {
            const dir = getCppRefactoryDir(tmpDir)
            assert.equal(dir, path.join(tmpDir, ".cpp_refactory"))
        })
    })

    describe("stateExists", () => {
        it("returns false when .cpp_refactory does not exist", () => {
            assert.equal(stateExists(tmpDir), false)
        })

        it("returns true when .cpp_refactory/state exists with files", () => {
            const stateDir = path.join(tmpDir, ".cpp_refactory", "state")
            fs.mkdirSync(stateDir, { recursive: true })
            fs.writeFileSync(path.join(stateDir, "REFACTOR_STATE.md"), "# test")
            assert.equal(stateExists(tmpDir), true)
        })
    })

    describe("readStateFiles", () => {
        it("returns null values when state does not exist", () => {
            const result = readStateFiles(tmpDir)
            assert.equal(result.refactorState, null)
            assert.equal(result.partitionLedger, null)
            assert.equal(result.toolGaps, null)
        })

        it("reads state files when they exist", () => {
            const stateDir = path.join(tmpDir, ".cpp_refactory", "state")
            fs.mkdirSync(stateDir, { recursive: true })
            fs.writeFileSync(path.join(stateDir, "REFACTOR_STATE.md"), "# Refactor State")
            fs.writeFileSync(path.join(stateDir, "PARTITION_LEDGER.md"), "# Ledger")
            fs.writeFileSync(path.join(stateDir, "TOOL_GAPS.md"), "# Gaps")

            const result = readStateFiles(tmpDir)
            assert.equal(result.refactorState, "# Refactor State")
            assert.equal(result.partitionLedger, "# Ledger")
            assert.equal(result.toolGaps, "# Gaps")
        })

        it("returns null for missing individual files", () => {
            const stateDir = path.join(tmpDir, ".cpp_refactory", "state")
            fs.mkdirSync(stateDir, { recursive: true })
            fs.writeFileSync(path.join(stateDir, "REFACTOR_STATE.md"), "# Only this")

            const result = readStateFiles(tmpDir)
            assert.equal(result.refactorState, "# Only this")
            assert.equal(result.partitionLedger, null)
            assert.equal(result.toolGaps, null)
        })
    })
})
