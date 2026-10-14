import { spawnSync } from "node:child_process";

const python = process.platform === "win32" ? "python" : "python3";
for (const arguments_ of [
  ["-m", "unittest", "bridge/native/test_rea_lldb_tracer.py", "-v"],
  [
    "-m",
    "unittest",
    "discover",
    "-s",
    "experiments/analysis-efficiency",
    "-p",
    "test_*.py",
    "-v",
  ],
]) {
  const result = spawnSync(python, arguments_, {
    stdio: "inherit",
    windowsHide: true,
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    process.exitCode = result.status ?? 1;
    break;
  }
}
