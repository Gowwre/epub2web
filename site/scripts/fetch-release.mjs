#!/usr/bin/env node
/**
 * Resolve the latest GitHub release to direct asset download URLs.
 *
 * The Pages workflow runs this before building so the download page always
 * offers the current installers. For local updates, run:
 *
 *   npm run update-release
 */
import { mkdir, writeFile } from "node:fs/promises";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const repo = process.env.RELEASE_REPO ?? "Gowwre/epub2web";
const token = process.env.GITHUB_TOKEN ?? process.env.GH_TOKEN;
const target = fileURLToPath(new URL("../src/data/latest-release.json", import.meta.url));

const platformPatterns = {
  windows: /^epub2web-gui-.*-windows-x64\.exe$/i,
  macosArm64: /^epub2web-gui-.*-macos-arm64\.dmg$/i,
  macosX64: /^epub2web-gui-.*-macos-x64\.dmg$/i,
  linux: /^epub2web-gui-.*-linux-x86_64\.AppImage$/i,
};

function fail(message) {
  console.error(`error: ${message}`);
  process.exit(1);
}

let response;
try {
  response = await fetch(`https://api.github.com/repos/${repo}/releases/latest`, {
    headers: {
      Accept: "application/vnd.github+json",
      "User-Agent": "epub2web-site-build",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
} catch (error) {
  fail(`could not reach the GitHub API: ${error instanceof Error ? error.message : error}`);
}

if (!response.ok) {
  fail(`GitHub API returned ${response.status} ${response.statusText} for ${repo}`);
}

const release = await response.json();
const assets = Array.isArray(release.assets) ? release.assets : [];

function pickAsset(pattern, label) {
  const asset = assets.find((candidate) => pattern.test(candidate.name));
  if (!asset) {
    fail(`latest release ${release.tag_name} has no ${label} asset`);
  }
  return {
    filename: asset.name,
    size: asset.size,
    url:
      asset.browser_download_url ??
      `https://github.com/${repo}/releases/download/${release.tag_name}/${encodeURIComponent(asset.name)}`,
  };
}

const downloads = Object.fromEntries(
  Object.entries(platformPatterns).map(([key, pattern]) => [key, pickAsset(pattern, key)]),
);

const checksums = pickAsset(/^SHA256SUMS\.txt$/i, "checksums");
const version = String(release.tag_name).replace(/^v/, "");

const data = {
  tagName: release.tag_name,
  version,
  name: release.name,
  publishedAt: release.published_at,
  releaseUrl: release.html_url,
  checksums,
  downloads,
};

await mkdir(dirname(target), { recursive: true });
await writeFile(target, `${JSON.stringify(data, null, 2)}\n`);

console.log(
  `Resolved epub2web ${version}: ${Object.values(downloads)
    .map((asset) => `${asset.filename} (${asset.size} bytes)`)
    .join(", ")}`,
);
