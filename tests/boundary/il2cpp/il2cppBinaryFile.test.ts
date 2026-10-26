import { describe, expect, it } from "vitest";
import { linkIl2cppBinary } from "../../../src/il2cpp/Il2cppBinaryFile.js";
import { Il2cppBinaryFormatFailure } from "../../../src/il2cpp/Il2cppBinaryFormat.js";
import { readIl2cppMetadataForLinking } from "../../../src/il2cpp/Il2cppMetadataFile.js";
import { mappedFileOffset } from "../../../src/go/GoBinaryContainer.js";
import { readGoPeImage } from "../../../src/go/GoPeImage.js";
import { createIl2cppMetadataFixture } from "../../fixtures/il2cpp/metadata.js";
import {
  createPeIl2cppFixture,
  withPeAlias,
  PE_BASE,
  PE_RVA,
  type PeIl2cppOptions,
} from "../../fixtures/il2cpp/peBinary.js";

const metadata = (version: 24 | 27 | 29 | 31 | 39 = 31) =>
  readIl2cppMetadataForLinking(createIl2cppMetadataFixture({ version }).bytes);
const link = (bytes = createPeIl2cppFixture()) => {
  const { metadata: report, link: facts } = metadata();
  return linkIl2cppBinary(bytes, report, facts);
};
const reason = (bytes: Buffer) => {
  try {
    link(bytes);
  } catch (cause) {
    if (cause instanceof Il2cppBinaryFormatFailure) return cause.reason;
    throw cause;
  }
  throw new Error("Expected link refusal");
};

describe("Windows PE IL2CPP static address association", () => {
  it.each([24, 27, 29, 31, 39] as const)(
    "links version %i tokens rather than row order",
    (version) => {
      const { metadata: report, link: facts } = metadata(version);
      const result = linkIl2cppBinary(createPeIl2cppFixture(), report, facts);
      expect(result.format).toBe("pe");
      expect(result.architecture).toBe("amd64");
      expect(result.method_addresses).toEqual(
        [0x200, 0x210, 0x220, 0x230, null].map((offset) =>
          offset === null
            ? { state: "no-body", address: null, rva: null }
            : {
                state: "code",
                address: `0x${(PE_BASE + BigInt(PE_RVA + offset)).toString(16)}`,
                rva: `0x${(PE_RVA + offset).toString(16)}`,
              },
        ),
      );
      expect(result.return_types.map((row) => row.name)).toEqual(
        Array(5).fill(version === 27 ? null : "string[]"),
      );
      expect(result.types_count).toBe(2);
    },
  );

  it.each<[PeIl2cppOptions, string]>([
    [{ firstModuleName: "Wrong.dll" }, "code-gen-modules-not-found"],
    [{ duplicateModule: true }, "ambiguous-code-gen-module"],
    [{ duplicateRegistration: true }, "code-registration-not-found"],
    [{ codeRegistration: false }, "code-registration-not-found"],
    [{ metadataRegistration: false }, "metadata-registration-not-found"],
    [{ executable: false }, "invalid-method-pointer"],
    [{ machine: 0xaa64 }, "unsupported-container"],
  ])("refuses an inconsistent or unsupported image %j", (options, expected) => {
    expect(reason(createPeIl2cppFixture(options))).toBe(expected);
  });

  it("keeps orphan methods unknown and distinguishes observed zero slots", () => {
    const { metadata: report, link: facts } = metadata();
    const result = linkIl2cppBinary(
      createPeIl2cppFixture(),
      {
        ...report,
        methods: [...report.methods, { name: "Orphan", declaring_type: -1 }],
      },
      {
        ...facts,
        methodTokens: Uint32Array.from([...facts.methodTokens, 0x06000001]),
      },
    );
    expect(result.method_addresses.at(-1)).toEqual({
      state: "unknown",
      address: null,
      rva: null,
    });
    expect(result.method_addresses.at(-2)?.state).toBe("no-body");
  });

  it("preserves token, mapping and type failures", () => {
    const { metadata: report, link: facts } = metadata();
    expect(() =>
      linkIl2cppBinary(createPeIl2cppFixture(), report, {
        ...facts,
        methodTokens: Uint32Array.from([
          0x0600ffff,
          ...facts.methodTokens.slice(1),
        ]),
      }),
    ).toThrow("invalid-method-token");
    const bad = createPeIl2cppFixture();
    bad.writeBigUInt64LE(PE_BASE + 0xffffffffn, 0x200 + 0x300);
    expect(reason(bad)).toBe("invalid-method-pointer");
    const type = createPeIl2cppFixture();
    type.writeBigUInt64LE(0n, 0x200 + 0x900);
    expect(reason(type)).toBe("invalid-type");
  });

  it("finds a folded x64 registration only with an executable array reference", () => {
    const result = link(
      createPeIl2cppFixture({ codeRegistration: false, codeReference: true }),
    );
    expect(result.code_gen_modules_field).toBeNull();
    expect(result.code_gen_modules_array).toBe(
      PE_BASE + BigInt(PE_RVA + 0x500),
    );
  });

  it("uses the PE owner's preferred base and unique executable mappings", () => {
    const bytes = createPeIl2cppFixture(),
      pe = readGoPeImage(bytes);
    expect(pe.image_base).toBe(PE_BASE);
    expect(
      mappedFileOffset(pe.executable_mappings ?? [], PE_BASE + 0x1200n, 1),
    ).toBe(0x400);
    expect(reason(Buffer.from("not a DLL"))).toBe("unsupported-container");
  });

  it.each([
    [0x101, 20, "code-gen-modules-not-found"],
    [0x400, 24, "code-gen-modules-not-found"],
    [0x600, 16, "code-registration-not-found"],
    [0x830, 16, "metadata-registration-not-found"],
  ] as const)(
    "refuses an ambiguous PE mapping at source offset %i",
    (offset, size, expected) => {
      expect(reason(withPeAlias(createPeIl2cppFixture(), offset, size))).toBe(
        expected,
      );
    },
  );

  it("does not infer a folded registration from ambiguously mapped instruction bytes", () => {
    const bytes = createPeIl2cppFixture({
      codeRegistration: false,
      codeReference: true,
    });
    expect(reason(withPeAlias(bytes, 0xc00, 7))).toBe(
      "code-registration-not-found",
    );
  });
});
