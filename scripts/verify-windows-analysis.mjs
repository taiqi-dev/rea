import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { randomUUID } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import { join, resolve } from "node:path";
import { promisify } from "node:util";
import { Client } from "@modelcontextprotocol/client";
import { StdioClientTransport } from "@modelcontextprotocol/client/stdio";
import { supportedClients } from "../dist/application/SupportedClients.js";
import {
  parseClientConfiguration,
  effectiveClientServer,
} from "../dist/application/ClientConfigurationDocument.js";
import { toolContract } from "../dist/contracts/toolContracts.js";
import { requireMcpOperationResult } from "./lib/mcp-verifier-results.mjs";

assert.equal(
  process.platform,
  "win32",
  "Real Windows acceptance requires Windows.",
);
const root = resolve(import.meta.dirname, "..");
const target = join(root, "build/fixtures/rea-windows-analysis.exe");
const entry = join(root, "scripts/rea.mjs");
const output = join(root, ".cache/windows-analysis-proof", randomUUID());
await mkdir(output, { recursive: true });
const sourceBytes = await readFile(target);
const execute = promisify(execFile);
for (const [level, expected] of [
  ["3", "REA_WINDOWS_READY score=55"],
  ["1", "REA_WINDOWS_REVIEW score=35"],
]) {
  const result = await execute(target, [level], {
    windowsHide: true,
    timeout: 10_000,
  });
  assert.equal(result.stdout.trim(), expected);
}

const codex = supportedClients(homedir(), process.platform, process.env).find(
  ({ name }) => name === "codex",
);
assert.ok(
  codex && !codex.configPathError,
  "Codex configuration location is unresolved.",
);
const document = parseClientConfiguration(
  await readFile(codex.configPath, "utf8"),
  codex.format,
);
const registration = effectiveClientServer(document, "rea");
assert.ok(
  registration &&
    typeof registration.command === "string" &&
    Array.isArray(registration.args),
  "Configure Codex with this checkout's REA setup first.",
);
assert.equal(
  resolve(registration.command),
  resolve(process.execPath),
  "Codex must use the project-local Node.",
);
assert.deepEqual(
  registration.args,
  [entry, "mcp"],
  "Codex must launch this fork's source checkout.",
);
const environment = { ...process.env, ...registration.env };
const cli = await execute(
  process.execPath,
  [entry, "decompile", target, "rea_score", "--provider", "ghidra", "--json"],
  {
    env: environment,
    windowsHide: true,
    timeout: 360_000,
    maxBuffer: 8 * 1024 * 1024,
  },
);
const cliEvidence = JSON.parse(cli.stdout);
assert.match(cliEvidence.normalized_result, /\b(?:0x19|25)\b/u);
await writeFile(join(output, "cli.json"), JSON.stringify(cliEvidence, null, 2));

const transport = new StdioClientTransport({
  command: registration.command,
  args: registration.args,
  env: environment,
  stderr: "pipe",
});
let diagnostics = "";
transport.stderr?.on("data", (chunk) => {
  diagnostics = (diagnostics + String(chunk)).slice(-64 * 1024);
});
const client = new Client({
  name: "rea-windows-analysis-acceptance",
  version: "1",
});
const evidence = [];
const call = async (name, input = {}) => {
  const contract = toolContract(name);
  const result = await client.callTool(
    { name, arguments: contract.inputSchema.parse(input) },
    { timeout: 360_000 },
  );
  const value = requireMcpOperationResult(result, name, contract);
  evidence.push({
    name,
    result:
      result.structuredContent ??
      JSON.parse(result.content.find(({ type }) => type === "text").text),
  });
  return value;
};
let closed = false;
let connected = false;
const failures = [];
try {
  await client.connect(transport);
  connected = true;
  const identity = await call("binary_session", {
    expected_server_path: entry,
  });
  assert.equal(identity.open, false);
  assert.equal(identity.server_identity.alignment.state, "aligned");
  await call("open_binary", { path: target, provider_id: "ghidra" });
  const procedures = await call("list_procedures");
  const score = procedures.find(({ value }) => value === "rea_score");
  assert.ok(score, "Ghidra must recover the exported score function.");
  const scoreCode = await call("procedure_pseudo_code", {
    procedure: score.address,
  });
  assert.match(scoreCode, /\b(?:0x19|25)\b/u);
  assert.match(scoreCode, /\*\s*(?:10|0xa)\b/u);
  const labelCode = await call("procedure_pseudo_code", {
    procedure: "rea_label",
  });
  assert.match(labelCode, /REA_WINDOWS_READY/u);
  assert.match(labelCode, /REA_WINDOWS_REVIEW/u);
  const callers = await call("procedure_callers", { procedure: score.address });
  assert.ok(callers.length > 0, "Ghidra must recover the compiled caller.");
  const memory = await call("read_bytes", {
    address: score.address,
    length: 16,
  });
  const mapping = await call("address_to_file_offset", {
    address: score.address,
  });
  assert.equal(memory.complete, true);
  assert.equal(
    memory.bytes_hex,
    sourceBytes
      .subarray(mapping.file_offset, mapping.file_offset + 16)
      .toString("hex"),
  );
  const snapshot = join(output, "analysis-snapshot.json");
  await call("close_binary", { snapshot_path: snapshot });
  closed = true;
  await call("open_binary", {
    path: target,
    provider_id: "ghidra",
    snapshot_path: snapshot,
  });
  closed = false;
  assert.equal(
    await call("procedure_pseudo_code", { procedure: score.address }),
    scoreCode,
  );
  await call("close_binary");
  closed = true;
  assert.equal((await call("binary_session")).open, false);
} catch (cause) {
  failures.push(cause);
} finally {
  try {
    if (connected && !closed) await call("close_binary");
  } catch (cause) {
    failures.push(cause);
  }
  try {
    await client.close();
  } catch (cause) {
    failures.push(cause);
  }
  await writeFile(
    join(output, "mcp-evidence.json"),
    JSON.stringify(evidence, null, 2),
  );
  await writeFile(join(output, "diagnostics.log"), diagnostics);
}
if (failures.length > 0)
  throw new AggregateError(failures, `Real analysis failed; inspect ${output}`);
assert.ok(
  sourceBytes.equals(await readFile(target)),
  "Analysis modified the selected executable.",
);
const report = {
  ok: true,
  target,
  codex_configuration: codex.configPath,
  runtime_branches: true,
  cli_decompilation: true,
  registered_mcp: true,
  recovered_functions: ["rea_score", "rea_label"],
  callers: true,
  memory_file_mapping: true,
  snapshot_reopen: true,
  source_unchanged: true,
  closed: true,
  evidence_directory: output,
};
await writeFile(join(output, "report.json"), JSON.stringify(report, null, 2));
process.stdout.write(`${JSON.stringify(report)}\n`);
