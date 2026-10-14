/** Minimal OS prerequisites for launching real fixture processes, without
 * inheriting the developer's HOME, PATH, credentials, or application settings. */
export const testProcessEnvironment = (): NodeJS.ProcessEnv => {
  if (process.platform !== "win32") return {};
  const systemRoot = process.env.SystemRoot ?? process.env.SYSTEMROOT;
  if (!systemRoot)
    throw new Error("Windows fixture processes require SystemRoot.");
  return { SYSTEMROOT: systemRoot };
};
