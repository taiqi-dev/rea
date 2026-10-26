import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { isAbsolute, join } from "node:path";

import { parseBinaryTarget } from "../dist/application/BinaryTargetResolver.js";
import { parseConfig } from "../dist/config/parseConfig.js";
import { projectAnalysisError } from "../dist/domain/analysisErrorProjection.js";
import { GhidraClient } from "../dist/ghidra/GhidraClient.js";
import { GhidraProvider } from "../dist/ghidra/GhidraProvider.js";
import { silentLogger } from "../dist/logger.js";
import { execFileOutput } from "../dist/process/ExecFileOutput.js";
import { createVerifierRun, completeVerifierRun } from "./lib/verifier-run.mjs";

// A static, source-owned PE DLL; this verifier never loads or executes it.
assert.equal(process.platform, "win32");
assert.equal(process.arch, "x64");
const compiler = process.env.REA_CC;
assert.ok(
  compiler && isAbsolute(compiler),
  "Set REA_CC to cl.exe in a Visual Studio x64 developer environment",
);
const branches = Number(process.env.REA_DECOMPILE_TIMEOUT_BRANCHES ?? 6000);
const sourceBudget = 1024 * 1024;
const longestLine = Buffer.byteLength(
  "if (rea_state[63] & 1073741824u) a = a * 31u + 999999u; else a ^= rea_state[63];\n",
);
assert.ok(
  Number.isSafeInteger(branches) &&
    branches > 0 &&
    branches <= Math.floor((sourceBudget - 1024) / longestLine),
  "Generated fixture must fit its one MiB source budget",
);
const lines = [
  "volatile unsigned rea_state[64];",
  'extern "C" __declspec(dllexport) __declspec(noinline) unsigned rea_slow(unsigned x) { unsigned a = x;',
];
for (let i = 0; i < branches; i++)
  lines.push(
    `if (rea_state[${i % 64}] & ${(1 << (i % 31)) >>> 0}u) a = a * 31u + ${i}u; else a ^= rea_state[${(i * 7) % 64}];`,
  );
lines.push(
  "return a; }",
  'extern "C" __declspec(dllexport) __declspec(noinline) int rea_small(int x) { return x + (int)rea_state[0]; }',
);
const source = lines.join("\n");
assert.ok(Buffer.byteLength(source) <= sourceBudget);
const run = createVerifierRun();
const workspace = await mkdtemp(join(tmpdir(), "rea-ghidra-timeout-windows-"));
let removable = true;
let report;
let primaryFailure;
try {
  const sourcePath = join(workspace, "timeout.cc");
  const targetPath = join(workspace, "timeout.dll");
  await writeFile(sourcePath, source);
  await execFileOutput(
    compiler,
    [
      "/nologo",
      "/Od",
      "/GS-",
      "/LD",
      "/Zl",
      sourcePath,
      `/Fo${join(workspace, "timeout.obj")}`,
      `/Fe${targetPath}`,
      "/link",
      "/NOENTRY",
      "/NODEFAULTLIB",
      `/IMPLIB:${join(workspace, "timeout.lib")}`,
    ],
    {
      cwd: workspace,
      env: process.env,
      windowsHide: true,
      timeout: 120_000,
      maxBuffer: 1024 * 1024,
      stopSignal: "SIGTERM",
    },
  );
  const originalBytes = await readFile(targetPath);
  const target = await parseBinaryTarget(targetPath);
  if (!target.ok) throw target.error;
  assert.equal(target.value.format, "pe");
  const config = parseConfig({
    ...process.env,
    REA_GHIDRA_DECOMPILE_TIMEOUT_SECONDS: "1",
  });
  if (!config.ok) throw config.error;
  let bridge;
  const provider = new GhidraProvider(
    config.value,
    silentLogger,
    process.env,
    undefined,
    (options) => {
      bridge = new GhidraClient(options);
      return bridge;
    },
  );
  const profile = await provider.resolveAnalysisProfile(target.value);
  if (!profile.ok) throw profile.error;
  assert.ok(profile.value.profile);
  const client = provider.createClient(target.value, profile.value.profile);
  removable = false;
  let queryFailure;
  try {
    const listed = await client.execute("list_procedures", {});
    if (!listed.ok) throw listed.error;
    const entry = (name) => {
      const found = listed.value.result.find((item) => item.value === name);
      assert.ok(found, `Missing exported fixture function: ${name}`);
      return found.address;
    };
    const slowEntry = entry("rea_slow");
    const smallEntry = entry("rea_small");
    const before = await bridge.ping();
    if (!before.ok) throw before.error;
    const started = performance.now();
    const slow = await client.execute("analyze_function", {
      procedure: slowEntry,
    });
    if (!slow.ok) throw slow.error;
    const dossier = slow.value.result;
    assert.equal(dossier.facet_availability.pseudocode.available, false);
    assert.match(
      dossier.facet_availability.pseudocode.reason,
      /REA_GHIDRA_DECOMPILE_TIMEOUT_SECONDS/u,
    );
    assert.equal(dossier.native_api.available, false);
    assert.equal(dossier.native_value_flow.available, false);
    assert.ok(dossier.assembly.length > branches);
    assert.ok(dossier.basic_blocks.length > 0);
    assert.equal(slow.value.cachePolicy, "live");
    assert.ok(
      slow.value.limitations.some((reason) =>
        reason.includes("REA_GHIDRA_DECOMPILE_TIMEOUT_SECONDS"),
      ),
    );
    const degradedSeconds = (performance.now() - started) / 1000;
    const atomic = await client.execute("procedure_pseudo_code", {
      procedure: slowEntry,
    });
    assert.equal(atomic.ok, false);
    const error = projectAnalysisError(atomic.error);
    assert.equal(error.code, "provider_timeout");
    assert.equal(error.retryable, true);
    assert.equal(error.details.timeout_ms, 1000);
    assert.equal(error.details.diagnostics.remote_code, "decompile_timed_out");
    const small = await client.execute("procedure_pseudo_code", {
      procedure: smallEntry,
    });
    if (!small.ok) throw small.error;
    assert.ok(small.value.result.length > 0);
    const after = await bridge.ping();
    if (!after.ok) throw after.error;
    assert.equal(after.value.run_id, before.value.run_id);
    assert.equal(after.value.target.sha256, target.value.sha256);
    assert.ok(originalBytes.equals(await readFile(targetPath)));
    report = {
      ok: true,
      platform: process.platform,
      version: after.value.provider.version,
      branches,
      degraded_seconds: degradedSeconds,
      assembly_lines: dossier.assembly.length,
      basic_blocks: dossier.basic_blocks.length,
      timeout_code: error.code,
      same_session_reused: true,
      subsequent_small_function: true,
      target_unchanged: true,
    };
  } catch (cause) {
    queryFailure = cause;
    throw cause;
  } finally {
    const closed = await client.close();
    removable = closed.ok;
    if (!closed.ok)
      throw new AggregateError(
        queryFailure === undefined
          ? [closed.error]
          : [queryFailure, closed.error],
        "Ghidra verification cleanup is incomplete",
      );
  }
} catch (cause) {
  primaryFailure = cause;
  throw cause;
} finally {
  if (removable) {
    try {
      await rm(workspace, { recursive: true });
    } catch (cleanupFailure) {
      throw new AggregateError(
        primaryFailure === undefined
          ? [cleanupFailure]
          : [primaryFailure, cleanupFailure],
        "Fixture cleanup failed",
      );
    }
  } else
    console.error(
      `Cleanup incomplete; retained owned fixture workspace: ${workspace}`,
    );
}
console.log(
  JSON.stringify({ ...report, verifier_run: await completeVerifierRun(run) }),
);
