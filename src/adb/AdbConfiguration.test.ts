import { describe, expect, it } from "vitest";

import {
  ADB_BINARY_ENV,
  parseAdbVersionOutput,
  resolveAdbBinary,
} from "./AdbConfiguration.js";

describe("resolveAdbBinary", () => {
  it("prefers an absolute REA_ADB_PATH", async () => {
    expect(
      await resolveAdbBinary({ [ADB_BINARY_ENV]: "/opt/tools/adb" }, "linux"),
    ).toEqual({
      binary: "/opt/tools/adb",
      pathSource: "environment",
    });
  });

  it("falls back to PATH resolution without the environment key on POSIX", async () => {
    expect(await resolveAdbBinary({}, "linux")).toEqual({
      binary: "adb",
      pathSource: "path",
    });
    expect(await resolveAdbBinary({ [ADB_BINARY_ENV]: "  " }, "linux")).toEqual(
      {
        binary: "adb",
        pathSource: "path",
      },
    );
  });

  it("rejects a relative environment path explicitly", async () => {
    await expect(
      resolveAdbBinary({ [ADB_BINARY_ENV]: "tools/adb" }),
    ).rejects.toThrow(/must be an absolute path/u);
  });

  it("refuses a missing default Windows executable before spawn", async () => {
    await expect(resolveAdbBinary({ Path: "" }, "win32")).rejects.toMatchObject(
      {
        code: "binary_missing",
      },
    );
  });
});

describe("parseAdbVersionOutput", () => {
  it("reads the build version and install path from real output", () => {
    expect(
      parseAdbVersionOutput(
        [
          "Android Debug Bridge version 1.0.41",
          "Version 34.0.5-debian",
          "Installed as /usr/lib/android-sdk/platform-tools/adb",
          "",
        ].join("\n"),
      ),
    ).toEqual({
      version: "34.0.5-debian",
      installedPath: "/usr/lib/android-sdk/platform-tools/adb",
    });
  });

  it("reports null identity fields when the named lines are absent", () => {
    expect(parseAdbVersionOutput("unexpected output")).toEqual({
      version: null,
      installedPath: null,
    });
  });
});
