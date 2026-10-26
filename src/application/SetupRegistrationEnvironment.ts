import type { DoctorProviderInspection } from "./Doctor.js";
import { compareUnicodeCodePoints } from "../domain/unicodeCodePointOrder.js";

/** Preserve adapter-published settings independently of runtime readiness. */
export const providerRegistrationEnvironment = (
  inspections: readonly DoctorProviderInspection[],
  environment: Readonly<Record<string, string | undefined>> = {},
): Readonly<Record<string, string>> =>
  Object.fromEntries(
    [
      ...inspections.flatMap(({ registrationEnvironment }) =>
        Object.entries(registrationEnvironment),
      ),
      ...[
        "REA_GHIDRA_STARTUP_TIMEOUT_MS",
        "REA_GHIDRA_DECOMPILE_TIMEOUT_SECONDS",
      ].flatMap((name) => {
        const selected = environment[name];
        return selected === undefined ? [] : [[name, selected] as const];
      }),
    ].sort(([left], [right]) => compareUnicodeCodePoints(left, right)),
  );
