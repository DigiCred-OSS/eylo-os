import rootReadme from "../../../../README.md?raw";

type DocumentationSectionId =
  "start" | "tutorials" | "how-to" | "reference" | "explanation" | "diagrams";

interface DocumentationSection {
  id: DocumentationSectionId;
  label: string;
}

interface DocumentationHeading {
  depth: 2 | 3;
  id: string;
  line: number;
  text: string;
}

interface DocumentationPage {
  body: string;
  headings: readonly DocumentationHeading[];
  label: string;
  searchText: string;
  sectionId: DocumentationSectionId;
  slug: string;
  sourcePath: string;
  summary: string;
  title: string;
}

interface DocumentationSearchResult {
  page: DocumentationPage;
  score: number;
}

interface ResolvedDocumentationLink {
  href: string;
  openInNewTab: boolean;
}

const DOCUMENTATION_SECTIONS: readonly DocumentationSection[] = [
  {
    id: "start",
    label: "Start",
  },
  {
    id: "tutorials",
    label: "Learn",
  },
  {
    id: "how-to",
    label: "How-to",
  },
  {
    id: "reference",
    label: "Reference",
  },
  {
    id: "explanation",
    label: "Understand",
  },
  {
    id: "diagrams",
    label: "Architecture and data flows",
  },
] as const;

const NAVIGATION_LABELS: Readonly<Record<string, string>> = {
  "README.md": "Platform overview",
  "docs/README.md": "Documentation home",
  "docs/explanation/README.md": "Explanation overview",
  "docs/how-to/README.md": "How-to overview",
  "docs/reference/README.md": "Reference overview",
};

const rawDocumentationFiles = import.meta.glob<string>(
  "../../../../docs/**/*.md",
  {
    eager: true,
    import: "default",
    query: "?raw",
  },
);

const sourceEntries: readonly [string, string][] = [
  ["README.md", rootReadme],
  ...Object.entries(rawDocumentationFiles).map(
    ([importPath, source]): [string, string] => [
      canonicalDocumentationPath(importPath),
      source,
    ],
  ),
];
const NAVIGATION_ORDER_BY_SOURCE = buildNavigationOrder(sourceEntries);

const DOCUMENTATION_PAGES = sourceEntries
  .map(([sourcePath, source]) => createDocumentationPage(sourcePath, source))
  .sort(compareDocumentationPages);

const DOCUMENTATION_BY_SLUG = new Map(
  DOCUMENTATION_PAGES.map((page) => [page.slug, page]),
);
const DOCUMENTATION_BY_SOURCE = new Map(
  DOCUMENTATION_PAGES.map((page) => [page.sourcePath, page]),
);

function canonicalDocumentationPath(importPath: string): string {
  const docsOffset = importPath.lastIndexOf("/docs/");
  if (docsOffset === -1) {
    throw new Error(`Documentation import is outside docs/: ${importPath}`);
  }
  return importPath.slice(docsOffset + 1);
}

function createDocumentationPage(
  sourcePath: string,
  source: string,
): DocumentationPage {
  const normalizedSource = source.replaceAll("\r\n", "\n");
  const lines = normalizedSource.split("\n");
  const titleIndex = lines.findIndex((line) => /^#\s+\S/.test(line));
  const fallbackTitle = titleFromFilename(sourcePath);
  const titleLine = titleIndex === -1 ? null : (lines[titleIndex] ?? null);
  const title =
    titleLine === null
      ? fallbackTitle
      : cleanInlineMarkdown(titleLine.replace(/^#\s+/, ""));
  const bodyLines = [...lines];

  if (titleIndex !== -1) {
    bodyLines.splice(titleIndex, 1);
    if (bodyLines[titleIndex]?.trim() === "") {
      bodyLines.splice(titleIndex, 1);
    }
  }

  const body = bodyLines.join("\n").trim();
  const headings = extractHeadings(body);
  const sectionId = sectionForSource(sourcePath);
  const summary = extractSummary(body);

  return {
    body,
    headings,
    label: NAVIGATION_LABELS[sourcePath] ?? title,
    searchText: `${title}\n${summary}\n${body}`.toLocaleLowerCase(),
    sectionId,
    slug: slugForSource(sourcePath),
    sourcePath,
    summary,
    title,
  };
}

function titleFromFilename(sourcePath: string): string {
  const filename = sourcePath.split("/").at(-1)?.replace(/\.md$/, "") ?? "Page";
  return filename
    .split("-")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function sectionForSource(sourcePath: string): DocumentationSectionId {
  if (sourcePath === "README.md" || sourcePath === "docs/README.md") {
    return "start";
  }
  const section = sourcePath.split("/")[1];
  if (
    section === "tutorials" ||
    section === "how-to" ||
    section === "reference" ||
    section === "explanation" ||
    section === "diagrams"
  ) {
    return section;
  }
  return "start";
}

function slugForSource(sourcePath: string): string {
  if (sourcePath === "README.md") {
    return "platform-overview";
  }
  if (sourcePath === "docs/README.md") {
    return "";
  }

  return sourcePath
    .replace(/^docs\//, "")
    .replace(/\/README\.md$/, "")
    .replace(/\.md$/, "");
}

function extractHeadings(body: string): readonly DocumentationHeading[] {
  const headings: DocumentationHeading[] = [];
  const occurrences = new Map<string, number>();
  let fenceMarker: "```" | "~~~" | null = null;

  body.split("\n").forEach((line, index) => {
    const trimmed = line.trimStart();
    if (trimmed.startsWith("```") || trimmed.startsWith("~~~")) {
      const marker = trimmed.slice(0, 3) as "```" | "~~~";
      fenceMarker =
        fenceMarker === null
          ? marker
          : fenceMarker === marker
            ? null
            : fenceMarker;
      return;
    }
    if (fenceMarker !== null) {
      return;
    }

    const match = /^(##|###)\s+(.+?)\s*#*\s*$/.exec(line);
    if (match === null) {
      return;
    }

    const depthMarker = match[1] ?? "";
    const text = cleanInlineMarkdown(match[2] ?? "");
    const baseId = slugify(text) || `section-${index + 1}`;
    const occurrence = occurrences.get(baseId) ?? 0;
    occurrences.set(baseId, occurrence + 1);
    headings.push({
      depth: depthMarker.length as 2 | 3,
      id: occurrence === 0 ? baseId : `${baseId}-${occurrence + 1}`,
      line: index + 1,
      text,
    });
  });

  return headings;
}

function extractSummary(body: string): string {
  const paragraphs = body.split(/\n\s*\n/);
  const paragraph = paragraphs.find((candidate) => {
    const value = candidate.trim();
    return (
      value.length > 0 && !/^(?:#|[-*+]\s|\d+\.\s|>|\||```|~~~)/.test(value)
    );
  });

  if (paragraph === undefined) {
    return "Open this page for the current platform contract.";
  }

  return cleanInlineMarkdown(paragraph.replaceAll("\n", " "));
}

function cleanInlineMarkdown(value: string): string {
  return value
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/[`*_~]/g, "")
    .replace(/<[^>]+>/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function slugify(value: string): string {
  return value
    .toLocaleLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function compareDocumentationPages(
  left: DocumentationPage,
  right: DocumentationPage,
): number {
  const sectionOrder = new Map(
    DOCUMENTATION_SECTIONS.map((section, index) => [section.id, index]),
  );
  const sectionComparison =
    (sectionOrder.get(left.sectionId) ?? 0) -
    (sectionOrder.get(right.sectionId) ?? 0);
  if (sectionComparison !== 0) {
    return sectionComparison;
  }

  const leftOrder =
    NAVIGATION_ORDER_BY_SOURCE.get(left.sourcePath) ?? Number.MAX_SAFE_INTEGER;
  const rightOrder =
    NAVIGATION_ORDER_BY_SOURCE.get(right.sourcePath) ?? Number.MAX_SAFE_INTEGER;
  if (leftOrder !== rightOrder) {
    return leftOrder - rightOrder;
  }
  return left.label.localeCompare(right.label);
}

function buildNavigationOrder(
  entries: readonly [string, string][],
): ReadonlyMap<string, number> {
  const order = new Map<string, number>([
    ["docs/README.md", 0],
    ["README.md", 1],
  ]);
  const sectionIndexes = entries.filter(([sourcePath]) =>
    /^docs\/(?:how-to|reference|explanation)\/README\.md$/.test(sourcePath),
  );

  for (const [indexPath, source] of sectionIndexes) {
    order.set(indexPath, 0);
    const directory = indexPath.split("/").slice(0, -1);
    let position = 1;
    for (const match of source.matchAll(/\]\(([^)#?]+\.md)(?:#[^)]*)?\)/g)) {
      const relativeTarget = match[1];
      if (relativeTarget === undefined) {
        continue;
      }
      const targetPath = normalizeRelativePath([
        ...directory,
        ...relativeTarget.split("/"),
      ]);
      if (!order.has(targetPath)) {
        order.set(targetPath, position);
        position += 1;
      }
    }
  }

  return order;
}

function pagesForSection(
  sectionId: DocumentationSectionId,
): readonly DocumentationPage[] {
  return DOCUMENTATION_PAGES.filter((page) => page.sectionId === sectionId);
}

function pageForSlug(slug: string | undefined): DocumentationPage | null {
  return DOCUMENTATION_BY_SLUG.get(slug ?? "") ?? null;
}

function documentationPath(organizationId: string, slug: string): string {
  const base = `/org/${organizationId}/documentation`;
  return slug === "" ? base : `${base}/${slug}`;
}

function searchDocumentation(
  query: string,
): readonly DocumentationSearchResult[] {
  const tokens = query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  if (tokens.length === 0) {
    return [];
  }

  return DOCUMENTATION_PAGES.flatMap((page) => {
    if (!tokens.every((token) => page.searchText.includes(token))) {
      return [];
    }

    const lowerTitle = page.title.toLocaleLowerCase();
    const lowerLabel = page.label.toLocaleLowerCase();
    const score = tokens.reduce((total, token) => {
      if (lowerTitle === token || lowerLabel === token) {
        return total + 100;
      }
      if (lowerTitle.startsWith(token) || lowerLabel.startsWith(token)) {
        return total + 50;
      }
      if (lowerTitle.includes(token) || lowerLabel.includes(token)) {
        return total + 25;
      }
      return total + 1;
    }, 0);
    return [{ page, score }];
  }).sort(
    (left, right) =>
      right.score - left.score ||
      compareDocumentationPages(left.page, right.page),
  );
}

function resolveDocumentationLink(
  currentSourcePath: string,
  href: string,
  organizationId: string,
): ResolvedDocumentationLink {
  if (href.startsWith("#")) {
    return { href, openInNewTab: false };
  }
  if (/^[a-z][a-z\d+.-]*:/i.test(href) || href.startsWith("//")) {
    return {
      href,
      openInNewTab: /^https?:/i.test(href) || href.startsWith("//"),
    };
  }
  if (href.startsWith("/")) {
    return {
      href,
      openInNewTab: href === "/docs" || href.startsWith("/docs#"),
    };
  }

  const hashOffset = href.indexOf("#");
  const targetPath = hashOffset === -1 ? href : href.slice(0, hashOffset);
  const hash = hashOffset === -1 ? "" : href.slice(hashOffset);
  const sourceDirectory = currentSourcePath.split("/").slice(0, -1);
  const resolvedSource = normalizeRelativePath([
    ...sourceDirectory,
    ...targetPath.split("/"),
  ]);
  const targetPage = DOCUMENTATION_BY_SOURCE.get(resolvedSource);

  if (targetPage === undefined) {
    return { href, openInNewTab: false };
  }
  return {
    href: `${documentationPath(organizationId, targetPage.slug)}${hash}`,
    openInNewTab: false,
  };
}

function normalizeRelativePath(parts: readonly string[]): string {
  const normalized: string[] = [];
  for (const part of parts) {
    if (part === "" || part === ".") {
      continue;
    }
    if (part === "..") {
      normalized.pop();
      continue;
    }
    normalized.push(part);
  }
  return normalized.join("/");
}

export {
  DOCUMENTATION_PAGES,
  DOCUMENTATION_SECTIONS,
  documentationPath,
  pageForSlug,
  pagesForSection,
  resolveDocumentationLink,
  searchDocumentation,
};
export type {
  DocumentationHeading,
  DocumentationPage,
  DocumentationSearchResult,
  DocumentationSection,
};
