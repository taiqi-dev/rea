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

const convertToMachO = (pe: Buffer): Buffer => {
  const bytes = Buffer.from(pe);
  bytes.fill(0, 0, 0x200);
  bytes.writeUInt32LE(0xfeedfacf, 0);
  bytes.writeUInt32LE(0x0100000c, 4);
  bytes.writeUInt32LE(6, 12);
  bytes.writeUInt32LE(1, 16);
  bytes.writeUInt32LE(72, 20);
  bytes.writeUInt32LE(0x19, 32);
  bytes.writeUInt32LE(72, 36);
  bytes.write("__TEXT", 40);
  bytes.writeBigUInt64LE(PE_BASE + BigInt(PE_RVA), 56);
  bytes.writeBigUInt64LE(BigInt(bytes.length - 0x200), 64);
  bytes.writeBigUInt64LE(0x200n, 72);
  bytes.writeBigUInt64LE(BigInt(bytes.length - 0x200), 80);
  bytes.writeUInt32LE(5, 88);
  bytes.writeUInt32LE(5, 92);
  return bytes;
};

const convertToElf = (pe: Buffer): Buffer => {
  const base = PE_BASE + BigInt(PE_RVA);
  const dynamic = Buffer.alloc(64);
  const rela = Buffer.alloc(24);
  const physicalSlot = 0x200 + 0x308;
  rela.writeBigUInt64LE(base + 0x308n, 0);
  rela.writeBigUInt64LE(1027n, 8);
  rela.writeBigUInt64LE(pe.readBigUInt64LE(physicalSlot), 16);
  for (const [index, [tag, value]] of [
    [7n, base + BigInt(pe.length - 0x200)],
    [8n, 24n],
    [9n, 24n],
  ].entries()) {
    dynamic.writeBigUInt64LE(tag!, index * 16);
    dynamic.writeBigUInt64LE(value!, index * 16 + 8);
  }
  const bytes = Buffer.concat([pe, rela, dynamic]);
  bytes.writeBigUInt64LE(0n, physicalSlot);
  bytes.fill(0, 0, 0x200);
  bytes.write("\x7fELF", 0, "latin1");
  bytes.set([2, 1, 1], 4);
  bytes.writeUInt16LE(3, 16);
  bytes.writeUInt16LE(183, 18);
  bytes.writeUInt32LE(1, 20);
  bytes.writeBigUInt64LE(64n, 32);
  bytes.writeUInt16LE(64, 52);
  bytes.writeUInt16LE(56, 54);
  bytes.writeUInt16LE(2, 56);
  bytes.writeUInt32LE(1, 64);
  bytes.writeUInt32LE(7, 68);
  bytes.writeBigUInt64LE(0x200n, 72);
  bytes.writeBigUInt64LE(base, 80);
  bytes.writeBigUInt64LE(base, 88);
  bytes.writeBigUInt64LE(BigInt(bytes.length - 0x200), 96);
  bytes.writeBigUInt64LE(BigInt(bytes.length - 0x200), 104);
  bytes.writeUInt32LE(2, 120);
  bytes.writeBigUInt64LE(BigInt(pe.length + rela.length), 128);
  bytes.writeBigUInt64LE(base + BigInt(pe.length + rela.length - 0x200), 136);
  bytes.writeBigUInt64LE(BigInt(dynamic.length), 152);
  bytes.writeBigUInt64LE(BigInt(dynamic.length), 160);
  return bytes;
};

it.each([
  ["macho", convertToMachO],
  ["elf", convertToElf],
] as const)(
  "links ARM64 %s with the same observed definition addresses as PE",
  (format, convert) => {
    const pe = createPeIl2cppFixture();
    const linked = link(convert(pe));
    expect(linked).toMatchObject({ format, architecture: "arm64" });
    expect(linked.method_addresses.map((row) => row.address)).toEqual(
      link(pe).method_addresses.map((row) => row.address),
    );
  },
);

describe("Windows PE IL2CPP static address association", () => {
  it("links the selected generic method spec and preserves definition addresses", () => {
    const fixture = createIl2cppMetadataFixture({
      version: 31,
      wide: { genericContainers: 1, fillerTypes: 0, parameters: 0 },
    });
    fixture.bytes.writeInt32LE(0, fixture.record("methods", 0) + 20);
    fixture.bytes.writeInt32LE(
      1,
      fixture.section("genericContainers").offset + 4,
    );
    const { metadata: report, link: facts } = readIl2cppMetadataForLinking(
      fixture.bytes,
    );
    const bytes = createPeIl2cppFixture({ genericInstance: true });
    const linked = linkIl2cppBinary(bytes, report, facts, undefined, {
      genericInstances: true,
    });
    const ordinary = linkIl2cppBinary(bytes, report, facts);
    expect(ordinary.generic_methods).toBeUndefined();
    expect(linked.method_addresses).toEqual(ordinary.method_addresses);
    expect(linked.generic_methods?.issues).toEqual([]);
    expect(linked.generic_methods?.instances).toEqual([
      {
        method_spec: 0,
        method: 0,
        name: expect.stringMatching(/\$\$[^<]+<string>$/u),
        state: "code",
        address: `0x${(PE_BASE + BigInt(PE_RVA + 0x210)).toString(16)}`,
        rva: "0x1210",
      },
    ]);
  });
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
