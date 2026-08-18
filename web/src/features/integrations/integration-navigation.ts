const CONSOLE_ORIGIN = "https://console.eylo.invalid";

function configuredIntegrationsPath(organizationId: string): string {
  return `/org/${organizationId}/integrations/configured`;
}

function integrationConnectionsPath(organizationId: string): string {
  return `/org/${organizationId}/integrations/connections`;
}

function integrationVendorPath(
  organizationId: string,
  vendor: string,
  returnTo?: string,
): string {
  const path = `/org/${organizationId}/integrations/${vendor}`;
  return returnTo === undefined
    ? path
    : `${path}?${new URLSearchParams({ returnTo }).toString()}`;
}

function safeIntegrationReturnPath(
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
    const integrationRoot = `/org/${organizationId}/integrations`;
    if (
      parsed.origin !== CONSOLE_ORIGIN ||
      (parsed.pathname !== integrationRoot &&
        !parsed.pathname.startsWith(`${integrationRoot}/`))
    ) {
      return null;
    }
    return `${parsed.pathname}${parsed.search}${parsed.hash}`;
  } catch {
    return null;
  }
}

export {
  configuredIntegrationsPath,
  integrationConnectionsPath,
  integrationVendorPath,
  safeIntegrationReturnPath,
};
