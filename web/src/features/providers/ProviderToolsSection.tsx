import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { ProviderTool } from "@/features/providers/providers.types";

interface ProviderToolsSectionProps {
  errorMessage: string | null;
  isLoading: boolean;
  isStale: boolean;
  onRetry: () => void;
  tools: ProviderTool[];
}

function ProviderToolsSection({
  errorMessage,
  isLoading,
  isStale,
  onRetry,
  tools,
}: ProviderToolsSectionProps) {
  if (isLoading && tools.length === 0) {
    return <ProviderToolsLoading />;
  }
  if (errorMessage !== null && tools.length === 0) {
    return (
      <section className="space-y-3" aria-labelledby="provider-tools-title">
        <ProviderToolsHeading />
        <div className="border p-4" role="alert">
          <p className="text-sm font-medium">Agent tools are unavailable</p>
          <p className="mt-1 text-sm text-muted-foreground">{errorMessage}</p>
          <Button
            className="mt-3"
            size="sm"
            variant="outline"
            onClick={onRetry}
          >
            Try again
          </Button>
        </div>
      </section>
    );
  }
  if (tools.length === 0) {
    return null;
  }

  return (
    <section className="space-y-3" aria-labelledby="provider-tools-title">
      <ProviderToolsHeading />
      {isStale ? (
        <div
          className="border border-warning/40 bg-warning/10 p-3 text-sm"
          role="alert"
        >
          Showing the last loaded Agent tools. {errorMessage}
        </div>
      ) : null}
      <div className="divide-y border">
        {tools.map((tool) => (
          <article
            className="flex min-w-0 flex-col gap-1 p-3 sm:flex-row sm:items-start sm:gap-6"
            key={tool.id}
          >
            <div className="min-w-0 sm:w-56 sm:shrink-0">
              <h3 className="text-sm font-medium">{tool.displayName}</h3>
              <code className="block break-all text-xs text-muted-foreground">
                {tool.name}
              </code>
            </div>
            <p className="min-w-0 break-words text-sm leading-5 text-muted-foreground">
              {summarizeDescription(tool.description)}
            </p>
          </article>
        ))}
      </div>
    </section>
  );
}

function ProviderToolsHeading() {
  return (
    <div className="space-y-1">
      <h2 id="provider-tools-title" className="text-base font-semibold">
        Agent tools
      </h2>
      <p className="max-w-3xl text-sm leading-5 text-muted-foreground">
        Configure this capability, then assign only the tools an Agent needs.
        Runtime requirements still apply.
      </p>
    </div>
  );
}

function ProviderToolsLoading() {
  return (
    <section className="space-y-3" aria-label="Loading Agent tools">
      <div className="space-y-2">
        <Skeleton className="h-5 w-28" />
        <Skeleton className="h-4 w-full max-w-lg" />
      </div>
      <div className="divide-y border">
        {Array.from({ length: 3 }, (_, index) => (
          <div
            className="flex flex-col gap-2 p-3 sm:flex-row sm:gap-6"
            key={index}
          >
            <Skeleton className="h-9 w-48" />
            <Skeleton className="h-9 min-w-0 flex-1" />
          </div>
        ))}
      </div>
    </section>
  );
}

function summarizeDescription(description: string): string {
  const firstParagraph = description.trim().split(/\n\s*\n/, 1)[0] ?? "";
  return firstParagraph.replace(/\s+/g, " ");
}

export { ProviderToolsSection };
