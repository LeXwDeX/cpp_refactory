import { describe, it } from "node:test"
import assert from "node:assert/strict"
import { buildEnvVars, type EnvVars } from "../../lib/hooks/env-inject.js"

describe("env-inject", () => {
    describe("buildEnvVars", () => {
        it("returns CPP_REFACTORY_ROOT pointing to .cpp_refactory dir", () => {
            const vars = buildEnvVars("/home/user/my-project")
            assert.equal(vars.CPP_REFACTORY_ROOT, "/home/user/my-project/.cpp_refactory")
        })

        it("returns CPP_REFACTORY_SCRIPTS pointing to scripts dir", () => {
            const vars = buildEnvVars("/home/user/my-project")
            assert.ok(vars.CPP_REFACTORY_SCRIPTS)
            assert.ok(vars.CPP_REFACTORY_SCRIPTS.includes("scripts"))
        })

        it("returns CPP_REFACTORY_RESOURCES pointing to resources dir", () => {
            const vars = buildEnvVars("/home/user/my-project")
            assert.ok(vars.CPP_REFACTORY_RESOURCES)
            assert.ok(vars.CPP_REFACTORY_RESOURCES.includes("resources"))
        })

        it("handles trailing slash in project dir", () => {
            const vars = buildEnvVars("/home/user/my-project/")
            assert.equal(vars.CPP_REFACTORY_ROOT, "/home/user/my-project/.cpp_refactory")
        })
    })
})
