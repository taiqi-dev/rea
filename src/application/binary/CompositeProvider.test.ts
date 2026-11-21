import { expect, it, vi } from "vitest";
import type {
  AnalysisOperation,
  AnalysisProvider,
} from "../AnalysisProvider.js";
import type { BinaryTarget } from "../../domain/binaryTargetTypes.js";
import { ProviderCleanupError } from "../../domain/providerCleanupError.js";
import { err, ok } from "../../domain/result.js";
import { CompositeProvider } from "./CompositeProvider.js";

it("reports every child still owned, joins concurrent closes and retries only failed children", async () => {
  const providerWithClose = (
    id: string,
    operation: Exclude<AnalysisOperation, "health">,
    fails: boolean,
  ) => {
    const identity = { id, name: id, version: null };
    const rejected = new ProviderCleanupError(id, [`${id}-handle`], {});
    const close = vi.fn(async () => ok(null));
    if (fails)
      close.mockImplementationOnce(async () => {
        throw rejected;
      });
    const provider: AnalysisProvider = {
      identity: () => identity,
      capabilities: () => [
        {
          operation,
          provider: identity,
          available: true,
          reason: null,
          effects: {
            mutatesArtifact: false,
            launchesProcess: false,
            mayShowUi: false,
            mayAccessNetwork: false,
            mayWriteFilesystem: false,
            changesPermissions: false,
            requiresRoot: false,
          },
          limitations: [],
        },
      ],
      createClient: () => ({ execute: async () => err(rejected), close }),
    };
    return { provider, operation, close };
  };
  const children = [
    providerWithClose("a", "address_name", true),
    providerWithClose("b", "list_procedures", false),
    providerWithClose("c", "list_strings", true),
  ];
  const composite = new CompositeProvider(
    children.map(({ provider }) => provider),
  );
  const target = {
    path: "/fixture",
    sha256: "a".repeat(64),
    kind: "archive",
    format: "zip",
  } satisfies BinaryTarget;
  const client = composite.createClient(target);
  for (const { operation } of children) await client.execute(operation, {});
  const first = client.close();
  expect(client.close()).toBe(first);
  expect(await first).toMatchObject({
    ok: false,
    error: {
      cleanupResources: ["a-handle", "c-handle"],
      diagnostics: { failures: [{ provider_id: "a" }, { provider_id: "c" }] },
    },
  });
  expect(await client.close()).toEqual(ok(null));
  expect(children.map(({ close }) => close.mock.calls.length)).toEqual([
    2, 1, 2,
  ]);
});
