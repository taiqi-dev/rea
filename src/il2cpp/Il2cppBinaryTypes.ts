import { Il2cppBinaryFormatFailure } from "./Il2cppBinaryFormat.js";
import {
  readPointer,
  readUInt32,
  isMapped,
  type NativeImage,
} from "./Il2cppBinaryImage.js";
import type {
  Il2cppMetadataDecoded,
  Il2cppMetadataLinkFacts,
} from "./Il2cppMetadataFile.js";
const PRIMITIVES = new Map([
  [0x01, "void"],
  [0x02, "bool"],
  [0x03, "char"],
  [0x04, "sbyte"],
  [0x05, "byte"],
  [0x06, "short"],
  [0x07, "ushort"],
  [0x08, "int"],
  [0x09, "uint"],
  [0x0a, "long"],
  [0x0b, "ulong"],
  [0x0c, "float"],
  [0x0d, "double"],
  [0x0e, "string"],
  [0x16, "System.TypedReference"],
  [0x18, "nint"],
  [0x19, "nuint"],
  [0x1c, "object"],
]);

// Cached rendered text has its own workspace bound; the report owner separately
// charges each returned occurrence and JSON expansion. No live-state cache.
const TYPE_TEXT_BYTES = 64 * 1024 * 1024;
const TYPE_DEPTH = 64;

/** Render one snapshot's type graph cooperatively without allocating unchecked expansions. */
export const createTypeNamer = (
  image: NativeImage,
  metadata: Il2cppMetadataDecoded,
  facts: Il2cppMetadataLinkFacts,
  version: number,
  beforeText?: (bytes: number) => void,
  includeByref = true,
) => {
  const fail = (message: string): never => {
    throw new Il2cppBinaryFormatFailure("invalid-type", message);
  };
  const pointer = (address: bigint, label: string) =>
    readPointer(image, address) ??
    fail(`${label} at 0x${address.toString(16)} is not file mapped`);
  const u32 = (address: bigint, label: string) =>
    readUInt32(image, address) ??
    fail(`${label} at 0x${address.toString(16)} is not file mapped`);
  let cachedBytes = 0;
  let work = 0;
  const guard = (bytes: number) => {
    if (bytes > TYPE_TEXT_BYTES - cachedBytes)
      throw new Il2cppBinaryFormatFailure(
        "native-type-text-capacity",
        `rendered type text workspace exceeds ${TYPE_TEXT_BYTES} UTF-8 bytes`,
        { maximum_type_text_bytes: TYPE_TEXT_BYTES },
      );
    beforeText?.(bytes);
  };
  const join = (parts: readonly string[], separator = "") => {
    let bytes = Math.max(parts.length - 1, 0) * Buffer.byteLength(separator);
    for (const part of parts) {
      bytes += Buffer.byteLength(part);
      guard(bytes);
    }
    return parts.join(separator);
  };
  function* definitionName(index: number): Generator<void, string> {
    const seen = new Set<number>();
    const parts: string[] = [];
    let namespace = "";
    for (let at = index; at !== -1;) {
      if (seen.has(at)) fail(`cyclic declaring type at ${at}`);
      if (++work % 256 === 0) yield;
      seen.add(at);
      const type =
        metadata.types[at] ?? fail(`type definition ${at} is out of range`);
      parts.push(type.name);
      namespace = type.namespace;
      at = type.declaring_type;
    }
    const name = join(parts.reverse(), "+");
    return namespace === "" ? name : join([namespace, name], ".");
  }
  const byAddress = new Map<bigint, string>();
  const active = new Set<bigint>();
  const byrefBit = version >= 29 ? 29 : 30;
  function* name(address: bigint, depth: number): Generator<void, string> {
    const cached = byAddress.get(address);
    if (cached !== undefined) return cached;
    if (active.has(address))
      fail(`cyclic Il2CppType at 0x${address.toString(16)}`);
    if (depth > TYPE_DEPTH)
      throw new Il2cppBinaryFormatFailure(
        "type-nesting-capacity",
        `type rendering exceeds ${TYPE_DEPTH} nested frames`,
        { maximum_type_nesting: TYPE_DEPTH },
      );
    active.add(address);
    try {
      if (++work % 256 === 0) yield;
      const data = pointer(address, "Il2CppType data");
      const bits = u32(address + 8n, "Il2CppType attributes");
      const kind = (bits >>> 16) & 0xff;
      const index = Number(BigInt.asIntN(32, data & 0xffffffffn));
      let result: string;
      const primitive = PRIMITIVES.get(kind);
      if (primitive !== undefined) result = primitive;
      else if (kind === 0x11 || kind === 0x12)
        result = yield* definitionName(index);
      else if (kind === 0x0f || kind === 0x1d)
        result = join([
          yield* name(data, depth + 1),
          kind === 0x0f ? "*" : "[]",
        ]);
      else if (kind === 0x14) {
        const rank = u32(data + 8n, "Il2CppArrayType rank") & 0xff;
        if (rank === 0) fail("array rank is zero");
        result = join([
          yield* name(pointer(data, "array element"), depth + 1),
          "[",
          ",".repeat(rank - 1),
          "]",
        ]);
      } else if (kind === 0x13 || kind === 0x1e)
        result =
          facts.genericParameterName(index) ??
          fail(`generic parameter ${index} is out of range`);
      else if (kind === 0x15) result = yield* generic(data, depth);
      else
        throw new Il2cppBinaryFormatFailure(
          "unsupported-type-kind",
          `type kind 0x${kind.toString(16)} is not rendered`,
        );
      if (includeByref && ((bits >>> byrefBit) & 1) === 1)
        result = join([result, "&"]);
      const bytes = Buffer.byteLength(result);
      guard(bytes);
      cachedBytes += bytes;
      byAddress.set(address, result);
      return result;
    } finally {
      active.delete(address);
    }
  }
  function* generic(data: bigint, depth: number): Generator<void, string> {
    const definition =
      version >= 27
        ? yield* name(pointer(data, "generic class type"), depth + 1)
        : yield* definitionName(u32(data, "generic class definition"));
    const instance = pointer(data + 8n, "generic class instance");
    const count = u32(instance, "generic argument count");
    const argv = pointer(instance + 8n, "generic arguments");
    guard(Math.max(count - 1, 0) * 2);
    if (!isMapped(image, argv, count * 8))
      fail("generic argument array is not file mapped");
    const args: string[] = [];
    let bytes = Math.max(count - 1, 0) * 2;
    for (let slot = 0; slot < count; slot++) {
      if (++work % 256 === 0) yield;
      const argument = yield* name(
        pointer(argv + BigInt(slot * 8), "generic argument"),
        depth + 1,
      );
      bytes += Buffer.byteLength(argument);
      guard(bytes);
      args.push(argument);
    }
    return join([definition.replace(/`\d+$/u, ""), "<", join(args, ", "), ">"]);
  }
  return name;
};

/** Render a method-spec label using the existing bounded C#-style type names. */
export const createMethodSpecNamer = (
  image: NativeImage,
  metadata: Il2cppMetadataDecoded,
  facts: Il2cppMetadataLinkFacts,
  version: number,
  beforeText?: (bytes: number) => void,
) => {
  const renderType = createTypeNamer(
    image,
    metadata,
    facts,
    version,
    beforeText,
    false,
  );
  const fail = (message: string): never => {
    throw new Il2cppBinaryFormatFailure("invalid-type", message);
  };
  const guard = (bytes: number): void => {
    if (bytes > TYPE_TEXT_BYTES)
      throw new Il2cppBinaryFormatFailure(
        "native-type-text-capacity",
        "Rendered generic method label exceeds its UTF-8 byte limit",
        { maximum_type_text_bytes: TYPE_TEXT_BYTES },
      );
    beforeText?.(bytes);
  };
  function* argumentsAt(instance: bigint | null): Generator<void, string> {
    if (instance === null) return "";
    const count =
      readUInt32(image, instance) ??
      fail("Generic instance count is unreadable");
    const table =
      readPointer(image, instance + 8n) ??
      fail("Generic argument table is unreadable");
    guard(count * 2);
    if (!isMapped(image, table, count * 8))
      fail("Generic arguments are outside the image");
    const args: string[] = [];
    let bytes = count * 2;
    for (let index = 0; index < count; index++) {
      if (index % 256 === 0) yield;
      const type =
        readPointer(image, table + BigInt(index * 8)) ??
        fail("Generic argument pointer is unreadable");
      const name = yield* renderType(type, 0);
      bytes += Buffer.byteLength(name);
      guard(bytes);
      args.push(name);
    }
    return `<${args.join(", ")}>`;
  }
  return function* methodSpecName(
    method: number,
    classInstance: bigint | null,
    methodInstance: bigint | null,
  ): Generator<void, string> {
    const row =
      metadata.methods[method] ??
      fail("Generic method definition is unavailable");
    const parts: string[] = [];
    let namespace = "";
    let bytes = Buffer.byteLength(row.name) + 2;
    for (let at = row.declaring_type; at >= 0;) {
      if (parts.length % 256 === 0) yield;
      const type =
        metadata.types[at] ?? fail("Generic method owner is unavailable");
      const name = type.name.replace(/`\d+$/u, "");
      bytes += Buffer.byteLength(name) + 1;
      guard(bytes);
      parts.push(name);
      namespace = type.namespace;
      at = type.declaring_type;
    }
    if (parts.length === 0) fail("Generic method has no declaring type");
    const classArguments = yield* argumentsAt(classInstance);
    const methodArguments = yield* argumentsAt(methodInstance);
    guard(
      bytes +
        Buffer.byteLength(namespace) +
        Buffer.byteLength(classArguments) +
        Buffer.byteLength(methodArguments),
    );
    const owner = parts.reverse().join("+");
    return `${namespace === "" ? "" : namespace + "."}${owner}${classArguments}$$${row.name}${methodArguments}`;
  };
};
