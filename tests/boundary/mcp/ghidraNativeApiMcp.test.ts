import { describe, expect, it } from "vitest";
import { connectGhidraMcp, sessionEvidence } from "./ghidraMcpHarness.js";

describe("Ghidra MCP native API evidence", () => {
  it("returns complete native API boundaries without output-cap unknowns", async () => {
    const harness = await connectGhidraMcp("ghidra-native-api");
    const { mcp, session } = harness;
    try {
      const inspection = sessionEvidence(
        session,
        (
          await mcp.callTool({
            name: "inspect_native_api",
            arguments: { procedure: "fixture_main" },
          })
        ).structuredContent,
      );
      expect(inspection.normalized_result).toMatchObject({
        procedure: { address: "0x401000", name: "fixture_main" },
        boundary: {
          available: true,
          return_type: { data_type: "int", confidence: "medium" },
          jump_tables: [
            {
              dispatch_address: "0x401010",
              data_sources: [{ address: "0x403000" }],
              mappings: [{ case_value: 0, target_address: "0x401020" }],
              default_targets: [
                { target_address: "0x401030", confidence: "high" },
              ],
            },
          ],
        },
        unsupported_branches: [],
        residual_unknowns: [],
      });
      expect(
        (
          await mcp.callTool({
            name: "list_unknowns",
            arguments: {},
          })
        ).structuredContent,
      ).toMatchObject({ result: { items: [] } });
    } finally {
      await harness.close();
    }
  }, 30_000);
});

it("retains partial function Evidence over MCP and retries partial composed native API reads", async () => {
  const { functionDossierSchema } =
    await import("../../../src/domain/hopperValues.js");
  const { ghidraFunctionDossier } =
    await import("../../../src/domain/ghidraValues.fixture.js");
  const { jsonValueSchema } = await import("../../../src/domain/jsonValue.js");
  const { ok } = await import("../../../src/domain/result.js");
  let reads = 0;
  const reason = "Native decompiler exceeded the configured function limit";
  const harness = await connectGhidraMcp(
    "ghidra-partial-retry",
    async (operation) => {
      if (operation !== "analyze_function")
        throw new Error(`Unexpected operation: ${operation}`);
      reads++;
      const dossier = functionDossierSchema.parse(ghidraFunctionDossier());
      if (reads > 2)
        return ok(jsonValueSchema.parse({ value: dossier, limitations: [] }));
      return ok(
        jsonValueSchema.parse({
          value: {
            ...dossier,
            pseudocode: "",
            facet_availability: { pseudocode: { available: false, reason } },
            native_api: {
              available: false,
              reason,
              residual_unknowns: [reason],
            },
            native_value_flow: {
              available: false,
              reason,
              limitations: [reason],
            },
          },
          limitations: [reason],
          cache_policy: "live",
        }),
      );
    },
  );
  try {
    const first = await harness.mcp.callTool({
      name: "analyze_function",
      arguments: { procedure: "fixture_main" },
    });
    expect(first.isError).not.toBe(true);
    const evidence = sessionEvidence(harness.session, first.structuredContent);
    expect(evidence.normalized_result).toMatchObject({
      assembly: expect.any(Array),
      facet_availability: { pseudocode: { available: false, reason } },
    });
    const inspect = () =>
      harness.mcp.callTool({
        name: "inspect_native_api",
        arguments: { procedure: "fixture_main" },
      });
    const partial = await inspect();
    expect(partial.isError).not.toBe(true);
    expect(
      sessionEvidence(harness.session, partial.structuredContent)
        .normalized_result,
    ).toMatchObject({ boundary: { available: false } });
    const complete = await inspect();
    expect(complete.isError).not.toBe(true);
    expect(
      sessionEvidence(harness.session, complete.structuredContent)
        .normalized_result,
    ).toMatchObject({ boundary: { available: true } });
    await inspect();
    expect(reads).toBe(3);
  } finally {
    await harness.close();
  }
}, 30_000);
