import {
  AnalysisInputError,
  type AnalysisInputIssue,
} from "../analysisErrorCore.js";
import { INSPECT_ANALYSIS_VIEW_OPERATION } from "./analysisViewOperation.js";

/** Shared input failure independent of the schemas that consume it. */
export const analysisViewInputError = (
  issues: readonly AnalysisInputIssue[],
): AnalysisInputError =>
  new AnalysisInputError(INSPECT_ANALYSIS_VIEW_OPERATION, undefined, issues);
