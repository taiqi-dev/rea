import { spawnSync } from "node:child_process";
import { access, readFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { parse } from "yaml";

if (process.platform !== "win32" || process.arch !== "x64")
  throw new Error("Windows acceptance requires a real Windows x64 host.");
const root = resolve(import.meta.dirname, "..");
const npm = process.env.npm_execpath;
if (!npm) throw new Error("Run this gate through npm run check:windows.");
const run = (arguments_) => {
  const result = spawnSync(process.execPath, arguments_, {
    cwd: root,
    stdio: "inherit",
    windowsHide: true,
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    process.exitCode = result.status ?? 1;
    throw new Error(`Windows check failed: ${arguments_.join(" ")}`);
  }
};
const task = (name) => run([npm, "run", name]);
for (const name of [
  "deps:check",
  "build:cached",
  "typecheck",
  "lint",
  "knip",
  "metadata:check",
])
  task(name);
// Application-source formatting is part of Windows acceptance. Research
// documents retain their authored evidence presentation; check:pr still reports
// the original repository-wide formatting and cross-platform suite separately.
run([
  "node_modules/oxfmt/bin/oxfmt",
  "--check",
  "src",
  "tests",
  "scripts",
  "bridge",
  "native",
  "AGENTS.md",
  "CONTRIBUTING.md",
  "package.json",
]);
task("test:prepare");
task("verify:test-discovery");
run([
  "node_modules/vitest/vitest.mjs",
  "run",
  "--project=domain",
  "--project=services",
  "--coverage.enabled=false",
]);
const workflow = parse(
  await readFile(join(root, ".github/workflows/ci.yml"), "utf8"),
);
const invocations = workflow.jobs?.["windows-curated"]?.steps
  ?.map(({ run }) => run)
  .filter((run) => run?.includes("npx vitest run"));
if (!invocations?.length)
  throw new Error("Missing retained Windows capability test lane.");
const paths = [
  ...new Set(
    invocations.flatMap((run) =>
      run.split(/\s+/u).filter((token) => token.endsWith(".test.ts")),
    ),
  ),
];
if (paths.length === 0)
  throw new Error("The retained Windows test selection is empty.");
for (const path of paths) await access(join(root, path));
run([
  "node_modules/vitest/vitest.mjs",
  "run",
  "--coverage.enabled=false",
  ...paths,
]);
run(["--test", "scripts/lib/windows-submodules.test.mjs"]);
task("verify:windows-native:artifact");
run([
  "scripts/verify-windows-native.mjs",
  ".",
  join(root, ".cache/windows-process-boundary/process-boundary.exe"),
]);
run(["scripts/verify-windows-native-inspection.mjs"]);
for (const name of [
  "verify:package:windows",
  "test:python",
  "docs:check",
  "jscpd",
  "scan:todos",
])
  task(name);
