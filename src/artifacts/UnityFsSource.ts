import { lstat } from "node:fs/promises";

import { OwnedFileHandle } from "../filesystem/OwnedFileHandle.js";
import {
  NonRegularFileReadError,
  openRegularFile,
  RegularFileAdmissionFailure,
  sameRegularFileState,
  type StableRegularFileDescriptor,
} from "../filesystem/RegularFile.js";
import { abortIfNeeded } from "./ArtifactHash.js";
import { ArtifactReaderFailure } from "./ArtifactReader.js";

/** An inventory can lend its admitted descriptor; extraction owns its own. */
export class UnityFsSource {
  #opening: Promise<StableRegularFileDescriptor> | undefined;
  #owner: OwnedFileHandle | undefined;

  constructor(
    readonly path: string,
    readonly admitted?: StableRegularFileDescriptor,
  ) {}

  async read(signal?: AbortSignal): Promise<StableRegularFileDescriptor> {
    abortIfNeeded(signal);
    const selection = this.admitted ?? (await (this.#opening ??= this.#open()));
    const [descriptor, named] = await Promise.all([
      selection.handle.stat(),
      lstat(this.path).catch((cause: unknown) => {
        if (
          cause instanceof Error &&
          "code" in cause &&
          (cause.code === "ENOENT" || cause.code === "ENOTDIR")
        )
          throw new ArtifactReaderFailure(
            "integrity",
            "UnityFS source disappeared",
            { cause },
          );
        throw cause;
      }),
    ]);
    abortIfNeeded(signal);
    if (
      !sameRegularFileState(selection.initial, descriptor) ||
      !sameRegularFileState(selection.initial, named)
    )
      throw new ArtifactReaderFailure(
        "integrity",
        "UnityFS source changed after admission",
      );
    return selection;
  }

  async #open(): Promise<StableRegularFileDescriptor> {
    try {
      const handle = await openRegularFile(this.path, { symlinks: "reject" });
      this.#owner = new OwnedFileHandle(handle);
      return { handle, initial: await handle.stat() };
    } catch (cause: unknown) {
      if (cause instanceof RegularFileAdmissionFailure) {
        this.#owner = cause.owner;
        throw ArtifactReaderFailure.withCleanup(
          cause.cause,
          ArtifactReaderFailure.cleanupObservation(
            cause.cleanupCause,
            this.path,
          ),
        );
      }
      if (cause instanceof NonRegularFileReadError)
        throw new ArtifactReaderFailure(
          "format",
          "UnityFS source must be a regular file",
          { cause },
        );
      throw cause;
    }
  }

  async close(): Promise<void> {
    await this.#owner?.close();
    this.#owner = undefined;
  }
}
