import { ArrowRight, Cable } from "lucide-react";
import { observer } from "mobx-react-lite";
import { useEffect } from "react";
import { useNavigate, useParams } from "react-router";

import { useRootStore } from "@/app/use-root-store";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ProviderStatusBadge } from "@/features/providers/ProviderStatusBadge";
import type { ProviderCapability } from "@/features/providers/providers.types";

const ProvidersPage = observer(function ProvidersPage() {
  const { providers } = useRootStore();
  const { organizationId } = useParams();
  const navigate = useNavigate();

  useEffect(() => {
    void providers.loadOverview();
  }, [providers]);

  if (organizationId === undefined) {
    return null;
  }

  function openCapability(capability: ProviderCapability): void {
    void navigate(`/org/${organizationId}/providers/${capability}`);
  }

  const isFirstUse =
    providers.capabilities !== null &&
    Object.values(providers.capabilities).every((status) => !status.configured);

  return (
    <section className="space-y-6 p-4 sm:p-6" aria-labelledby="providers-title">
      <header className="space-y-1">
        <h1
          id="providers-title"
          className="text-2xl font-semibold tracking-tight"
        >
          Providers
        </h1>
        <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
          Connect the external capabilities your Agents use. Eylo configures
          nothing until you choose and verify a provider.
        </p>
      </header>

      {isFirstUse ? (
        <div className="flex gap-3 border bg-muted/30 p-4" role="status">
          <Cable className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
          <div>
            <p className="text-sm font-medium">No providers configured yet</p>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">
              Choose the capability your Agent needs first. Saving stores the
              configuration; verification is a separate provider check.
            </p>
          </div>
        </div>
      ) : null}

      {providers.isOverviewStale ? (
        <div
          className="border border-warning/40 bg-warning/10 p-3 text-sm"
          role="alert"
        >
          Showing the last loaded provider state.{" "}
          {providers.overviewErrorMessage}
        </div>
      ) : null}

      {providers.overviewErrorMessage !== null && providers.catalog === null ? (
        <div className="border py-16 text-center" role="alert">
          <p className="text-sm font-medium">Providers are unavailable</p>
          <p className="mt-1 text-sm text-muted-foreground">
            {providers.overviewErrorMessage}
          </p>
          <Button
            className="mt-4"
            variant="outline"
            onClick={() => void providers.loadOverview()}
          >
            Try again
          </Button>
        </div>
      ) : (
        <div className="border">
          <div
            className="divide-y sm:hidden"
            role="list"
            aria-label="Provider capabilities"
          >
            {providers.catalog === null
              ? Array.from({ length: 8 }, (_, index) => (
                  <CapabilityLoadingCard key={index} />
                ))
              : providers.catalog.capabilities.map((definition) => {
                  const status = providers.statusFor(definition.capability);
                  return (
                    <div
                      className="space-y-3 p-4"
                      key={definition.capability}
                      role="listitem"
                    >
                      <div className="flex items-start gap-3">
                        <button
                          className="min-w-0 flex-1 text-left focus-visible:rounded-sm focus-visible:outline-2"
                          type="button"
                          onClick={() => openCapability(definition.capability)}
                        >
                          <span className="block font-medium">
                            {definition.label}
                          </span>
                          <span className="mt-1 block text-xs leading-5 text-muted-foreground">
                            {definition.description}
                          </span>
                        </button>
                        <Button
                          className="shrink-0"
                          variant="ghost"
                          size="icon"
                          aria-label={`Open ${definition.label}`}
                          title={`Open ${definition.label}`}
                          onClick={() => openCapability(definition.capability)}
                        >
                          <ArrowRight aria-hidden="true" />
                        </Button>
                      </div>
                      {status === null ? (
                        <p className="text-xs text-muted-foreground">
                          Readiness unavailable
                        </p>
                      ) : (
                        <ProviderStatusBadge
                          configured={status.configured}
                          ready={status.ready}
                          verified={status.verified}
                        />
                      )}
                    </div>
                  );
                })}
          </div>

          <Table className="hidden sm:table" aria-label="Provider capabilities">
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>Capability</TableHead>
                <TableHead className="hidden lg:table-cell">
                  Configured providers
                </TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="w-12 text-right">
                  <span className="sr-only">Actions</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {providers.catalog === null
                ? Array.from({ length: 8 }, (_, index) => (
                    <CapabilityLoadingRow key={index} />
                  ))
                : providers.catalog.capabilities.map((definition) => {
                    const status = providers.statusFor(definition.capability);
                    return (
                      <TableRow key={definition.capability}>
                        <TableCell className="max-w-lg whitespace-normal">
                          <button
                            className="text-left font-medium underline-offset-4 hover:underline focus-visible:rounded-sm focus-visible:outline-2"
                            type="button"
                            onClick={() =>
                              openCapability(definition.capability)
                            }
                          >
                            {definition.label}
                          </button>
                          <p className="mt-1 text-xs leading-5 text-muted-foreground">
                            {definition.description}
                          </p>
                        </TableCell>
                        <TableCell className="hidden text-muted-foreground lg:table-cell">
                          {status === null
                            ? "Unavailable"
                            : status.providers.length === 0
                              ? "None"
                              : status.providers.join(", ")}
                        </TableCell>
                        <TableCell>
                          {status === null ? (
                            <span className="text-xs text-muted-foreground">
                              Readiness unavailable
                            </span>
                          ) : (
                            <ProviderStatusBadge
                              configured={status.configured}
                              ready={status.ready}
                              verified={status.verified}
                            />
                          )}
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            variant="ghost"
                            size="icon"
                            aria-label={`Open ${definition.label}`}
                            title={`Open ${definition.label}`}
                            onClick={() =>
                              openCapability(definition.capability)
                            }
                          >
                            <ArrowRight aria-hidden="true" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    );
                  })}
            </TableBody>
          </Table>
        </div>
      )}
    </section>
  );
});

function CapabilityLoadingRow() {
  return (
    <TableRow>
      <TableCell>
        <Skeleton className="h-5 w-36" />
        <Skeleton className="mt-2 h-3 w-64 max-w-full" />
      </TableCell>
      <TableCell className="hidden lg:table-cell">
        <Skeleton className="h-4 w-24" />
      </TableCell>
      <TableCell>
        <Skeleton className="h-6 w-48" />
      </TableCell>
      <TableCell>
        <Skeleton className="ml-auto size-8" />
      </TableCell>
    </TableRow>
  );
}

function CapabilityLoadingCard() {
  return (
    <div className="space-y-3 p-4" role="listitem">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <Skeleton className="h-5 w-36 max-w-full" />
          <Skeleton className="mt-2 h-3 w-64 max-w-full" />
        </div>
        <Skeleton className="size-8 shrink-0" />
      </div>
      <Skeleton className="h-6 w-48 max-w-full" />
    </div>
  );
}

export { ProvidersPage };
