import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { promisify } from "node:util";
import { Client } from "@modelcontextprotocol/client";
import { StdioClientTransport } from "@modelcontextprotocol/client/stdio";
import { toolContract } from "../dist/contracts/toolContracts.js";
import { analysisViewResultSchema } from "../dist/domain/analysisView/analysisView.js";
import { requireMcpOperationResult } from "./lib/mcp-verifier-results.mjs";

const args = process.argv.slice(2);
if (args.length !== 2 || args[0] !== "--metadata")
  throw new Error(
    "Expected --metadata PATH; supply an unencrypted, caller-selected metadata file.",
  );
const path = resolve(args[1]);
const original = await readFile(path);
const contract = toolContract("inspect_il2cpp_metadata");
const execute = promisify(execFile);
const started = performance.now();
const cli = await execute(
  process.execPath,
  ["scripts/rea.mjs", "inspect-il2cpp-metadata", path, "--json"],
  { windowsHide: true, timeout: 120_000, maxBuffer: 128 * 1024 * 1024 },
);
const complete = contract.outputSchema.parse(JSON.parse(cli.stdout));
const report = complete.normalized_result;
assert.equal(report.artifact.path, path);
assert.equal(report.artifact.bytes, original.length);
const cliMs = performance.now() - started;
const client = new Client({ name: "il2cpp-windows-verifier", version: "1" });
const transport = new StdioClientTransport({
  command: process.execPath,
  args: [resolve("scripts/rea.mjs"), "mcp"],
  stderr: "pipe",
});
transport.stderr?.resume();
let primary;
let summary;
try {
  await client.connect(transport);
  const call = async (operation, input) =>
    requireMcpOperationResult(
      await client.callTool(
        { name: operation, arguments: input },
        { timeout: 120_000 },
      ),
      operation,
    );
  const observed = await call("inspect_il2cpp_metadata", {
    path,
    detail: "complete",
  });
  assert.deepEqual(observed, report);
  summary = await call("inspect_il2cpp_metadata", { path });
  for (const collection of [
    "sections",
    "images",
    "types",
    "methods",
    "fields",
    "properties",
    "events",
    "parameters",
    "string_literals",
  ]) {
    assert.equal(summary.summary.counts[collection], report[collection].length);
    const page = analysisViewResultSchema.parse(
      await call("inspect_analysis_view", {
        source: {
          kind: "retained-evidence",
          evidence_id: summary.parent_evidence_id,
        },
        view: { kind: "il2cpp-metadata", collection, limit: 16 },
      }),
    );
    assert.deepEqual(
      page.items,
      report[collection].slice(0, 16).map((row, index) => ({ ...row, index })),
    );
  }
  // A format-level oracle independent of the production decoder for v31.
  if (report.metadata_version === 31) {
    const section = (index) => ({
      offset: original.readInt32LE(8 + index * 8),
      bytes: original.readInt32LE(12 + index * 8),
    });
    const strings = section(2);
    const name = (index) => {
      const offset = strings.offset + index;
      const end = original.indexOf(0, offset);
      assert.ok(
        index >= 0 && end >= offset && end < strings.offset + strings.bytes,
      );
      return original.subarray(offset, end).toString("utf8");
    };
    for (const [collection, sectionIndex, stride] of [
      ["images", 20, 40],
      ["types", 19, 88],
      ["methods", 5, 36],
    ]) {
      const table = section(sectionIndex);
      assert.equal(table.bytes, report[collection].length * stride);
      report[collection].forEach((row, index) =>
        assert.equal(
          row.name,
          name(original.readInt32LE(table.offset + index * stride)),
        ),
      );
    }
  }
  assert.ok(original.equals(await readFile(path)), "Input metadata changed");
} catch (cause) {
  primary = cause;
  throw cause;
} finally {
  const closed = await Promise.allSettled([client.close(), transport.close()]);
  const failures = closed.flatMap((result) =>
    result.status === "rejected" ? [result.reason] : [],
  );
  if (failures.length > 0)
    throw new AggregateError(
      primary === undefined ? failures : [primary, ...failures],
      "IL2CPP verifier cleanup failed",
    );
}
console.log(
  JSON.stringify({
    ok: true,
    platform: process.platform,
    metadata_version: report.metadata_version,
    artifact: report.artifact,
    counts: summary.summary.counts,
    cli_ms: cliMs,
    complete_bytes: Buffer.byteLength(cli.stdout),
    summary_bytes: Buffer.byteLength(JSON.stringify(summary)),
    source_unchanged: true,
    cli_mcp_parity: true,
    cleanup: "complete",
  }),
);
