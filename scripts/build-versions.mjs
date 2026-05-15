#!/usr/bin/env node
/**
 * Build the Docusaurus site with per-tag versioned docs derived from git history.
 *
 * Strategy:
 *   1. List git tags matching the project release pattern (e.g. "5.1.0").
 *   2. Keep only the tags whose tree already contains a Docusaurus-style
 *      docs/ tree and sidebars.ts (i.e. tags cut after docs migration).
 *   3. For each eligible tag (newest -> oldest):
 *        a. Copy docs/ + sidebars.ts from that tag into the working tree.
 *        b. Run `docusaurus docs:version <tag>` to snapshot it.
 *        c. Restore HEAD docs/ + sidebars.ts.
 *   4. Set DOCS_LAST_VERSION env var to the newest tag and invoke `npm run build`.
 *
 * versioned_docs/, versioned_sidebars/, and versions.json are NOT committed to
 * the repo (see .gitignore). They are regenerated on every build.
 */

import { execSync } from "node:child_process";
import { existsSync, mkdtempSync, rmSync, cpSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const log = (msg) => console.log(`[build-versions] ${msg}`);

function sh(cmd, opts = {}) {
  return execSync(cmd, { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"], ...opts });
}

function tagHasDocusaurusDocs(tag) {
  try {
    execSync(`git cat-file -e ${tag}:sidebars.ts`, { stdio: "ignore" });
    execSync(`git cat-file -e ${tag}:docs/intro.md`, { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

function listTags() {
  const out = sh("git tag --sort=-version:refname").trim();
  if (!out) return [];
  return out
    .split("\n")
    .map((t) => t.trim())
    .filter((t) => /^\d+\.\d+\.\d+$/.test(t));
}

function snapshotTag(tag) {
  log(`Snapshotting ${tag}`);
  const work = mkdtempSync(join(tmpdir(), `docs-${tag}-`));
  try {
    // Extract docs/ and sidebars.ts from the tag into a temp dir.
    sh(`git archive ${tag} docs sidebars.ts | tar -x -C ${work}`, {
      shell: "/bin/bash",
    });
    // Swap into the working tree, then snapshot, then restore HEAD.
    rmSync("docs", { recursive: true, force: true });
    cpSync(join(work, "docs"), "docs", { recursive: true });
    cpSync(join(work, "sidebars.ts"), "sidebars.ts");
    execSync(`npx --no-install docusaurus docs:version ${tag}`, {
      stdio: "inherit",
    });
  } finally {
    rmSync(work, { recursive: true, force: true });
    // Restore HEAD versions of docs/ and sidebars.ts.
    execSync("git checkout HEAD -- docs sidebars.ts", { stdio: "ignore" });
  }
}

function main() {
  // Refuse to run if working tree has uncommitted changes to docs or sidebars,
  // because we temporarily overwrite them during snapshots.
  const dirty = sh("git status --porcelain -- docs sidebars.ts").trim();
  if (dirty && !process.env.FORCE_BUILD_VERSIONS) {
    console.error(
      "[build-versions] docs/ or sidebars.ts has uncommitted changes; refusing to run.\n" +
        "Commit / stash them first, or set FORCE_BUILD_VERSIONS=1 to override.",
    );
    process.exit(1);
  }

  const tags = listTags();
  const eligible = tags.filter(tagHasDocusaurusDocs);

  log(
    eligible.length
      ? `Found ${eligible.length} eligible tag(s): ${eligible.join(", ")}`
      : "No eligible release tags found; building HEAD as 'Current' only.",
  );

  for (const tag of eligible) {
    snapshotTag(tag);
  }

  const lastVersion = eligible[0] || "";
  log(`DOCS_LAST_VERSION=${lastVersion || "(unset, HEAD only)"}`);

  execSync("npm run build", {
    stdio: "inherit",
    env: { ...process.env, DOCS_LAST_VERSION: lastVersion },
  });
}

main();
