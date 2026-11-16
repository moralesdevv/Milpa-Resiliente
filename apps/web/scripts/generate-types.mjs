import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, isAbsolute, resolve } from "node:path";

const defaultSpec = "../../docs/openapi/openapi.json";
const configuredSpec = process.env.MILPA_OPENAPI_SPEC || defaultSpec;
const specPath = isAbsolute(configuredSpec) ? configuredSpec : resolve(process.cwd(), configuredSpec);
const outputPath = resolve(process.cwd(), "src/api/types.gen.ts");
const require = createRequire(import.meta.url);
const openapiPackage = require.resolve("openapi-typescript/package.json");
const cliPath = resolve(dirname(openapiPackage), "bin/cli.js");

if (!existsSync(specPath)) throw new Error(`OpenAPI file not found: ${specPath}`);
const result = spawnSync(process.execPath, [cliPath, specPath, "-o", outputPath], { stdio: "inherit" });
if (result.error) throw result.error;
if (result.status !== 0) process.exit(result.status ?? 1);
