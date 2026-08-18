import { makeAutoObservable, runInAction } from "mobx";

import { ProviderDraftStorage } from "@/features/providers/provider-draft-storage";
import { ProviderFormStore } from "@/features/providers/provider-form.store";
import {
  ProviderServiceError,
  ProvidersService,
} from "@/features/providers/providers.service";
import type {
  ProviderCapabilities,
  ProviderCapability,
  ProviderCapabilityDefinition,
  ProviderCapabilityStatus,
  ProviderCatalog,
  ProviderConfigRecord,
  ProviderConfigUpdateInput,
  ProviderTool,
} from "@/features/providers/providers.types";

const OVERVIEW_ERROR_MESSAGE =
  "Provider readiness could not be loaded. Check the API connection and try again.";
const COLLECTION_ERROR_MESSAGE =
  "Provider configurations could not be loaded. Check the API connection and try again.";
const DETAIL_ERROR_MESSAGE =
  "This provider configuration could not be loaded. It may no longer exist.";
const PROVIDER_TOOLS_ERROR_MESSAGE =
  "Agent tools for this provider could not be loaded. Try again.";
const ACTION_ERROR_MESSAGE =
  "The provider configuration could not be changed. Try again.";

type ProviderAction = "delete" | "disable" | "enable" | "verify";

class ProvidersStore {
  actionErrorMessage: string | null = null;
  activeCapability: ProviderCapability | null = null;
  capabilities: ProviderCapabilities | null = null;
  catalog: ProviderCatalog | null = null;
  collectionErrorMessage: string | null = null;
  hasLoadedCollection = false;
  isCollectionLoading = false;
  isOverviewLoading = false;
  isProviderToolsLoading = false;
  isSelectedLoading = false;
  items: ProviderConfigRecord[] = [];
  overviewErrorMessage: string | null = null;
  pendingAction: { action: ProviderAction; configId: string } | null = null;
  providerTools: ProviderTool[] = [];
  providerToolsErrorMessage: string | null = null;
  selectedConfig: ProviderConfigRecord | null = null;
  selectedErrorMessage: string | null = null;

  readonly form: ProviderFormStore;

  private collectionRequestId = 0;
  private overviewRequestId = 0;
  private providerToolsCapability: ProviderCapability | null = null;
  private providerToolsRequestId = 0;
  private selectedRequestId = 0;
  private readonly service: ProvidersService;

  constructor(service: ProvidersService, draftStorage: ProviderDraftStorage) {
    this.service = service;
    this.form = new ProviderFormStore(service, draftStorage);

    makeAutoObservable<
      this,
      | "collectionRequestId"
      | "overviewRequestId"
      | "providerToolsCapability"
      | "providerToolsRequestId"
      | "selectedRequestId"
      | "service"
    >(
      this,
      {
        collectionRequestId: false,
        form: false,
        overviewRequestId: false,
        providerToolsCapability: false,
        providerToolsRequestId: false,
        selectedRequestId: false,
        service: false,
      },
      { autoBind: true },
    );
  }

  get isCollectionStale(): boolean {
    return this.collectionErrorMessage !== null && this.items.length > 0;
  }

  get isOverviewStale(): boolean {
    return this.overviewErrorMessage !== null && this.catalog !== null;
  }

  get isProviderToolsStale(): boolean {
    return (
      this.providerToolsErrorMessage !== null && this.providerTools.length > 0
    );
  }

  definitionFor(
    capability: ProviderCapability,
  ): ProviderCapabilityDefinition | null {
    return (
      this.catalog?.capabilities.find(
        (definition) => definition.capability === capability,
      ) ?? null
    );
  }

  statusFor(capability: ProviderCapability): ProviderCapabilityStatus | null {
    return this.capabilities?.[capability] ?? null;
  }

  async loadOverview(): Promise<void> {
    const requestId = ++this.overviewRequestId;
    this.isOverviewLoading = true;
    this.overviewErrorMessage = null;

    const [catalog, capabilities] = await Promise.allSettled([
      this.service.loadCatalog(),
      this.service.loadCapabilities(),
    ]);
    if (this.overviewRequestId !== requestId) {
      return;
    }

    runInAction(() => {
      if (catalog.status === "fulfilled") {
        this.catalog = catalog.value;
      }
      if (capabilities.status === "fulfilled") {
        this.capabilities = capabilities.value;
      }
      this.overviewErrorMessage = firstRejectedMessage(
        [catalog, capabilities],
        OVERVIEW_ERROR_MESSAGE,
      );
      this.isOverviewLoading = false;
    });
  }

  async loadCapability(capability: ProviderCapability): Promise<void> {
    const requestId = ++this.collectionRequestId;
    const isSameCapability = this.activeCapability === capability;
    this.activeCapability = capability;
    this.collectionErrorMessage = null;
    this.hasLoadedCollection = false;
    this.isCollectionLoading = true;
    if (!isSameCapability) {
      this.items = [];
      this.clearSelected();
    }

    const [items, catalog, capabilities] = await Promise.allSettled([
      this.service.list(capability),
      this.catalog === null
        ? this.service.loadCatalog()
        : Promise.resolve(this.catalog),
      this.service.loadCapabilities(),
    ]);
    if (
      this.collectionRequestId !== requestId ||
      this.activeCapability !== capability
    ) {
      return;
    }

    runInAction(() => {
      if (items.status === "fulfilled") {
        this.items = items.value;
      }
      if (catalog.status === "fulfilled") {
        this.catalog = catalog.value;
      }
      if (capabilities.status === "fulfilled") {
        this.capabilities = capabilities.value;
        this.overviewErrorMessage = null;
      } else {
        this.overviewErrorMessage = serviceErrorMessage(
          capabilities.reason,
          OVERVIEW_ERROR_MESSAGE,
        );
      }
      this.collectionErrorMessage = firstRejectedMessage(
        [items, catalog],
        COLLECTION_ERROR_MESSAGE,
      );
      this.hasLoadedCollection = true;
      this.isCollectionLoading = false;
    });
  }

  async loadProviderTools(
    organizationId: string,
    capability: ProviderCapability,
  ): Promise<void> {
    const requestId = ++this.providerToolsRequestId;
    const isSameCapability = this.providerToolsCapability === capability;
    this.providerToolsCapability = capability;
    this.providerToolsErrorMessage = null;
    this.isProviderToolsLoading = true;
    if (!isSameCapability) {
      this.providerTools = [];
    }

    try {
      const tools = await this.service.listProviderTools(
        organizationId,
        capability,
      );
      if (
        this.providerToolsRequestId !== requestId ||
        this.providerToolsCapability !== capability
      ) {
        return;
      }
      runInAction(() => {
        this.providerTools = tools;
      });
    } catch (error) {
      if (
        this.providerToolsRequestId === requestId &&
        this.providerToolsCapability === capability
      ) {
        runInAction(() => {
          this.providerToolsErrorMessage = serviceErrorMessage(
            error,
            PROVIDER_TOOLS_ERROR_MESSAGE,
          );
        });
      }
    } finally {
      if (
        this.providerToolsRequestId === requestId &&
        this.providerToolsCapability === capability
      ) {
        runInAction(() => {
          this.isProviderToolsLoading = false;
        });
      }
    }
  }

  async loadSelected(
    capability: ProviderCapability,
    configId: string,
  ): Promise<void> {
    const requestId = ++this.selectedRequestId;
    this.selectedConfig =
      this.items.find((config) => config.id === configId) ?? null;
    this.selectedErrorMessage = null;
    this.isSelectedLoading = true;

    try {
      const config = await this.service.get(capability, configId);
      if (this.selectedRequestId !== requestId) {
        return;
      }
      runInAction(() => {
        this.selectedConfig = config;
        this.replaceRecord(config);
      });
    } catch (error) {
      if (this.selectedRequestId === requestId) {
        runInAction(() => {
          this.selectedConfig = null;
          this.selectedErrorMessage = serviceErrorMessage(
            error,
            DETAIL_ERROR_MESSAGE,
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
    this.selectedConfig = null;
    this.selectedErrorMessage = null;
    this.isSelectedLoading = false;
  }

  clearActionError(): void {
    this.actionErrorMessage = null;
  }

  async verify(config: ProviderConfigRecord): Promise<boolean> {
    return this.runAction(config, "verify", async () => {
      await this.service.verify(config.capability, config.id);
      return this.service.get(config.capability, config.id);
    });
  }

  async setEnabled(
    config: ProviderConfigRecord,
    enabled: boolean,
  ): Promise<boolean> {
    const input: ProviderConfigUpdateInput = { enabled };
    return this.runAction(config, enabled ? "enable" : "disable", () =>
      this.service.update(config.capability, config.id, input),
    );
  }

  async delete(config: ProviderConfigRecord): Promise<boolean> {
    if (this.pendingAction !== null) {
      return false;
    }
    this.pendingAction = { action: "delete", configId: config.id };
    this.actionErrorMessage = null;

    try {
      await this.service.delete(config.capability, config.id);
      const isCurrent = this.activeCapability === config.capability;
      runInAction(() => {
        if (isCurrent) {
          this.items = this.items.filter((item) => item.id !== config.id);
          if (this.selectedConfig?.id === config.id) {
            this.clearSelected();
          }
        }
      });
      await this.refreshCapabilities();
      return isCurrent && this.activeCapability === config.capability;
    } catch (error) {
      if (this.activeCapability === config.capability) {
        runInAction(() => {
          this.actionErrorMessage = serviceErrorMessage(
            error,
            ACTION_ERROR_MESSAGE,
          );
        });
      }
      return false;
    } finally {
      runInAction(() => {
        this.pendingAction = null;
      });
    }
  }

  private async runAction(
    config: ProviderConfigRecord,
    action: Exclude<ProviderAction, "delete">,
    operation: () => Promise<ProviderConfigRecord>,
  ): Promise<boolean> {
    if (this.pendingAction !== null) {
      return false;
    }
    this.pendingAction = { action, configId: config.id };
    this.actionErrorMessage = null;

    try {
      const updated = await operation();
      const isCurrent = this.activeCapability === config.capability;
      runInAction(() => {
        if (isCurrent) {
          this.replaceRecord(updated);
          if (this.selectedConfig?.id === updated.id) {
            this.selectedConfig = updated;
          }
        }
      });
      await this.refreshCapabilities();
      return isCurrent && this.activeCapability === config.capability;
    } catch (error) {
      if (this.activeCapability === config.capability) {
        runInAction(() => {
          this.actionErrorMessage = serviceErrorMessage(
            error,
            ACTION_ERROR_MESSAGE,
          );
        });
      }
      return false;
    } finally {
      runInAction(() => {
        this.pendingAction = null;
      });
    }
  }

  private replaceRecord(config: ProviderConfigRecord): void {
    const index = this.items.findIndex((item) => item.id === config.id);
    if (index === -1) {
      this.items = [...this.items, config];
      return;
    }
    this.items = this.items.map((item) =>
      item.id === config.id ? config : item,
    );
  }

  private async refreshCapabilities(): Promise<void> {
    try {
      const capabilities = await this.service.loadCapabilities();
      runInAction(() => {
        this.capabilities = capabilities;
      });
    } catch {
      runInAction(() => {
        this.overviewErrorMessage = OVERVIEW_ERROR_MESSAGE;
      });
    }
  }
}

function serviceErrorMessage(error: unknown, fallback: string): string {
  return error instanceof ProviderServiceError ? error.message : fallback;
}

function firstRejectedMessage(
  results: readonly PromiseSettledResult<unknown>[],
  fallback: string,
): string | null {
  const rejected = results.find(
    (result): result is PromiseRejectedResult => result.status === "rejected",
  );
  return rejected === undefined
    ? null
    : serviceErrorMessage(rejected.reason, fallback);
}

export { ProvidersStore };
