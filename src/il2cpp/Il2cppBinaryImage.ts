import {
  GoBinaryFormatFailure,
  GoBinaryResourceFailure,
  mappedFileOffset,
  isZeroFilledSpan,
  type GoBinaryContainer,
} from "../go/GoBinaryContainer.js";
import { readGoPeImage } from "../go/GoPeImage.js";
import { Il2cppBinaryFormatFailure } from "./Il2cppBinaryFormat.js";

export interface NativeImage {
  readonly bytes: Buffer;
  readonly container: GoBinaryContainer;
  readonly imageBase: bigint;
}

/** The PE owner supplies preferred addresses and executable coverage. No DLL load or relocation execution. */
export function* openImageSteps(
  bytes: Buffer,
  architecture?: string,
): Generator<void, NativeImage> {
  yield;
  if (
    architecture !== undefined ||
    bytes.length < 2 ||
    bytes.readUInt16LE(0) !== 0x5a4d
  )
    throw new Il2cppBinaryFormatFailure(
      "unsupported-container",
      "Windows linking requires one x64 PE GameAssembly.dll; no slice selection is supported",
    );
  let container: GoBinaryContainer;
  try {
    container = readGoPeImage(bytes);
  } catch (cause) {
    if (cause instanceof GoBinaryResourceFailure)
      throw new Il2cppBinaryFormatFailure(
        "native-index-capacity",
        cause.message,
        {
          boundary: cause.boundary,
          maximum_structure_bytes: cause.maximum_bytes,
        },
      );
    if (cause instanceof GoBinaryFormatFailure)
      throw new Il2cppBinaryFormatFailure(
        cause.kind === "unsupported"
          ? "unsupported-container"
          : "malformed-container",
        cause.message,
      );
    throw cause;
  }
  if (
    container.bits !== 64 ||
    container.architecture !== "amd64" ||
    container.image_base === undefined
  )
    throw new Il2cppBinaryFormatFailure(
      "unsupported-container",
      "Only Windows x64 PE images with an observed preferred image base can be linked",
    );
  return { bytes, container, imageBase: container.image_base };
}

const mappedRead = <T>(
  image: NativeImage,
  address: bigint,
  size: number,
  read: (offset: number) => T,
): T | null => {
  try {
    return read(
      mappedFileOffset(
        image.container.mappings,
        address,
        size,
        image.container.zero_fills,
      ),
    );
  } catch (cause) {
    if (cause instanceof GoBinaryFormatFailure) return null;
    throw cause;
  }
};

export const readPointer = (
  image: NativeImage,
  address: bigint,
): bigint | null =>
  mappedRead(image, address, 8, (offset) =>
    image.bytes.readBigUInt64LE(offset),
  );

export const readUInt32 = (
  image: NativeImage,
  address: bigint,
): number | null =>
  mappedRead(image, address, 4, (offset) => image.bytes.readUInt32LE(offset));

export const isMapped = (
  image: NativeImage,
  address: bigint,
  size: number,
): boolean => mappedRead(image, address, size, () => true) === true;

export const isZeroFilled = (
  image: NativeImage,
  address: bigint,
  size: number,
): boolean =>
  isZeroFilledSpan(
    image.container.mappings,
    image.container.zero_fills,
    address,
    size,
  );

/** Admit an array across complete, unambiguous slots, including declared zero-fill. */
export const hasPointerArrayCoverage = (
  image: NativeImage,
  address: bigint,
  count: number,
): boolean => {
  const end = address + BigInt(count) * 8n;
  let cursor = address;
  while (cursor < end) {
    let fileEnd = cursor;
    for (const range of image.container.mappings)
      if (
        range.address <= cursor &&
        range.address + BigInt(range.size) > fileEnd
      )
        fileEnd = range.address + BigInt(range.size);
    let coveredEnd = fileEnd;
    if (fileEnd === cursor)
      for (const range of image.container.zero_fills)
        if (range.address <= cursor && range.address + range.size > coveredEnd)
          coveredEnd = range.address + range.size;
    const stop = coveredEnd < end ? coveredEnd : end;
    const size = Number(((stop - cursor) / 8n) * 8n);
    if (size <= 0) return false;
    try {
      if (fileEnd === cursor) {
        if (!isZeroFilled(image, cursor, size)) return false;
      } else
        mappedFileOffset(
          image.container.mappings,
          cursor,
          size,
          image.container.zero_fills,
        );
    } catch (cause) {
      if (cause instanceof GoBinaryFormatFailure) return false;
      throw cause;
    }
    cursor += BigInt(size);
  }
  return true;
};

/** Executable coverage must resolve to exactly the same unique file mapping. */
export const isExecutable = (image: NativeImage, address: bigint): boolean => {
  const actual = mappedRead(image, address, 1, (offset) => offset);
  if (actual === null) return false;
  try {
    return (
      actual ===
      mappedFileOffset(image.container.executable_mappings ?? [], address, 1)
    );
  } catch (cause) {
    if (cause instanceof GoBinaryFormatFailure) return false;
    throw cause;
  }
};

export const readSlot = (
  image: NativeImage,
  address: bigint,
): bigint | "unknown" | null => {
  try {
    return isZeroFilled(image, address, 8) ? 0n : readPointer(image, address);
  } catch (cause) {
    if (cause instanceof GoBinaryFormatFailure)
      throw new Il2cppBinaryFormatFailure("malformed-container", cause.message);
    throw cause;
  }
};
