import { readFile, unlink, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { expect, it } from "vitest";
import { createEvidence, parseEvidence } from "../../src/domain/evidence.js";
import { il2cppMetadataSchema } from "../../src/domain/il2cpp/il2cppMetadata.js";
import { analysisViewResultSchema } from "../../src/domain/analysisView/analysisView.js";
import { createTestTempDirectory } from "../fixtures/temporaryDirectory.js";
import { createIl2cppMetadataFixture } from "../fixtures/il2cpp/metadata.js";
import {
  createPeIl2cppFixture,
  withPeAlias,
} from "../fixtures/il2cpp/peBinary.js";
import { connectLocalToolsMcp } from "../fixtures/localToolsMcp.js";
import { parseMcpToolError } from "../fixtures/mcpToolError.js";
import { cliTest } from "../support/cli/cliFixture.js";

const inputs = async (name = "Assembly-CSharp.dll") => {
  const root = await createTestTempDirectory("rea-il2cpp-native-cli-");
  const path = join(root, "global-metadata.dat"),
    binary_path = join(root, "GameAssembly.dll");
  await writeFile(
    path,
    createIl2cppMetadataFixture({ version: 31, propertiesAndEvents: true })
      .bytes,
  );
  await writeFile(
    binary_path,
    createPeIl2cppFixture({ firstModuleName: name }),
  );
  return { path, binary_path };
};

cliTest(
  "matches native CLI/MCP Evidence and queries addresses after both inputs are removed",
  async ({ cli }) => {
    const input = await inputs(),
      before = await readFile(input.binary_path);
    const result = await cli.run({
      arguments: [
        "inspect-il2cpp-metadata",
        input.path,
        "--binary_path",
        input.binary_path,
        "--json",
      ],
    });
    expect(result.exitCode, result.stderr).toBe(0);
    const cliEvidence = parseEvidence(result.json),
      report = il2cppMetadataSchema.parse(cliEvidence.normalized_result);
    const { call } = await connectLocalToolsMcp();
    const response = await call("inspect_il2cpp_metadata", {
      ...input,
      detail: "complete",
    });
    expect(response.isError).not.toBe(true);
    expect(parseEvidence(response.structuredContent).normalized_result).toEqual(
      report,
    );
    expect(cliEvidence.parameters).toEqual(input);
    expect(cliEvidence.locations).toContainEqual({
      kind: "artifact-path",
      path: input.binary_path,
    });
    const summary = await call("inspect_il2cpp_metadata", input);
    const overview = analysisViewResultSchema.parse(
      parseEvidence(summary.structuredContent).normalized_result,
    );
    if (overview.kind !== "summary") throw new Error("Expected summary");
    expect(before.equals(await readFile(input.binary_path))).toBe(true);
    await unlink(input.path);
    await unlink(input.binary_path);
    for (const collection of [
      "method_addresses",
      "return_types",
      "field_types",
      "parameter_types",
    ] as const) {
      const page = await call("inspect_analysis_view", {
        source: {
          kind: "retained-evidence",
          evidence_id: overview.parent_evidence_id,
        },
        view: {
          kind: "il2cpp-metadata",
          collection,
          indices: [0, 1],
          fields: [],
        },
      });
      expect(page.isError).not.toBe(true);
      const value = analysisViewResultSchema.parse(
        parseEvidence(page.structuredContent).normalized_result,
      );
      if (value.kind !== "il2cpp-metadata") throw new Error("Wrong view");
      expect(value.items).toEqual(
        report[collection].slice(0, 2).map((_, index) => ({ index })),
      );
      expect(value.binary_source?.artifact.sha256).toBe(
        report.binary?.artifact.sha256,
      );
    }
    if (report.binary === null || cliEvidence.subject === null)
      throw new Error("Expected paired identities");
    const malformed = {
      ...report,
      binary: {
        ...report.binary,
        code_gen_modules: report.binary.code_gen_modules.map((module, index) =>
          index === 0 ? { ...module, image: 999 } : module,
        ),
      },
    };
    const invented = createEvidence(
      {
        path: input.path,
        sha256: cliEvidence.subject.digest.sha256,
        format: "file",
      },
      cliEvidence.provider,
      {
        operation: "inspect_il2cpp_metadata",
        parameters: input,
        result: malformed,
      },
    );
    const refused = parseMcpToolError(
      await call("inspect_analysis_view", {
        source: { kind: "inline", evidence: invented },
        view: { kind: "il2cpp-metadata", collection: "code_gen_modules" },
      }),
    );
    expect(refused.error.code).toBe("invalid_request");
  },
);

cliTest(
  "refuses a mismatched DLL identically through CLI and MCP with metadata source Evidence",
  async ({ cli }) => {
    const input = await inputs("Other.dll");
    const result = await cli.run({
      arguments: [
        "inspect-il2cpp-metadata",
        input.path,
        "--binary_path",
        input.binary_path,
        "--json",
      ],
    });
    expect(result.exitCode).toBe(1);
    expect(result.json).toMatchObject({
      code: "invalid_request",
      details: {
        issues: [
          {
            path: ["binary_path"],
            message: expect.stringContaining(input.binary_path),
          },
        ],
      },
    });
    const { call } = await connectLocalToolsMcp();
    const failed = parseMcpToolError(
      await call("inspect_il2cpp_metadata", input),
    );
    expect(failed.error.code).toBe("invalid_request");
    expect(failed.error).toMatchObject({
      details: {
        issues: [
          {
            path: ["binary_path"],
            message: expect.stringContaining(input.binary_path),
          },
        ],
      },
    });
  },
);

it("does not accept a missing native binary as an empty address inventory", async () => {
  const input = await inputs();
  await unlink(input.binary_path);
  const { call } = await connectLocalToolsMcp();
  const failed = parseMcpToolError(
    await call("inspect_il2cpp_metadata", input),
  );
  expect(failed.error.code).toBe("invalid_request");
});

it("refuses ambiguous native registration provenance through MCP", async () => {
  const input = await inputs();
  await writeFile(
    input.binary_path,
    withPeAlias(createPeIl2cppFixture(), 0x400, 24),
  );
  const { call } = await connectLocalToolsMcp();
  const failed = parseMcpToolError(
    await call("inspect_il2cpp_metadata", input),
  );
  expect(failed.error).toMatchObject({
    code: "invalid_request",
    details: {
      issues: [
        {
          path: ["binary_path"],
          message: expect.stringContaining("code-gen-modules-not-found"),
        },
      ],
    },
  });
});
