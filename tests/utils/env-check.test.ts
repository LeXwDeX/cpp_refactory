import { describe, it } from "node:test"
import assert from "node:assert/strict"
import { checkTool, type ToolCheckResult } from "../../lib/utils/env-check.js"

describe("env-check", () => {
    describe("checkTool", () => {
        it("returns available for a known tool (node)", async () => {
            const result = await checkTool("node")
            assert.equal(result.available, true)
            assert.ok(result.path)
        })

        it("returns unavailable for a nonexistent tool", async () => {
            const result = await checkTool("definitely-not-a-real-tool-xyz")
            assert.equal(result.available, false)
            assert.equal(result.path, null)
        })
    })

    describe("ToolCheckResult type", () => {
        it("has correct shape", () => {
            const result: ToolCheckResult = {
                name: "test",
                available: true,
                path: "/usr/bin/test",
                version: "1.0",
            }
            assert.equal(result.name, "test")
            assert.equal(result.available, true)
        })
    })
})
