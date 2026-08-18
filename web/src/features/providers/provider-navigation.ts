import type { ProviderCapability } from "@/features/providers/providers.types";

const CONSOLE_ORIGIN = "https://console.eylo.invalid";

function providerCollectionPath(
  organizationId: string,
  capability: ProviderCapability,
): string {
  return `/org/${organizationId}/providers/${capability}`;
}

function providerCreatePath(
  organizationId: string,
  capability: ProviderCapability,
  returnTo?: string,
): string {
  return withReturnContext(
    `${providerCollectionPath(organizationId, capability)}/new`,
    returnTo,
  );
}

function withReturnContext(path: string, returnTo?: string): string {
  if (returnTo === undefined) {
    return path;
  }
  const params = new URLSearchParams({ returnTo });
  return `${path}?${params.toString()}`;
}

function safeOrganizationReturnPath(
  value: string | null,
  organizationId: string | undefined,
): string | null {
  if (
    value === null ||
    organizationId === undefined ||
    !value.startsWith("/") ||
    value.startsWith("//")
  ) {
    return null;
  }
  try {
    const parsed = new URL(value, CONSOLE_ORIGIN);
    if (
      parsed.origin !== CONSOLE_ORIGIN ||
      !parsed.pathname.startsWith(`/org/${organizationId}/`)
    ) {
      return null;
    }
    return `${parsed.pathname}${parsed.search}${parsed.hash}`;
  } catch {
    return null;
  }
}

function preserveReturnContext(
  target: URLSearchParams,
  source: URLSearchParams,
  organizationId: string,
): URLSearchParams {
  const returnTo = safeOrganizationReturnPath(
    source.get("returnTo"),
    organizationId,
  );
  if (returnTo !== null) {
    target.set("returnTo", returnTo);
  }
  return target;
}

export {
  preserveReturnContext,
  providerCollectionPath,
  providerCreatePath,
  safeOrganizationReturnPath,
  withReturnContext,
};
