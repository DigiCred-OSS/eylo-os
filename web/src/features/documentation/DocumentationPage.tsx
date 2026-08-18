import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  ExternalLink,
  Menu,
  Search,
  X,
} from "lucide-react";
import { useEffect, useId, useMemo, useState } from "react";
import { Link, useLocation, useParams, useSearchParams } from "react-router";

import { Button } from "@/components/ui/button";
import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
  DrawerTrigger,
} from "@/components/ui/drawer";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { DocumentationArticle } from "@/features/documentation/DocumentationArticle";
import {
  DOCUMENTATION_PAGES,
  DOCUMENTATION_SECTIONS,
  documentationPath,
  pageForSlug,
  pagesForSection,
  searchDocumentation,
  type DocumentationPage as DocumentationPageRecord,
} from "@/features/documentation/documentation-content";
import { cn } from "@/lib/utils";

function DocumentationPage() {
  const params = useParams();
  const organizationId = params.organizationId;
  const slug = (params["*"] ?? "").replace(/\/+$/, "");
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const [isNavigationOpen, setNavigationOpen] = useState(false);
  const query = searchParams.get("q") ?? "";
  const page = pageForSlug(slug);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      if (location.hash === "") {
        window.scrollTo({ top: 0, behavior: "auto" });
        return;
      }
      document.getElementById(hashTargetId(location.hash))?.scrollIntoView();
    });
    return () => window.cancelAnimationFrame(frame);
  }, [location.hash, slug]);

  if (organizationId === undefined) {
    return null;
  }

  function updateQuery(value: string): void {
    const next = new URLSearchParams(searchParams);
    if (value.trim() === "") {
      next.delete("q");
    } else {
      next.set("q", value);
    }
    setSearchParams(next, { replace: true });
  }

  const navigation = (
    <DocumentationNavigation
      currentSlug={page?.slug ?? null}
      onNavigate={() => setNavigationOpen(false)}
      onQueryChange={updateQuery}
      organizationId={organizationId}
      query={query}
    />
  );

  return (
    <section className="min-w-0 p-4 sm:p-6" aria-label="Documentation">
      <header className="flex items-start justify-between gap-4 border-b pb-5">
        <div className="min-w-0">
          <p className="text-xs font-medium text-muted-foreground">Resources</p>
          <p className="mt-1 text-xl font-semibold tracking-tight">
            Documentation library
          </p>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">
            Current guides, contracts, architecture, and data flows from this
            console build.
          </p>
        </div>

        <Drawer
          open={isNavigationOpen}
          swipeDirection="left"
          onOpenChange={setNavigationOpen}
        >
          <DrawerTrigger
            render={
              <Button className="lg:hidden" variant="outline" size="sm" />
            }
          >
            <Menu aria-hidden="true" />
            Browse docs
          </DrawerTrigger>
          <DrawerContent>
            <DrawerHeader className="border-b pb-4 text-left">
              <DrawerTitle>Documentation</DrawerTitle>
              <DrawerDescription>
                Search or choose a page. Your current page remains open behind
                this drawer.
              </DrawerDescription>
            </DrawerHeader>
            <div className="min-h-0 flex-1 overflow-y-auto p-4">
              {navigation}
            </div>
          </DrawerContent>
        </Drawer>
      </header>

      <div className="mt-6 grid min-w-0 gap-8 lg:grid-cols-[15rem_minmax(0,1fr)] 2xl:grid-cols-[15rem_minmax(0,1fr)_13rem]">
        <aside className="hidden min-w-0 lg:block">
          <div className="sticky top-20 max-h-[calc(100svh-6rem)] overflow-y-auto pr-2">
            {navigation}
          </div>
        </aside>

        <div className="min-w-0 2xl:px-4">
          <div className="mx-auto min-w-0 max-w-4xl">
            {page === null ? (
              <DocumentationNotFound organizationId={organizationId} />
            ) : (
              <>
                <DocumentationArticle
                  organizationId={organizationId}
                  page={page}
                />
                <DocumentationTraversal
                  organizationId={organizationId}
                  page={page}
                />
              </>
            )}
          </div>
        </div>

        {page !== null && page.headings.length > 0 ? (
          <aside className="hidden min-w-0 2xl:block">
            <DocumentationTableOfContents page={page} />
          </aside>
        ) : null}
      </div>
    </section>
  );
}

interface DocumentationNavigationProps {
  currentSlug: string | null;
  onNavigate: () => void;
  onQueryChange: (value: string) => void;
  organizationId: string;
  query: string;
}

function DocumentationNavigation({
  currentSlug,
  onNavigate,
  onQueryChange,
  organizationId,
  query,
}: DocumentationNavigationProps) {
  const results = useMemo(() => searchDocumentation(query), [query]);
  const searchId = useId();
  const resultsId = `${searchId}-results`;
  const hasQuery = query.trim() !== "";

  return (
    <div className="min-w-0">
      <div className="relative">
        <label className="sr-only" htmlFor={searchId}>
          Search documentation
        </label>
        <Search
          className="pointer-events-none absolute top-2.5 left-3 size-4 text-muted-foreground"
          aria-hidden="true"
        />
        <Input
          id={searchId}
          className="pr-9 pl-9"
          placeholder="Search docs"
          type="search"
          value={query}
          onChange={(event) => onQueryChange(event.currentTarget.value)}
        />
        {hasQuery ? (
          <Button
            className="absolute top-0.5 right-0.5"
            size="icon-sm"
            type="button"
            variant="ghost"
            aria-label="Clear documentation search"
            title="Clear search"
            onClick={() => onQueryChange("")}
          >
            <X aria-hidden="true" />
          </Button>
        ) : null}
      </div>

      {hasQuery ? (
        <DocumentationSearchResults
          organizationId={organizationId}
          query={query}
          resultsId={resultsId}
          results={results}
          onNavigate={onNavigate}
        />
      ) : (
        <nav className="mt-6 space-y-6" aria-label="Documentation pages">
          {DOCUMENTATION_SECTIONS.map((section) => {
            const pages = pagesForSection(section.id);
            return (
              <section
                key={section.id}
                aria-labelledby={`${searchId}-${section.id}`}
              >
                <h2
                  id={`${searchId}-${section.id}`}
                  className="mb-1 px-2 text-xs font-medium text-muted-foreground"
                >
                  {section.label}
                </h2>
                <ul className="space-y-0.5">
                  {pages.map((page) => (
                    <li key={page.sourcePath}>
                      <Link
                        aria-current={
                          currentSlug === page.slug ? "page" : undefined
                        }
                        className={cn(
                          "block rounded-md px-2 py-1.5 text-sm leading-5 transition-colors focus-visible:outline-2",
                          currentSlug === page.slug
                            ? "bg-muted font-medium text-foreground"
                            : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
                        )}
                        to={documentationPath(organizationId, page.slug)}
                        onClick={onNavigate}
                      >
                        {page.label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </section>
            );
          })}

          <Separator />
          <a
            className="flex items-center justify-between gap-2 rounded-md px-2 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground focus-visible:outline-2"
            href="/docs"
            rel="noreferrer"
            target="_blank"
          >
            <span>Live API reference</span>
            <ExternalLink className="size-3.5 shrink-0" aria-hidden="true" />
          </a>
        </nav>
      )}
    </div>
  );
}

function DocumentationSearchResults({
  onNavigate,
  organizationId,
  query,
  resultsId,
  results,
}: {
  onNavigate: () => void;
  organizationId: string;
  query: string;
  resultsId: string;
  results: ReturnType<typeof searchDocumentation>;
}) {
  return (
    <section className="mt-5" aria-labelledby={resultsId}>
      <h2 id={resultsId} className="text-xs font-medium text-muted-foreground">
        Search results
      </h2>
      <p className="mt-1 text-xs text-muted-foreground" aria-live="polite">
        {results.length === 0
          ? `No pages match “${query}”.`
          : `${results.length} ${results.length === 1 ? "page" : "pages"}`}
      </p>

      {results.length > 0 ? (
        <ul className="mt-3 space-y-1">
          {results.map(({ page }) => (
            <li key={page.sourcePath}>
              <Link
                className="block rounded-md px-2 py-2 transition-colors hover:bg-muted/60 focus-visible:outline-2"
                to={documentationPath(organizationId, page.slug)}
                onClick={onNavigate}
              >
                <span className="block text-sm font-medium leading-5">
                  {page.title}
                </span>
                <span className="mt-1 line-clamp-2 block text-xs leading-5 text-muted-foreground">
                  {page.summary}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <div className="mt-4 border bg-muted/30 p-4 text-sm leading-6 text-muted-foreground">
          Try a module, provider, event, or runtime term.
        </div>
      )}
    </section>
  );
}

function DocumentationTableOfContents({
  page,
}: {
  page: DocumentationPageRecord;
}) {
  return (
    <nav
      className="sticky top-20 max-h-[calc(100svh-6rem)] overflow-y-auto"
      aria-label="On this page"
    >
      <p className="text-xs font-medium text-muted-foreground">On this page</p>
      <ul className="mt-2 space-y-1">
        {page.headings.map((heading) => (
          <li key={`${heading.line}-${heading.id}`}>
            <a
              className={cn(
                "block py-1 text-xs leading-5 text-muted-foreground hover:text-foreground focus-visible:rounded-sm focus-visible:outline-2",
                heading.depth === 3 && "pl-3",
              )}
              href={`#${heading.id}`}
            >
              {heading.text}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}

function DocumentationTraversal({
  organizationId,
  page,
}: {
  organizationId: string;
  page: DocumentationPageRecord;
}) {
  const pageIndex = DOCUMENTATION_PAGES.findIndex(
    (candidate) => candidate.slug === page.slug,
  );
  const previousPage = DOCUMENTATION_PAGES[pageIndex - 1] ?? null;
  const nextPage = DOCUMENTATION_PAGES[pageIndex + 1] ?? null;

  return (
    <nav
      className="mt-12 grid gap-3 border-t pt-6 sm:grid-cols-2"
      aria-label="Adjacent documentation pages"
    >
      {previousPage === null ? (
        <span />
      ) : (
        <DocumentationTraversalLink
          direction="previous"
          organizationId={organizationId}
          page={previousPage}
        />
      )}
      {nextPage === null ? null : (
        <DocumentationTraversalLink
          direction="next"
          organizationId={organizationId}
          page={nextPage}
        />
      )}
    </nav>
  );
}

function DocumentationTraversalLink({
  direction,
  organizationId,
  page,
}: {
  direction: "next" | "previous";
  organizationId: string;
  page: DocumentationPageRecord;
}) {
  const isNext = direction === "next";
  return (
    <Link
      className={cn(
        "group flex min-w-0 items-center gap-3 border p-3 transition-colors hover:bg-muted/50 focus-visible:outline-2",
        isNext && "justify-end text-right",
      )}
      to={documentationPath(organizationId, page.slug)}
    >
      {!isNext ? (
        <ArrowLeft className="size-4 shrink-0" aria-hidden="true" />
      ) : null}
      <span className="min-w-0">
        <span className="block text-xs text-muted-foreground">
          {isNext ? "Next" : "Previous"}
        </span>
        <span className="mt-0.5 block truncate text-sm font-medium">
          {page.title}
        </span>
      </span>
      {isNext ? (
        <ArrowRight className="size-4 shrink-0" aria-hidden="true" />
      ) : null}
    </Link>
  );
}

function DocumentationNotFound({ organizationId }: { organizationId: string }) {
  return (
    <article
      className="border bg-muted/20 p-6"
      aria-labelledby="docs-not-found-title"
    >
      <BookOpen className="size-5" aria-hidden="true" />
      <h1 id="docs-not-found-title" className="mt-4 text-2xl font-semibold">
        Documentation page not found
      </h1>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">
        This link does not match a page included in the current console build.
      </p>
      <Link
        className="mt-5 inline-flex h-9 items-center rounded-md border px-3 text-sm font-medium hover:bg-muted focus-visible:outline-2"
        to={documentationPath(organizationId, "")}
      >
        Open documentation home
      </Link>
    </article>
  );
}

function hashTargetId(hash: string): string {
  const value = hash.slice(1);
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

export { DocumentationPage };
