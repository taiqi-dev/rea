import { writeFile } from "node:fs/promises";
import { join } from "node:path";
import { expect, it } from "vitest";
import { Il2cppMetadataProvider } from "../../../src/il2cpp/Il2cppMetadataProvider.js";
import { parseEvidence } from "../../../src/domain/evidence.js";
import { createTestTempDirectory } from "../../fixtures/temporaryDirectory.js";
import { createIl2cppMetadataFixture } from "../../fixtures/il2cpp/metadata.js";
import { createPeIl2cppFixture } from "../../fixtures/il2cpp/peBinary.js";

const inputs = async (bytes = createPeIl2cppFixture()) => {
  const root = await createTestTempDirectory("rea-il2cpp-native-");
  const path = join(root, "global-metadata.dat"),
    binary_path = join(root, "GameAssembly.dll");
  await writeFile(
    path,
    createIl2cppMetadataFixture({ version: 31, propertiesAndEvents: true })
      .bytes,
  );
  await writeFile(binary_path, bytes);
  return { path, binary_path };
};

it("retains both selected identities and one aligned row per native collection", async () => {
  const input = await inputs(),
    provider = new Il2cppMetadataProvider();
  try {
    const result = await provider.inspect(input);
    if (!result.ok) throw result.error;
    expect(result.value.binary?.artifact.path).toBe(input.binary_path);
    expect(result.value.binary?.format).toBe("pe");
    expect(result.value.method_addresses).toHaveLength(
      result.value.methods.length,
    );
    expect(result.value.field_types).toHaveLength(result.value.fields.length);
    expect(result.value.parameter_types).toHaveLength(
      result.value.parameters.length,
    );
    expect(result.value.return_types).toHaveLength(result.value.methods.length);
    expect(result.value.limitations.join(" ")).toContain(
      "not a cryptographic proof",
    );
  } finally {
    await provider.close();
  }
});

it.each([
  [
    "wrong module",
    createPeIl2cppFixture({ firstModuleName: "Other.dll" }),
    "AnalysisInputError",
  ],
  [
    "arm64 PE",
    createPeIl2cppFixture({ machine: 0xaa64 }),
    "AnalysisUnsupportedTargetError",
  ],
  [
    "unsupported container",
    Buffer.from("not a DLL"),
    "AnalysisUnsupportedTargetError",
  ],
] as const)(
  "preserves metadata provenance when %s cannot link",
  async (_, bytes, tag) => {
    const input = await inputs(bytes),
      provider = new Il2cppMetadataProvider();
    try {
      const result = await provider.inspect(input);
      if (result.ok) throw new Error("Expected binary refusal");
      expect(result.error._tag).toBe(tag);
      const source = parseEvidence(result.error.partialObservation);
      expect(source.subject?.local_path).toBe(input.path);
      expect(source.normalized_result).toMatchObject({
        artifact: { path: input.path },
        inventory_status: "not-returned-as-complete",
        selected_binary: {
          path: input.binary_path,
          identity_status: "observed",
        },
      });
    } finally {
      await provider.close();
    }
  },
);

it("names corrupt metadata instead of blaming the selected DLL", async () => {
  const input = await inputs(),
    provider = new Il2cppMetadataProvider();
  await writeFile(input.path, Buffer.from("broken metadata"));
  try {
    const result = await provider.inspect(input);
    if (result.ok) throw new Error("Expected metadata refusal");
    expect(result.error.message).toContain(input.path);
    expect(result.error.message).not.toContain(
      `Selected binary ${input.binary_path}`,
    );
  } finally {
    await provider.close();
  }
});

it("cancels during native scanning while preserving both snapshot identities", async () => {
  const input = await inputs(
    createPeIl2cppFixture({ payloadBytes: 4 * 1024 * 1024 }),
  );
  const controller = new AbortController();
  let checkpoints = 0;
  const provider = new Il2cppMetadataProvider(undefined, async () => {
    if (++checkpoints === 40)
      controller.abort(new Error("Stop native linking"));
  });
  try {
    const result = await provider.inspect(input, { signal: controller.signal });
    if (result.ok) throw new Error("Expected native cancellation");
    expect(result.error._tag).toBe("AnalysisCancelledError");
    expect(
      parseEvidence(result.error.partialObservation).normalized_result,
    ).toMatchObject({
      selected_binary: { path: input.binary_path, identity_status: "observed" },
    });
  } finally {
    await provider.close();
  }
});
