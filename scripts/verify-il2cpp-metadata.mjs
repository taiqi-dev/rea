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
if (
  ![2, 4, 5].includes(args.length) ||
  args[0] !== "--metadata" ||
  (args.length >= 4 && args[2] !== "--binary") ||
  (args.length === 5 && args[4] !== "--ghidra")
)
  throw new Error(
    "Expected --metadata PATH; supply an unencrypted, caller-selected metadata file.",
  );
const path = resolve(args[1]);
const binaryPath = args[3] === undefined ? undefined : resolve(args[3]);
const selected = {
  path,
  ...(binaryPath === undefined ? {} : { binary_path: binaryPath }),
};
const binaryBytes =
  binaryPath === undefined ? undefined : await readFile(binaryPath);
const original = await readFile(path);
const contract = toolContract("inspect_il2cpp_metadata");
const execute = promisify(execFile);
const started = performance.now();
const cli = await execute(
  process.execPath,
  [
    "scripts/rea.mjs",
    "inspect-il2cpp-metadata",
    path,
    ...(binaryPath === undefined ? [] : ["--binary_path", binaryPath]),
    "--json",
  ],
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
  env: Object.fromEntries(
    Object.entries(process.env).filter(
      ([, value]) => typeof value === "string",
    ),
  ),
  stderr: "pipe",
});
transport.stderr?.resume();
let primary;
let summary;
let binaryOpened = false;
let ghidraReadback = null;
try {
  await client.connect(transport);
  const call = async (operation, input) =>
    requireMcpOperationResult(
      await client.callTool(
        { name: operation, arguments: input },
        { timeout: 360_000 },
      ),
      operation,
    );
  const observed = await call("inspect_il2cpp_metadata", {
    ...selected,
    detail: "complete",
  });
  assert.deepEqual(observed, report);
  summary = await call("inspect_il2cpp_metadata", selected);
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
    ...(binaryPath === undefined
      ? []
      : ["method_addresses", "return_types", "field_types", "parameter_types"]),
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
  if (binaryPath !== undefined) {
    assert.equal(report.binary.artifact.path, binaryPath);
    assert.ok(
      binaryBytes.equals(await readFile(binaryPath)),
      "Selected binary changed",
    );
    const pe = binaryBytes.readUInt32LE(60),
      optional = pe + 24;
    const base = binaryBytes.readBigUInt64LE(optional + 24);
    assert.equal(BigInt(report.binary.image_base), base);
    const ranges = Array.from(
      { length: binaryBytes.readUInt16LE(pe + 6) },
      (_, index) => {
        const at = optional + binaryBytes.readUInt16LE(pe + 20) + index * 40;
        return {
          address: base + BigInt(binaryBytes.readUInt32LE(at + 12)),
          virtual: binaryBytes.readUInt32LE(at + 8),
          bytes: binaryBytes.readUInt32LE(at + 16),
          offset: binaryBytes.readUInt32LE(at + 20),
          executable: (binaryBytes.readUInt32LE(at + 36) & 0x20000000) !== 0,
        };
      },
    );
    const mapped = (address, size = 8) => {
      const found = ranges.filter(
        (range) =>
          address >= range.address &&
          address + BigInt(size) <= range.address + BigInt(range.bytes),
      );
      assert.equal(
        found.length,
        1,
        `Oracle mapping for ${address.toString(16)}`,
      );
      return found[0].offset + Number(address - found[0].address);
    };
    const pointer = (address) => {
      const zero = ranges.filter(
        (range) =>
          range.virtual > range.bytes &&
          address >= range.address + BigInt(range.bytes) &&
          address + 8n <= range.address + BigInt(range.virtual),
      );
      return zero.length === 1
        ? 0n
        : binaryBytes.readBigUInt64LE(mapped(address));
    };
    const owner = new Map();
    for (const module of report.binary.code_gen_modules) {
      const at = mapped(BigInt(module.address), 24);
      const nameAt = mapped(binaryBytes.readBigUInt64LE(at), 1);
      assert.equal(
        binaryBytes
          .subarray(nameAt, binaryBytes.indexOf(0, nameAt))
          .toString("utf8"),
        report.images[module.image].name,
      );
      const image = report.images[module.image];
      for (let i = 0; i < image.type_count; i++) {
        const type = report.types[image.type_start + i];
        for (let m = 0; m < type.method_count; m++)
          owner.set(type.method_start + m, module);
      }
    }
    if (report.metadata_version === 31) {
      const methodsAt = original.readInt32LE(8 + 5 * 8);
      report.method_addresses.forEach((row, index) => {
        const module = owner.get(index);
        if (module === undefined) {
          assert.equal(row.state, "unknown");
          return;
        }
        const token = original.readUInt32LE(methodsAt + index * 36 + 24);
        const slots = pointer(BigInt(module.address) + 16n);
        const code = pointer(slots + BigInt((token & 0xffffff) - 1) * 8n);
        assert.deepEqual(
          row,
          code === 0n
            ? { state: "no-body", address: null, rva: null }
            : {
                state: "code",
                address: `0x${code.toString(16)}`,
                rva: `0x${(code - base).toString(16)}`,
              },
        );
        if (code !== 0n) {
          mapped(code, 1);
          assert.ok(
            ranges.some(
              (range) =>
                range.executable &&
                code >= range.address &&
                code < range.address + BigInt(range.bytes),
            ),
          );
        }
      });
    }
    if (args.includes("--ghidra")) {
      const method = report.method_addresses.findIndex(
        (row) => row.state === "code",
      );
      assert.ok(
        method >= 0,
        "The selected metadata/binary pair has no code address to read back",
      );
      const code = report.method_addresses[method];
      const opened = await call("open_binary", {
        path: binaryPath,
        provider_id: "ghidra",
      });
      binaryOpened = true;
      assert.equal(opened.sha256, report.binary.artifact.sha256);
      const mapping = await call("address_to_file_offset", {
        address: code.address,
      });
      assert.equal(mapping.file_offset, mapped(BigInt(code.address), 16));
      const memory = await call("read_bytes", {
        address: code.address,
        length: 16,
      });
      assert.equal(memory.complete, true);
      assert.equal(
        memory.bytes_hex,
        binaryBytes
          .subarray(mapping.file_offset, mapping.file_offset + 16)
          .toString("hex"),
      );
      await call("close_binary", {});
      binaryOpened = false;
      ghidraReadback = {
        method_index: method,
        method_name: report.methods[method].name,
        address: code.address,
        rva: code.rva,
        file_offset: mapping.file_offset,
        bytes_match: true,
        closed: true,
      };
      assert.ok(
        binaryBytes.equals(await readFile(binaryPath)),
        "Native provider modified the selected binary",
      );
    }
  }
} catch (cause) {
  primary = cause;
  throw cause;
} finally {
  let nativeCleanup;
  if (binaryOpened) {
    try {
      requireMcpOperationResult(
        await client.callTool(
          { name: "close_binary", arguments: {} },
          { timeout: 120_000 },
        ),
        "close_binary",
      );
    } catch (cause) {
      nativeCleanup = cause;
    }
  }
  const closed = await Promise.allSettled([client.close(), transport.close()]);
  const failures = closed.flatMap((result) =>
    result.status === "rejected" ? [result.reason] : [],
  );
  if (nativeCleanup !== undefined) failures.push(nativeCleanup);
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
    binary: report.binary,
    ghidra_readback: ghidraReadback,
    method_address_states: report.method_addresses.reduce(
      (counts, row) => ({
        ...counts,
        [row.state]: (counts[row.state] ?? 0) + 1,
      }),
      {},
    ),
    counts: summary.summary.counts,
    cli_ms: cliMs,
    complete_bytes: Buffer.byteLength(cli.stdout),
    summary_bytes: Buffer.byteLength(JSON.stringify(summary)),
    source_unchanged: true,
    cli_mcp_parity: true,
    cleanup: "complete",
  }),
);
