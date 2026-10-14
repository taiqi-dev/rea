import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { test } from "node:test";

const root = resolve(import.meta.dirname, "../..");
const git = process.env.REA_TEST_GIT ?? "git";

test("Windows helper preserves source and supports Desktop recursive pull", {
  skip: process.platform !== "win32",
  timeout: 120_000,
}, (t) => {
  // Keep failed fixtures under Git metadata for diagnosis; no network, engines,
  // original source repositories, or user worktrees are needed by this test.
  const metadata = spawnSync(git, ["rev-parse", "--path-format=absolute", "--git-path", "windows-submodule-tests"], {
    cwd: root, encoding: "utf8", windowsHide: true,
  });
  assert.equal(metadata.status, 0, metadata.stderr);
  mkdirSync(metadata.stdout.trim(), { recursive: true });
  const temporary = mkdtempSync(join(metadata.stdout.trim(), "run-"));
  t.diagnostic(`Fixture retained at ${temporary}`);
  const environment = {
    ...process.env,
    GIT_ALLOW_PROTOCOL: "file",
    GIT_TERMINAL_PROMPT: "0",
    GIT_AUTHOR_NAME: "REA Test",
    GIT_AUTHOR_EMAIL: "test@localhost",
    GIT_COMMITTER_NAME: "REA Test",
    GIT_COMMITTER_EMAIL: "test@localhost",
  };
  const run = (command, args, cwd, input) => {
    const result = spawnSync(command, args, {
      cwd, env: environment, input, encoding: "utf8", windowsHide: true,
      timeout: 30_000, maxBuffer: 1024 * 1024,
    });
    assert.equal(result.error, undefined, result.error?.message);
    return result;
  };
  const checkedGit = (cwd, ...args) => {
    const result = run(git, args, cwd);
    assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
    return result.stdout.trim();
  };
  const upstream = (name, paths) => {
    const directory = join(temporary, `${name}.git`);
    checkedGit(temporary, "init", "--bare", "--initial-branch=main", directory);
    const files = paths.map((path) => `M 100644 inline ${path}\ndata 8\nfixture\n\n`).join("");
    // Synthesize a Linux upstream tree in a bare object database only. The
    // per-command override is never saved or used for a worktree checkout.
    const result = run(git, ["-c", "core.protectNTFS=false", "fast-import", "--quiet"], directory,
      `commit refs/heads/main\ncommitter REA Test <test@localhost> 1700000000 +0000\ndata 7\nfixture\n${files}\ndone\n`);
    assert.equal(result.status, 0, result.stderr);
    return { directory, revision: checkedGit(directory, "rev-parse", "HEAD") };
  };
  const engines = {
    unblob: upstream("unblob", [
      "python/unblob/__init__.py", "tests/test_cli.py", "tests/handlers/test_handler.py",
      '"tests/integration/bad\\001name.txt"',
    ]),
    wakaru: upstream("wakaru", ["README.md"]),
  };
  const checkout = join(temporary, "checkout");
  checkedGit(temporary, "init", "--initial-branch=main", checkout);
  mkdirSync(join(checkout, "scripts"));
  copyFileSync(join(root, "scripts/init-windows-submodules.ps1"), join(checkout, "scripts/init-windows-submodules.ps1"));
  for (const [name, engine] of Object.entries(engines)) {
    const path = `third_party/${name}`;
    checkedGit(checkout, "config", "--file", ".gitmodules", `submodule.${path}.path`, path);
    checkedGit(checkout, "config", "--file", ".gitmodules", `submodule.${path}.url`, engine.directory.replaceAll("\\", "/"));
    checkedGit(checkout, "update-index", "--add", "--cacheinfo", `160000,${engine.revision},${path}`);
  }
  checkedGit(checkout, "add", ".gitmodules", "scripts/init-windows-submodules.ps1");
  checkedGit(checkout, "commit", "--quiet", "-m", "test: initial checkout");
  // Match a clone made with --recurse-submodules. The named false setting must
  // take precedence over this broad active pathspec.
  checkedGit(checkout, "config", "submodule.active", ".");
  const helper = () => run("pwsh", ["-NoProfile", "-File", "scripts/init-windows-submodules.ps1"], checkout);
  const initialize = () => {
    const result = helper();
    assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
  };
  initialize();
  for (const [name, engine] of Object.entries(engines)) {
    assert.equal(checkedGit(join(checkout, "third_party", name), "rev-parse", "HEAD"), engine.revision);
  }
  assert.ok(existsSync(join(checkout, "third_party/unblob/python/unblob/__init__.py")));
  assert.ok(existsSync(join(checkout, "third_party/unblob/tests/test_cli.py")));
  assert.equal(existsSync(join(checkout, "third_party/unblob/tests/integration")), false);
  const beforePull = checkedGit(checkout, "rev-parse", "HEAD");
  const remote = join(temporary, "remote.git");
  checkedGit(temporary, "clone", "--quiet", "--bare", checkout, remote);
  checkedGit(checkout, "remote", "add", "origin", remote);
  writeFileSync(join(checkout, "new-document.md"), "A documentation-only update.\n");
  checkedGit(checkout, "add", "new-document.md");
  checkedGit(checkout, "commit", "--quiet", "-m", "test: document update");
  const afterPull = checkedGit(checkout, "rev-parse", "HEAD");
  checkedGit(checkout, "push", "--quiet", "origin", "HEAD:refs/heads/main");
  checkedGit(checkout, "switch", "--quiet", "--no-recurse-submodules", "--detach", beforePull);
  checkedGit(checkout, "config", "submodule.third_party/unblob.active", "true");
  const pullArgs = ["-c", "rebase.backend=merge", "pull", "--ff", "--recurse-submodules", "--progress", "origin", "main"];
  const baseline = run(git, pullArgs, checkout);
  assert.notEqual(baseline.status, 0);
  assert.match(baseline.stderr, /invalid path[\s\S]*Failed to recurse into submodule path 'third_party\/unblob'/);
  checkedGit(checkout, "switch", "--quiet", "--no-recurse-submodules", "--detach", beforePull);
  initialize();
  const repaired = run(git, pullArgs, checkout);
  assert.equal(repaired.status, 0, `${repaired.stdout}\n${repaired.stderr}`);
  assert.equal(checkedGit(checkout, "rev-parse", "HEAD"), afterPull);
  initialize();
  assert.equal(checkedGit(checkout, "status", "--porcelain"), "");
  const readme = join(checkout, "third_party/wakaru/README.md");
  const original = readFileSync(readme);
  writeFileSync(readme, "Local edit to preserve.\n");
  assert.notEqual(helper().status, 0);
  assert.equal(readFileSync(readme, "utf8"), "Local edit to preserve.\n");
  writeFileSync(readme, original);
  const unblob = join(checkout, "third_party/unblob");
  const exclude = checkedGit(unblob, "rev-parse", "--path-format=absolute", "--git-path", "info/exclude");
  writeFileSync(exclude, "/tests/integration/\n");
  const ignoredDirectory = join(unblob, "tests/integration");
  mkdirSync(ignoredDirectory, { recursive: true });
  const ignoredFile = join(ignoredDirectory, "keep.txt");
  writeFileSync(ignoredFile, "Ignored content to preserve.\n");
  assert.notEqual(helper().status, 0);
  assert.equal(readFileSync(ignoredFile, "utf8"), "Ignored content to preserve.\n");
});
