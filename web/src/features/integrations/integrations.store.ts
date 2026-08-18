import { makeAutoObservable, runInAction } from "mobx";

import { IntegrationDraftStorage } from "@/features/integrations/integration-draft-storage";
import {
  IntegrationsService,
  IntegrationsServiceError,
} from "@/features/integrations/integrations.service";
import type {
  CuratedConnection,
  CuratedCredentialInput,
  CuratedExecutionMode,
  CuratedInstallation,
  CuratedInstalledTool,
  CuratedVendor,
  CuratedVendorDetail,
  IntegrationDraftContext,
  IntegrationInstallDraftValues,
} from "@/features/integrations/integrations.types";

const EMPTY_DRAFT: IntegrationInstallDraftValues = {
  authKind: "",
  instanceUrl: "",
  oauthClientId: "",
  oauthTenant: "",
};

class IntegrationsStore {
  actionErrorMessage: string | null = null;
  catalogErrorMessage: string | null = null;
  connectionsErrorMessage: string | null = null;
  connections: CuratedConnection[] = [];
  draftSavedAt: string | null = null;
  draftValues: IntegrationInstallDraftValues = { ...EMPTY_DRAFT };
  installations: CuratedInstallation[] = [];
  isActing = false;
  isCatalogLoading = false;
  isConnectionsLoading = false;
  isInstallationsLoading = false;
  isSelectedLoading = false;
  installationsErrorMessage: string | null = null;
  selectedErrorMessage: string | null = null;
  selectedTools: CuratedInstalledTool[] = [];
  selectedVendor: CuratedVendorDetail | null = null;
  vendors: CuratedVendor[] = [];

  private catalogRequestId = 0;
  private connectionsRequestId = 0;
  private draftContext: IntegrationDraftContext | null = null;
  private readonly draftStorage: IntegrationDraftStorage;
  private installationsRequestId = 0;
  private selectedRequestId = 0;
  private readonly service: IntegrationsService;

  constructor(
    service: IntegrationsService,
    draftStorage: IntegrationDraftStorage,
  ) {
    this.service = service;
    this.draftStorage = draftStorage;
    makeAutoObservable<
      this,
      | "catalogRequestId"
      | "connectionsRequestId"
      | "draftContext"
      | "draftStorage"
      | "installationsRequestId"
      | "selectedRequestId"
      | "service"
    >(
      this,
      {
        catalogRequestId: false,
        connectionsRequestId: false,
        draftContext: false,
        draftStorage: false,
        installationsRequestId: false,
        selectedRequestId: false,
        service: false,
      },
      { autoBind: true },
    );
  }

  get selectedInstallation(): CuratedInstallation | null {
    const vendor = this.selectedVendor?.vendor;
    return this.installations.find((item) => item.vendor === vendor) ?? null;
  }

  get selectedConnections(): CuratedConnection[] {
    const vendor = this.selectedVendor?.vendor;
    return this.connections.filter((item) => item.vendor === vendor);
  }

  async loadCatalog(organizationId: string): Promise<void> {
    const requestId = ++this.catalogRequestId;
    this.isCatalogLoading = true;
    this.catalogErrorMessage = null;
    const [vendors, installations, connections] = await Promise.allSettled([
      this.service.listVendors(organizationId),
      this.service.listInstallations(organizationId),
      this.service.listConnections(organizationId),
    ]);
    if (this.catalogRequestId !== requestId) return;
    runInAction(() => {
      if (vendors.status === "fulfilled") this.vendors = vendors.value;
      if (installations.status === "fulfilled") {
        this.installations = installations.value;
      }
      if (connections.status === "fulfilled")
        this.connections = connections.value;
      const rejected = [vendors, installations, connections].find(
        (result) => result.status === "rejected",
      );
      this.catalogErrorMessage =
        rejected?.status === "rejected"
          ? messageFor(
              rejected.reason,
              "Integration catalog could not be loaded.",
            )
          : null;
      this.isCatalogLoading = false;
    });
  }

  async loadInstallations(organizationId: string): Promise<void> {
    const requestId = ++this.installationsRequestId;
    this.isInstallationsLoading = true;
    this.installationsErrorMessage = null;
    try {
      const installations =
        await this.service.listInstallations(organizationId);
      if (this.installationsRequestId !== requestId) return;
      runInAction(() => {
        this.installations = installations;
      });
    } catch (error) {
      if (this.installationsRequestId === requestId) {
        runInAction(() => {
          this.installationsErrorMessage = messageFor(
            error,
            "Configured integrations could not be loaded.",
          );
        });
      }
    } finally {
      if (this.installationsRequestId === requestId) {
        runInAction(() => {
          this.isInstallationsLoading = false;
        });
      }
    }
  }

  async loadConnections(organizationId: string): Promise<void> {
    const requestId = ++this.connectionsRequestId;
    this.isConnectionsLoading = true;
    this.connectionsErrorMessage = null;
    try {
      const connections = await this.service.listConnections(organizationId);
      if (this.connectionsRequestId !== requestId) return;
      runInAction(() => {
        this.connections = connections;
      });
    } catch (error) {
      if (this.connectionsRequestId === requestId) {
        runInAction(() => {
          this.connectionsErrorMessage = messageFor(
            error,
            "Integration connections could not be loaded.",
          );
        });
      }
    } finally {
      if (this.connectionsRequestId === requestId) {
        runInAction(() => {
          this.isConnectionsLoading = false;
        });
      }
    }
  }

  async loadVendor(organizationId: string, vendor: string): Promise<void> {
    const requestId = ++this.selectedRequestId;
    this.isSelectedLoading = true;
    this.selectedErrorMessage = null;
    this.actionErrorMessage = null;
    try {
      const detail = await this.service.getVendor(organizationId, vendor);
      const tools = detail.installed
        ? await this.service.listTools(organizationId, vendor)
        : [];
      if (this.selectedRequestId !== requestId) return;
      runInAction(() => {
        this.selectedVendor = detail;
        this.selectedTools = tools;
      });
    } catch (error) {
      if (this.selectedRequestId === requestId) {
        runInAction(() => {
          this.selectedVendor = null;
          this.selectedTools = [];
          this.selectedErrorMessage = messageFor(
            error,
            "This integration could not be loaded.",
          );
        });
      }
    } finally {
      if (this.selectedRequestId === requestId) {
        runInAction(() => {
          this.isSelectedLoading = false;
        });
      }
    }
  }

  clearSelected(): void {
    this.selectedRequestId += 1;
    this.selectedVendor = null;
    this.selectedTools = [];
    this.selectedErrorMessage = null;
    this.actionErrorMessage = null;
    this.draftContext = null;
    this.draftValues = { ...EMPTY_DRAFT };
    this.draftSavedAt = null;
  }

  prepareDraft(
    context: IntegrationDraftContext,
    vendor: CuratedVendorDetail,
  ): void {
    const contextKey = draftContextKey(context);
    if (
      this.draftContext &&
      draftContextKey(this.draftContext) === contextKey
    ) {
      return;
    }
    this.draftContext = context;
    const stored = this.draftStorage.read(context);
    const supported = new Set(vendor.authKinds ?? []);
    const fallbackAuth = onlyAuthKind(vendor);
    this.draftValues = stored
      ? {
          ...stored.values,
          authKind:
            stored.values.authKind !== "" &&
            supported.has(stored.values.authKind)
              ? stored.values.authKind
              : fallbackAuth,
        }
      : { ...EMPTY_DRAFT, authKind: fallbackAuth };
    this.draftSavedAt = stored?.savedAt ?? null;
  }

  updateDraft(patch: Partial<IntegrationInstallDraftValues>): void {
    this.draftValues = { ...this.draftValues, ...patch };
    if (
      this.draftContext &&
      this.draftStorage.write(this.draftContext, this.draftValues)
    ) {
      this.draftSavedAt = new Date().toISOString();
    }
  }

  discardDraft(vendor: CuratedVendorDetail): void {
    if (this.draftContext) this.draftStorage.clear(this.draftContext);
    this.draftValues = {
      ...EMPTY_DRAFT,
      authKind: onlyAuthKind(vendor),
    };
    this.draftSavedAt = null;
  }

  async install(
    organizationId: string,
    oauthClientSecret: string,
  ): Promise<boolean> {
    const vendor = this.selectedVendor;
    if (!vendor || this.isActing) return false;
    return this.runAction(async () => {
      await this.service.install(
        organizationId,
        vendor.vendor,
        this.draftValues,
        oauthClientSecret,
      );
      if (this.draftContext) this.draftStorage.clear(this.draftContext);
      await this.refreshSelected(organizationId, vendor.vendor);
    });
  }

  async setExecutionMode(
    organizationId: string,
    tool: CuratedInstalledTool,
    executionMode: CuratedExecutionMode,
  ): Promise<boolean> {
    const vendor = this.selectedVendor;
    if (!vendor || this.isActing) return false;
    return this.runAction(async () => {
      const updated = await this.service.setExecutionMode(
        organizationId,
        vendor.vendor,
        tool.name,
        executionMode,
      );
      runInAction(() => {
        this.selectedTools = this.selectedTools.map((item) =>
          item.id === updated.id ? updated : item,
        );
      });
    });
  }

  async connect(
    organizationId: string,
    credentials: CuratedCredentialInput,
  ): Promise<boolean> {
    const vendor = this.selectedVendor;
    if (!vendor || this.isActing) return false;
    return this.runAction(async () => {
      await this.service.connect(organizationId, vendor.vendor, credentials);
      await this.refreshSelected(organizationId, vendor.vendor);
    });
  }

  async deleteConnection(
    organizationId: string,
    connectionId: string,
  ): Promise<boolean> {
    if (this.isActing) return false;
    return this.runAction(async () => {
      await this.service.deleteConnection(organizationId, connectionId);
      runInAction(() => {
        this.connections = this.connections.filter(
          (connection) => connection.id !== connectionId,
        );
      });
    });
  }

  async beginAuthorization(
    organizationId: string,
  ): Promise<{ authorizationUrl: string; callbackOrigin: string } | null> {
    const vendor = this.selectedVendor;
    if (!vendor || this.isActing) return null;
    this.isActing = true;
    this.actionErrorMessage = null;
    try {
      return await this.service.beginAuthorization(
        organizationId,
        vendor.vendor,
      );
    } catch (error) {
      runInAction(() => {
        this.actionErrorMessage = messageFor(
          error,
          "Authorization could not be started.",
        );
      });
      return null;
    } finally {
      runInAction(() => {
        this.isActing = false;
      });
    }
  }

  async refreshSelected(organizationId: string, vendor: string): Promise<void> {
    await Promise.all([
      this.loadCatalog(organizationId),
      this.loadVendor(organizationId, vendor),
    ]);
  }

  setActionError(message: string): void {
    this.actionErrorMessage = message;
  }

  clearActionError(): void {
    this.actionErrorMessage = null;
  }

  private async runAction(action: () => Promise<void>): Promise<boolean> {
    this.isActing = true;
    this.actionErrorMessage = null;
    try {
      await action();
      return true;
    } catch (error) {
      runInAction(() => {
        this.actionErrorMessage = messageFor(
          error,
          "The integration could not be changed. Review the values and try again.",
        );
      });
      return false;
    } finally {
      runInAction(() => {
        this.isActing = false;
      });
    }
  }
}

function messageFor(error: unknown, fallback: string): string {
  return error instanceof IntegrationsServiceError || error instanceof Error
    ? error.message
    : fallback;
}

function draftContextKey(context: IntegrationDraftContext): string {
  return `${context.memberKey}:${context.organizationId}:${context.vendor}`;
}

function onlyAuthKind(
  vendor: CuratedVendorDetail,
): IntegrationInstallDraftValues["authKind"] {
  const authKinds = vendor.authKinds ?? [];
  return authKinds.length === 1 && authKinds[0] !== undefined
    ? authKinds[0]
    : "";
}

export { IntegrationsStore };
