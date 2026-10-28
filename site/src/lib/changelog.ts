import { marked } from "marked";

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
}

const releaseHeading = /^(\d+\.\d+\.\d+)\s*[—–-]\s*(\d{4}-\d{2}-\d{2})\s*$/;

const dateFormatter = new Intl.DateTimeFormat("en", {
  dateStyle: "long",
  timeZone: "UTC",
});

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
 * Parse released sections from the repository changelog. The `Unreleased`
 * section is intentionally left to the repository copy.
 */
export async function parseChangelog(markdown: string): Promise<ChangelogRelease[]> {
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
      dateLabel: dateFormatter.format(new Date(`${date}T00:00:00Z`)),
      heading,
      githubAnchor: githubHeadingId(heading),
      sections,
    });
  }

  if (releases.length === 0) {
    throw new Error("No released versions found in CHANGELOG.md");
  }

  return releases;
}
