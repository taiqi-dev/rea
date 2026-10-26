import { expect, it } from "vitest";
import { providerRegistrationEnvironment } from "./SetupRegistrationEnvironment.js";

it("preserves explicitly selected Ghidra deadlines without copying ambient environment or defaults", () => {
  expect(
    providerRegistrationEnvironment([], {
      REA_GHIDRA_STARTUP_TIMEOUT_MS: "900000",
      REA_GHIDRA_DECOMPILE_TIMEOUT_SECONDS: "60",
      UNRELATED_VALUE: "keep out of registration",
    }),
  ).toEqual({
    REA_GHIDRA_STARTUP_TIMEOUT_MS: "900000",
    REA_GHIDRA_DECOMPILE_TIMEOUT_SECONDS: "60",
  });
  expect(providerRegistrationEnvironment([])).toEqual({});
});
