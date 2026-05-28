import path from "node:path"
import { getScriptsDir, getResourcesDir } from "../utils/paths.js"

export interface EnvVars {
    CPP_REFACTORY_ROOT: string
    CPP_REFACTORY_SCRIPTS: string
    CPP_REFACTORY_RESOURCES: string
}

/**
 * Build environment variables to inject into shell sessions.
 */
export function buildEnvVars(projectDir: string): EnvVars {
    // Normalize: remove trailing slash
    const normalized = projectDir.replace(/\/+$/, "")

    return {
        CPP_REFACTORY_ROOT: path.join(normalized, ".cpp_refactory"),
        CPP_REFACTORY_SCRIPTS: getScriptsDir(),
        CPP_REFACTORY_RESOURCES: getResourcesDir(),
    }
}
