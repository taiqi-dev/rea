import { z } from "zod";
import { il2cppMetadataSummaryViewResultSchema } from "../../domain/analysisView/analysisView.js";
import {
  il2cppMetadataSchema,
  inspectIl2cppMetadataInputSchema,
} from "../../domain/il2cpp/il2cppMetadata.js";
import type { ToolContract } from "../toolContractTypes.js";
import { toolContractMetadata } from "../toolEffects.js";
import { evidenceResultOf } from "../toolOutputSchemaPrimitives.js";

/** Static IL2CPP metadata is independent of native-analysis providers and Unity installations. */
export const IL2CPP_TOOL_CONTRACTS = [
  {
    name: "inspect_il2cpp_metadata",
    ...toolContractMetadata("inspect_il2cpp_metadata"),
    kind: "artifact-provider",
    description:
      "Inspect a local Unity IL2CPP global-metadata.dat (versions 24, 27, 29, 31 and 39). Default summary retains complete Evidence and returns artifact identity, version and counts and parent_evidence_id. Query inspect_analysis_view kind il2cpp-metadata, collection sections/images/types/methods/fields/properties/events/parameters/string_literals, with exact indices or names, fields and pagination. Types also accept image_indices, namespaces and declaring_types; methods, fields, properties and events accept declaring_types. Parameters accept method_indices. Filters intersect and empty arrays select none. Each row always keeps index, scoped to its artifact SHA-256 and collection; page offsets count matching rows in metadata order. Explicit detail complete returns all rows. Reads existing files, with 256 MiB input and 64 MiB encoded-report guards and one active inspection per reader. Unsupported versions and malformed metadata return reasons. Type declaring_type is derived from nestedTypes, and member and parameter owners from index ranges; Without binary_path native addresses remain unknown. Optional binary_path selects a Windows x64 PE GameAssembly.dll for static module-name/count/token linking, preferred virtual addresses and RVAs, code/no-body/unknown states, and field/parameter/return types. No target execution or implicit DLL selection. Native rows use collections method_addresses/return_types/field_types/parameter_types/code_gen_modules in retained views. Structural agreement does not prove both files came from the same build; runtime addresses and generic method instances remain unknown. Binary input is bounded to 1 GiB. Open the same binary separately for native analysis only after matching its SHA-256.",
    inputSchema: inspectIl2cppMetadataInputSchema,
    outputSchema: evidenceResultOf(
      z.union([il2cppMetadataSchema, il2cppMetadataSummaryViewResultSchema]),
    ),
    examples: [
      {
        title: "Associate a caller-selected Windows GameAssembly.dll",
        input: {
          path: "C:/build/Data/il2cpp_data/Metadata/global-metadata.dat",
          binary_path: "C:/build/GameAssembly.dll",
          detail: "summary",
        },
      },
      {
        title: "Summarize metadata and retain rows for paging",
        input: {
          path: "/artifacts/Data/Managed/Metadata/global-metadata.dat",
          detail: "summary",
        },
      },
    ],
  },
] as const satisfies readonly ToolContract[];
