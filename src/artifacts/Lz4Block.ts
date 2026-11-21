import { scheduler } from "node:timers/promises";
import { abortIfNeeded } from "./ArtifactHash.js";
import { ArtifactReaderFailure } from "./ArtifactReader.js";

const MAX_DECODED_BYTES = 64 * 1024 * 1024;
const badBlock = (message: string): never => {
  throw new ArtifactReaderFailure("format", message);
};

/** Decode a raw LZ4 block within its declared output extent. */
export const decodeLz4Block = async (
  input: Buffer,
  expected: number,
  signal?: AbortSignal,
): Promise<Buffer> => {
  if (
    !Number.isSafeInteger(expected) ||
    expected < 0 ||
    expected > MAX_DECODED_BYTES
  )
    throw new ArtifactReaderFailure(
      "limit",

      "LZ4 decoded length exceeds the object budget",
    );
  const output = Buffer.alloc(expected);
  let read = 0,
    write = 0,
    checkpoint = 0;
  const byte = (): number => {
    if (read >= input.length) return badBlock("Truncated LZ4 block");
    return input[read++]!;
  };
  const length = (nibble: number, remaining: number): number => {
    let total = nibble;
    if (nibble === 15) {
      let extra: number;
      do {
        extra = byte();
        if (extra > remaining - total)
          badBlock("LZ4 length exceeds its declared output");
        total += extra;
      } while (extra === 255);
    }
    if (total > remaining) badBlock("LZ4 length exceeds its declared output");
    return total;
  };
  while (read < input.length) {
    if (write - checkpoint >= 4 * 1024 * 1024) {
      await scheduler.yield();
      checkpoint = write;
    }
    abortIfNeeded(signal);
    const token = byte();
    const literals = length(token >>> 4, expected - write);
    if (literals > input.length - read)
      badBlock("LZ4 literals exceed their encoded input");
    input.copy(output, write, read, read + literals);
    read += literals;
    write += literals;
    if (read === input.length) break;
    const distance = byte() | (byte() << 8);
    if (distance === 0 || distance > write)
      badBlock("LZ4 match has an invalid backward distance");
    const match = length(token & 15, expected - write - 4) + 4;
    let copied = Math.min(distance, match);
    output.copy(output, write, write - distance, write - distance + copied);
    // Grow the already decoded pattern; Buffer.copy alone has memmove rather than LZ4 overlap semantics.
    while (copied < match) {
      const count = Math.min(copied, match - copied);
      output.copy(output, write + copied, write, write + count);
      copied += count;
    }
    write += match;
  }
  if (write !== expected)
    badBlock("LZ4 decoded length disagrees with its declaration");
  abortIfNeeded(signal);
  return output;
};
