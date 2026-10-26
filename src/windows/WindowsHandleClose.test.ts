import { execFile } from "node:child_process";
import { resolve } from "node:path";
import { promisify } from "node:util";
import { describe, expect, it } from "vitest";

const run = promisify(execFile);

describe.skipIf(process.platform !== "win32" || process.arch !== "x64")(
  "Windows native handle close gate",
  () => {
    it("passes the injected matrix and real protected-handle failures with MSVC", async () => {
      const root = resolve(import.meta.dirname, "../..");
      await run(
        process.execPath,
        ["scripts/build-windows-native.mjs", "--handle-close-test"],
        {
          cwd: root,
          windowsHide: true,
          timeout: 180_000,
        },
      );
      const result = await run(
        resolve(root, ".cache/windows-handle-close-test/handle-close-test.exe"),
        [],
        {
          cwd: root,
          windowsHide: true,
          timeout: 30_000,
        },
      );
      expect(result.stdout).toBe("");
      expect(result.stderr).toBe("");
    }, 210_000);
  },
);
