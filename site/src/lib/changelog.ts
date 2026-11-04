import { marked } from "marked";
import type { Locale } from "../i18n/config";

export interface ChangelogSection {
  title: string | null;
  html: string;
}

export interface ChangelogRelease {
  version: string;
  date: string;
  dateLabel: string;
  heading: string;
  githubAnchor: string;
  sections: ChangelogSection[];
  translated: boolean;
}

const releaseHeading = /^(\d+\.\d+\.\d+)\s*[—–-]\s*(\d{4}-\d{2}-\d{2})\s*$/;

const dateFormatters: Record<Locale, Intl.DateTimeFormat> = {
  en: new Intl.DateTimeFormat("en-US", {
    dateStyle: "long",
    timeZone: "UTC",
  }),
  vi: new Intl.DateTimeFormat("vi-VN", {
    dateStyle: "long",
    timeZone: "UTC",
  }),
};

/**
 * GitHub's markdown heading anchors: strip punctuation, keep hyphens and
 * underscores, and replace each remaining space with a hyphen.
 */
function githubHeadingId(heading: string): string {
  return heading
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s_-]/gu, "")
    .trim()
    .replace(/ /g, "-");
}

function splitSections(body: string): { title: string | null; markdown: string }[] {
  const parts = body.split(/^### /m);
  const sections: { title: string | null; markdown: string }[] = [];
  const preamble = parts.shift()?.trim();

  if (preamble) {
    sections.push({ title: null, markdown: preamble });
  }

  for (const part of parts) {
    const newline = part.indexOf("\n");
    const title = (newline === -1 ? part : part.slice(0, newline)).trim();
    const markdown = newline === -1 ? "" : part.slice(newline + 1).trim();
    if (markdown) {
      sections.push({ title, markdown });
    }
  }

  return sections;
}

/**
 * Parse released sections from a changelog file. The `Unreleased` section is
 * intentionally left to the repository copy.
 */
export async function parseChangelog(
  markdown: string,
  locale: Locale = "en",
  translated = false,
): Promise<ChangelogRelease[]> {
  const releases: ChangelogRelease[] = [];
  const chunks = markdown.split(/^##\s+/m).slice(1);

  for (const chunk of chunks) {
    const lines = chunk.split(/\r?\n/);
    const heading = lines.shift()?.trim() ?? "";
    const match = heading.match(releaseHeading);

    if (!match) {
      continue;
    }

    const [, version, date] = match;
    const body = lines.join("\n").trim();
    const sections = await Promise.all(
      splitSections(body).map(async ({ title, markdown: sectionMarkdown }) => ({
        title,
        html: await marked.parse(sectionMarkdown),
      })),
    );

    releases.push({
      version,
      date,
      dateLabel: dateFormatters[locale].format(new Date(`${date}T00:00:00Z`)),
      heading,
      githubAnchor: githubHeadingId(heading),
      sections,
      translated,
    });
  }

  if (releases.length === 0) {
    throw new Error(`No released versions found in the ${locale} changelog`);
  }

  return releases;
}

/**
 * Use a translated release when it matches the canonical version and date.
 * Missing or stale translations fall back to the English release, one version
 * at a time, so a new release never blocks the localized site.
 */
export function mergeChangelog(
  english: ChangelogRelease[],
  localized: ChangelogRelease[],
): ChangelogRelease[] {
  const byVersion = new Map(localized.map((release) => [release.version, release]));

  return english.map((release) => {
    const translation = byVersion.get(release.version);
    if (translation && translation.date === release.date) {
      return { ...translation, translated: true };
    }
    return { ...release, translated: false };
  });
}
