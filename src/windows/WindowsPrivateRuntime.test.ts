import { afterEach, describe, expect, it, vi } from "vitest";

const nativeCall = vi.hoisted(() => vi.fn());
vi.mock("./WindowsNativeLoader.js", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./WindowsNativeLoader.js")>()),
  requireWindowsNativeAuthority: () => ({ call: nativeCall }),
}));

import {
  WindowsPrivateRuntime,
  windowsPrivateRuntime,
} from "./WindowsPrivateRuntime.js";

const identity = {
  requestedPath: "C:\\rea-private",
  finalPath: "C:\\rea-private",
  filesystem: "NTFS",
  volumeSerial: "0123456789abcdef",
  fileId: "fedcba9876543210fedcba9876543210",
  size: 0,
  directory: true,
};
const observation = {
  ...identity,
  path: identity.finalPath,
  handle: {},
  privateDacl: true,
};
const active = new Set<WindowsPrivateRuntime>();
afterEach(async () => {
  nativeCall.mockReturnValue(null);
  for (const runtime of active) await runtime.close();
  active.clear();
  nativeCall.mockReset();
});

const createRuntime = (
  options: { readFailure?: Error; closeFailures?: number } = {},
) => {
  const file = { ...identity, directory: false, size: 2, handle: {} };
  const closeFailure = new Error("Close admitted file handle failed");
  let closeFailures = options.closeFailures ?? 0;
  nativeCall.mockImplementation((operation: string) => {
    if (operation === "runtime_create") return observation;
    if (operation === "runtime_open") return file;
    if (operation === "read") {
      if (options.readFailure !== undefined) throw options.readFailure;
      return Buffer.from("ok");
    }
    if (operation === "close" && closeFailures-- > 0) throw closeFailure;
    return null;
  });
  const runtime = WindowsPrivateRuntime.create("C:\\", "rea-");
  active.add(runtime);
  return { runtime, file, closeFailure };
};

describe("Windows admitted file close ownership", () => {
  it("retries the exact failed file before walking the runtime", async () => {
    const { runtime, file, closeFailure } = createRuntime({ closeFailures: 1 });
    expect(() => runtime.readFile("endpoint")).toThrow(closeFailure);
    await runtime.close();
    expect(nativeCall.mock.calls.map(([operation]) => operation)).toEqual([
      "runtime_create",
      "runtime_open",
      "read",
      "close",
      "close",
      "runtime_close",
    ]);
    expect(
      nativeCall.mock.calls
        .filter(([operation]) => operation === "close")
        .map(([, arguments_]) => arguments_),
    ).toEqual([[file.handle], [file.handle]]);
    expect(() => windowsPrivateRuntime(observation.path)).toThrow(
      "No native private runtime",
    );
  });

  it("keeps a failed close registered and blocks the tree walk until retry succeeds", async () => {
    const { runtime, closeFailure } = createRuntime({ closeFailures: 2 });
    expect(() => runtime.readFile("endpoint")).toThrow(closeFailure);
    await expect(runtime.close()).rejects.toBe(closeFailure);
    expect(windowsPrivateRuntime(observation.path)).toBe(runtime);
    expect(
      nativeCall.mock.calls.some(
        ([operation]) => operation === "runtime_close",
      ),
    ).toBe(false);
    await runtime.close();
    expect(nativeCall.mock.calls.at(-1)?.[0]).toBe("runtime_close");
  });

  it("preserves both the read failure and the close failure", async () => {
    const readFailure = new Error("Read admitted file failed");
    const { runtime, closeFailure } = createRuntime({
      readFailure,
      closeFailures: 1,
    });
    let failure: unknown;
    try {
      runtime.readFile("endpoint");
    } catch (cause: unknown) {
      failure = cause;
    }
    expect(failure).toBeInstanceOf(AggregateError);
    expect((failure as AggregateError).errors).toEqual([
      readFailure,
      closeFailure,
    ]);
    await runtime.close();
  });

  it("preserves a lone read failure after successful close", async () => {
    const readFailure = new Error("Read failed before close");
    const { runtime } = createRuntime({ readFailure });
    expect(() => runtime.readFile("endpoint")).toThrow(readFailure);
    await runtime.close();
    expect(
      nativeCall.mock.calls.filter(([operation]) => operation === "close"),
    ).toHaveLength(1);
  });
});
