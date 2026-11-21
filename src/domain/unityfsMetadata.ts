import { z } from "zod";

const uint32 = z.int().min(0).max(0xffff_ffff);
const offset = z.int().nonnegative();

export const unityFsMetadataSchema = z.strictObject({
  kind: z.literal("unityfs"),
  signature: z.literal("UnityFS"),
  format_version: uint32,
  player_version: z.string(),
  engine_version: z.string(),
  declared_size: offset,
  flags: uint32,
  blocks_info_compressed_size: uint32,
  blocks_info_uncompressed_size: uint32,
  blocks_info_at_end: z.boolean(),
  data_start: offset.nullable(),
  block_count: uint32.nullable(),
  data_hash: z
    .string()
    .regex(/^[0-9a-f]{32}$/u)
    .nullable(),
  directory_status: z.enum([
    "available",
    "encrypted",
    "unsupported-compression",
    "unsupported-layout",
  ]),
});

export const unityFsEntryMetadataSchema = z.strictObject({
  kind: z.literal("unityfs-entry"),
  index: uint32,
  source_path: z.string(),
  declared_offset: offset,
  flags: uint32,
});

export type UnityFsMetadata = z.infer<typeof unityFsMetadataSchema>;
export type UnityFsEntryMetadata = z.infer<typeof unityFsEntryMetadataSchema>;
