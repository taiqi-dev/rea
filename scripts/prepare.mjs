import { spawnSync } from "node:child_process";
import { access, copyFile, mkdir, realpath, writeFile } from "node:fs/promises";
import { randomUUID } from "node:crypto";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

// npm installation and the optional source helper share this configuration
// owner. No optional source repositories need to be cloned for normal use.
const configureWindowsCheckout = async () => {
  const git = (args, optional = false) => {
    const result = spawnSync("git", ["-C", root, ...args], {
      encoding: "utf8",
      windowsHide: true,
    });
    if (result.error) throw result.error;
    if (optional && result.status === 1) return undefined;
    if (result.status !== 0)
      throw new Error(`Windows Git setup failed: ${result.stderr}`);
    return result.stdout.trim();
  };
  const gitRoot = git(["rev-parse", "--show-toplevel"]);
  if ((await realpath(gitRoot)) !== (await realpath(root)))
    throw new Error("Windows Git setup requires the repository root");
  const settings = {};
  const policies = git(
    [
      "config",
      "--file",
      ".gitmodules",
      "--get-regexp",
      "^submodule\\..*\\.update$",
    ],
    true,
  );
  for (const line of policies?.split(/\r?\n/u) ?? []) {
    const match = /^(submodule\..+)\.update\s+none$/u.exec(line);
    if (match) {
      settings[`${match[1]}.active`] = "false";
      settings[`${match[1]}.update`] = "none";
    }
  }
  if (git(["config", "--local", "--get", "remote.origin.url"], true))
    settings["remote.pushDefault"] = "origin";
  const changes = Object.entries(settings).filter(
    ([key, value]) => git(["config", "--local", "--get", key], true) !== value,
  );
  const upstream = git(
    ["config", "--local", "--get", "remote.upstream.url"],
    true,
  );
  const removeOriginalRemote =
    upstream !== undefined &&
    /^(?:https:\/\/github\.com\/|git@github\.com:)morluto\/rea(?:\.git)?\/?$/iu.test(
      upstream,
    );
  if (changes.length === 0 && !removeOriginalRemote) return;
  const backup = git([
    "rev-parse",
    "--path-format=absolute",
    "--git-path",
    `windows-checkout-backups/${randomUUID()}`,
  ]);
  await mkdir(backup, { recursive: true });
  const config = git([
    "rev-parse",
    "--path-format=absolute",
    "--git-path",
    "config",
  ]);
  await copyFile(config, join(backup, "config"));
  if (removeOriginalRemote) {
    await writeFile(
      join(backup, "upstream-refs.txt"),
      git([
        "for-each-ref",
        "--format=%(refname) %(objectname)",
        "refs/remotes/upstream/",
      ]),
    );
    git(["remote", "remove", "upstream"]);
  }
  for (const [key, value] of changes) git(["config", "--local", key, value]);
  console.log(
    `Windows Git setup applied; previous settings saved at ${backup}`,
  );
};

const sourceHuskyIsAvailable = async () => {
  try {
    await access(join(root, "src"));
    await access(join(root, "node_modules", "husky", "index.js"));
    return true;
  } catch (cause) {
    if (
      typeof cause === "object" &&
      cause !== null &&
      "code" in cause &&
      cause.code === "ENOENT"
    )
      return false;
    throw cause;
  }
};

const checkoutOnly = process.argv[2] === "--windows-checkout-only";
if (process.argv.length > (checkoutOnly ? 3 : 2))
  throw new Error("Unknown prepare argument");
if (
  checkoutOnly ||
  (process.platform === "win32" && (await sourceHuskyIsAvailable()))
)
  await configureWindowsCheckout();
if (
  !checkoutOnly &&
  process.env.HUSKY !== "0" &&
  (await sourceHuskyIsAvailable())
) {
  const { default: installHusky } = await import("husky");
  const message = installHusky();
  if (message.length > 0) process.stdout.write(`${message}\n`);
}
