/** Source-owned Windows x64 PE registration fixture. Never loaded or executed. */
export const PE_BASE = 0x180000000n;
export const PE_RVA = 0x1000;
export interface PeIl2cppOptions {
  readonly firstModuleName?: string;
  readonly duplicateModule?: boolean;
  readonly duplicateRegistration?: boolean;
  readonly codeRegistration?: boolean;
  readonly codeReference?: boolean;
  readonly metadataRegistration?: boolean;
  readonly executable?: boolean;
  readonly machine?: number;
  readonly payloadBytes?: number;
}

export const createPeIl2cppFixture = (
  options: PeIl2cppOptions = {},
): Buffer => {
  const payload = Buffer.alloc(options.payloadBytes ?? 0x1000);
  const address = (offset: number) => PE_BASE + BigInt(PE_RVA + offset);
  const pointer = (offset: number, target: number) =>
    payload.writeBigUInt64LE(address(target), offset);
  payload.write(`${options.firstModuleName ?? "Assembly-CSharp.dll"}\0`, 0x101);
  payload.write("mscorlib.dll\0", 0x141);
  for (const at of [0x200, 0x210, 0x220, 0x230]) payload[at] = 0xc3;
  // Method tokens [2,1,3,1,2] resolve to [200,210,220,230,no-body].
  pointer(0x300, 0x210);
  pointer(0x308, 0x200);
  pointer(0x310, 0x220);
  pointer(0x318, 0x230);
  const module = (
    offset: number,
    name: number,
    count: number,
    slots: number,
  ) => {
    pointer(offset, name);
    payload.writeUInt32LE(count, offset + 8);
    pointer(offset + 16, slots);
  };
  module(0x400, 0x101, 3, 0x300);
  module(0x440, 0x141, 2, 0x318);
  if (options.duplicateModule) module(0x700, 0x101, 3, 0x300);
  pointer(0x500, 0x400);
  pointer(0x508, 0x440);
  const registration = (offset: number) => {
    payload.writeBigUInt64LE(2n, offset);
    pointer(offset + 8, 0x500);
  };
  if (options.codeRegistration !== false) registration(0x600);
  if (options.duplicateRegistration) registration(0x680);
  if (options.codeReference) {
    payload.set([0x48, 0x8d, 0x05], 0xc00);
    payload.writeInt32LE(0x500 - (0xc00 + 7), 0xc03);
  }
  // Il2CppType: string[] (SZARRAY -> string). Each metadata type reference is 0.
  pointer(0x900, 0x980);
  pointer(0x908, 0x990);
  pointer(0x980, 0x990);
  payload.writeUInt32LE(0x1d << 16, 0x988);
  payload.writeUInt32LE(0x0e << 16, 0x998);
  if (options.metadataRegistration !== false) {
    payload.writeBigUInt64LE(2n, 0x830);
    pointer(0x838, 0x900);
    payload.writeBigUInt64LE(4n, 0x850);
    pointer(0x858, 0x900);
    payload.writeBigUInt64LE(4n, 0x860);
    pointer(0x868, 0x900);
  }
  const header = Buffer.alloc(0x200);
  header.writeUInt16LE(0x5a4d);
  header.writeUInt32LE(0x40, 60);
  header.writeUInt32LE(0x4550, 0x40);
  header.writeUInt16LE(options.machine ?? 0x8664, 0x44);
  header.writeUInt16LE(1, 0x46);
  header.writeUInt16LE(240, 0x54);
  header.writeUInt16LE(0x2022, 0x56);
  const optional = 0x58;
  header.writeUInt16LE(0x20b, optional);
  header.writeBigUInt64LE(PE_BASE, optional + 24);
  header.writeUInt32LE(0x1000, optional + 32);
  header.writeUInt32LE(0x200, optional + 36);
  header.writeUInt32LE(
    0x1000 + Math.ceil(payload.length / 0x1000) * 0x1000,
    optional + 56,
  );
  header.writeUInt32LE(0x200, optional + 60);
  const section = optional + 240;
  header.write(".text", section);
  header.writeUInt32LE(payload.length, section + 8);
  header.writeUInt32LE(PE_RVA, section + 12);
  header.writeUInt32LE(payload.length, section + 16);
  header.writeUInt32LE(0x200, section + 20);
  header.writeUInt32LE(
    options.executable === false ? 0x40000040 : 0x60000020,
    section + 36,
  );
  return Buffer.concat([header, payload]);
};

/** Conflicting loader alias used to test candidate provenance, not executable content. */
export const withPeAlias = (
  original: Buffer,
  offset: number,
  size: number,
): Buffer => {
  const bytes = Buffer.concat([original, Buffer.alloc(0x200)]);
  bytes.writeUInt16LE(2, 0x46);
  const section = 0x58 + 240 + 40;
  bytes.write(".alias", section);
  bytes.writeUInt32LE(size, section + 8);
  bytes.writeUInt32LE(PE_RVA + offset, section + 12);
  bytes.writeUInt32LE(size, section + 16);
  bytes.writeUInt32LE(original.length, section + 20);
  bytes.writeUInt32LE(0x40000040, section + 36);
  return bytes;
};
