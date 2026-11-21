import type {
  ArtifactInventoryCoverage,
  ArtifactInventoryResult,
  ArtifactNode,
  ArtifactOccurrence,
  IntegrityContradiction,
} from "./artifactGraph.js";

/** Immutable inventory produced by one complete artifact scan. */
export interface ArtifactInventorySnapshot {
  readonly coverage_status: ArtifactInventoryCoverage;
  readonly manifest: ArtifactInventoryResult["manifest"];
  readonly nodes: readonly ArtifactNode[];
  readonly occurrences: readonly ArtifactOccurrence[];
  readonly edges: ArtifactInventoryResult["edges"];
  readonly provenance: ReadonlyArray<
    ArtifactInventoryResult["provenance"][number]
  >;
  readonly integrity_contradictions: readonly IntegrityContradiction[];
  readonly limitations: readonly string[];
}
