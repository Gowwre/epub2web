export const GITHUB_URL = "https://github.com/Gowwre/epub2web";
export const RELEASES_URL = `${GITHUB_URL}/releases`;
export const LATEST_RELEASE_URL = `${GITHUB_URL}/releases/latest`;
export const ISSUES_URL = `${GITHUB_URL}/issues/new`;
export const LICENSE_URL = `${GITHUB_URL}/blob/main/LICENSE`;
export const CONTRIBUTING_URL = `${GITHUB_URL}/blob/main/CONTRIBUTING.md`;
export const CHANGELOG_URL = `${GITHUB_URL}/blob/main/CHANGELOG.md`;
export const README_URL = `${GITHUB_URL}/blob/main/README.md`;
export const FIRST_LAUNCH_URL = `${README_URL}#first-launch-security-warnings-are-expected`;
export const GUI_DOCS_URL = `${GITHUB_URL}/blob/main/docs/gui.md`;
export const DEMO_URL = "https://gowwre.github.io/epub2web/demo/";

const basePath = import.meta.env.BASE_URL.replace(/\/$/, "");

/**
 * Prefix a root-relative site path with Astro's configured base path.
 * Astro handles bundled assets itself; this is for routes and public files.
 */
export function withBase(path: string): string {
  if (!path.startsWith("/")) return path;
  return `${basePath}${path}`;
}

export const SITE_DESCRIPTION =
  "Turn the EPUB you own into a clean, static reading website. Every word, figure, note, and link checked. No account, no upload, no AI.";

export const NAV_LINKS = [
  { label: "Fidelity", href: "/#fidelity" },
  { label: "The edition", href: "/#edition" },
  { label: "How it works", href: "/#how-it-works" },
  { label: "FAQ", href: "/#faq" },
] as const;
