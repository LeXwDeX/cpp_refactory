import { describe, it, beforeEach, afterEach } from "node:test"
import assert from "node:assert/strict"
import fs from "node:fs"
import path from "node:path"
import os from "node:os"

// Import the plugin factory directly
import pluginFactory from "../index.js"

describe("plugin integration", () => {
    let tmpDir: string

    beforeEach(() => {
        tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "cpp-refactory-integration-"))
    })

    afterEach(() => {
        fs.rmSync(tmpDir, { recursive: true, force: true })
    })

    it("plugin factory is a function", () => {
        assert.equal(typeof pluginFactory, "function")
    })

    it("plugin factory returns object with hooks and tools", async () => {
        // Simulate the plugin context that OpenCode provides
        const mockCtx = {
            project: { id: "test-project" },
            client: {
                app: { log: async () => true },
                session: { prompt: async () => ({}) },
            },
            $: async () => ({ stdout: "", exitCode: 0 }),
            directory: tmpDir,
            worktree: tmpDir,
        }

        const result = await pluginFactory(mockCtx as any)

        // Should have event hook
        assert.ok(result.event, "should have event hook")
        assert.equal(typeof result.event, "function")

        // Should have tool.execute.before hook
        assert.ok(result["tool.execute.before"], "should have tool.execute.before hook")
        assert.equal(typeof result["tool.execute.before"], "function")

        // Should have shell.env hook
        assert.ok(result["shell.env"], "should have shell.env hook")
        assert.equal(typeof result["shell.env"], "function")

        // Should have tools
        assert.ok(result.tool, "should have tool definitions")
        assert.ok(result.tool["cpp-scan"], "should have cpp-scan tool")
        assert.ok(result.tool["cpp-bootstrap"], "should have cpp-bootstrap tool")
        assert.ok(result.tool["ledger-init"], "should have ledger-init tool")
    })

    it("event hook handles session.created for uninitialized project", async () => {
        const logs: string[] = []
        const mockCtx = {
            project: { id: "test" },
            client: {
                app: { log: async (input: any) => { logs.push(input.body?.message ?? ""); return true } },
                session: { prompt: async () => ({}) },
            },
            $: async () => ({ stdout: "", exitCode: 0 }),
            directory: tmpDir,
            worktree: tmpDir,
        }

        const result = await pluginFactory(mockCtx as any)
        await (result.event as Function)({
            event: { type: "session.created", properties: { id: "sess-1" } },
        })

        // Should log that cpp_refactory is not installed
        assert.ok(logs.some((l) => l.includes("not installed") || l.includes("bootstrap")))
    })

    it("shell.env hook injects CPP_REFACTORY_ROOT", async () => {
        const mockCtx = {
            project: { id: "test" },
            client: { app: { log: async () => true }, session: { prompt: async () => ({}) } },
            $: async () => ({ stdout: "", exitCode: 0 }),
            directory: tmpDir,
            worktree: tmpDir,
        }

        const result = await pluginFactory(mockCtx as any)
        const input = { cwd: tmpDir }
        const output = { env: {} as Record<string, string> }
        await (result["shell.env"] as Function)(input, output)

        assert.ok(output.env.CPP_REFACTORY_ROOT)
        assert.ok(output.env.CPP_REFACTORY_ROOT.includes(".cpp_refactory"))
    })

    it("tool.execute.before blocks when cpp_refactory not installed", async () => {
        const mockCtx = {
            project: { id: "test" },
            client: { app: { log: async () => true }, session: { prompt: async () => ({}) } },
            $: async () => ({ stdout: "", exitCode: 0 }),
            directory: tmpDir,
            worktree: tmpDir,
        }

        const result = await pluginFactory(mockCtx as any)

        // Should throw when trying to use a cpp-refactory tool without installation
        await assert.rejects(
            async () => {
                await (result["tool.execute.before"] as Function)(
                    { tool: "cpp-scan" },
                    { args: { target: "." } }
                )
            },
            { message: /not installed|bootstrap/ }
        )
    })
})
