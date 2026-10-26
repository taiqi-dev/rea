import { resolve as absoluteCallerPath } from "node:path";
import { z } from "incur";
import { createIl2cppMetadataService } from "../composition/il2cpp.js";
import { CLI_COMMANDS } from "../cliCommandNames.js";
import { logCliCommand } from "../cliLogging.js";
import type { Logger } from "pino";
import type { CliInstance } from "./types.js";
import { withCommandCancellation } from "./commandCancellation.js";
import {
  analysisEvidenceDeliveryOptions,
  deliverCliAnalysisEvidence,
} from "./analysisEvidenceDelivery.js";

/** CLI and MCP share inspection; one-shot summaries preserve a complete Evidence file. */
export const registerIl2cppCommands = (
  cli: CliInstance,
  logger: Logger,
): void => {
  cli.command(CLI_COMMANDS.inspectIl2cppMetadata, {
    description:
      "Inventory IL2CPP global-metadata.dat names, owners and string literals",
    args: z.object({
      path: z
        .string()
        .describe("Local global-metadata.dat (version 24, 27, 29, 31 or 39)"),
    }),
    options: z.object({
      ...analysisEvidenceDeliveryOptions,
      binary_path: z
        .string()
        .optional()
        .describe(
          "Explicit matching Windows x64 GameAssembly.dll; static reading only",
        ),
    }),
    run: ({ args, options }) =>
      withCommandCancellation((signal) =>
        logCliCommand(logger, CLI_COMMANDS.inspectIl2cppMetadata, async () => {
          const service = createIl2cppMetadataService();
          return deliverCliAnalysisEvidence({
            run: () =>
              service.inspect(
                {
                  path: absoluteCallerPath(args.path),
                  detail: "complete",
                  ...(options.binary_path === undefined
                    ? {}
                    : { binary_path: absoluteCallerPath(options.binary_path) }),
                },
                { signal },
              ),
            service,
            providerId: "il2cpp-metadata",
            operation: "inspect_il2cpp_metadata",
            signal,
            detail: options.detail,
            evidenceOutput: options.evidence_output,
          });
        }),
      ),
  });
};
