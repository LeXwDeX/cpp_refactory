import { describe, it } from "node:test"
import assert from "node:assert/strict"
import path from "node:path"
import { fileURLToPath } from "node:url"
import { resolveScriptPath, getScriptsDir, getResourcesDir } from "../../lib/utils/paths.js"

describe("paths", () => {
    describe("getScriptsDir", () => {
        it("returns absolute path to scripts directory", () => {
            const dir = getScriptsDir()
            assert.ok(path.isAbsolute(dir))
            assert.ok(dir.endsWith("scripts"))
        })
    })

    describe("getResourcesDir", () => {
        it("returns absolute path to resources directory", () => {
            const dir = getResourcesDir()
            assert.ok(path.isAbsolute(dir))
            assert.ok(dir.endsWith("resources"))
        })
    })

    describe("resolveScriptPath", () => {
        it("resolves a known script name to absolute path", () => {
            const p = resolveScriptPath("cpp-scan.sh")
            assert.ok(path.isAbsolute(p))
            assert.ok(p.endsWith("cpp-scan.sh"))
        })

        it("resolves another known script", () => {
            const p = resolveScriptPath("ledger.sh")
            assert.ok(p.endsWith("ledger.sh"))
        })

        it("throws for unknown script name", () => {
            assert.throws(() => resolveScriptPath("nonexistent.sh"), {
                message: /not found/,
            })
        })
    })
})
