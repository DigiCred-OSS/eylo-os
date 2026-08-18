import { makeAutoObservable, runInAction } from "mobx";

import {
  ToolsService,
  ToolsServiceError,
} from "@/features/tools/tools.service";
import type {
  ToolCapability,
  ToolRecord,
  ToolSource,
} from "@/features/tools/tools.types";

class ToolsStore {
  actionErrorMessage: string | null = null;
  collectionErrorMessage: string | null = null;
  isActing = false;
  isCollectionLoading = false;
  isSelectedLoading = false;
  items: ToolRecord[] = [];
  selectedErrorMessage: string | null = null;
  selectedTool: ToolRecord | null = null;

  private collectionRequest: AbortController | null = null;
  private collectionContext: string | null = null;
  private selectedRequest: AbortController | null = null;
  private readonly service: ToolsService;

  constructor(service: ToolsService) {
    this.service = service;
    makeAutoObservable<
      this,
      "collectionContext" | "collectionRequest" | "selectedRequest" | "service"
    >(
      this,
      {
        collectionContext: false,
        collectionRequest: false,
        selectedRequest: false,
        service: false,
      },
      { autoBind: true },
    );
  }

  async loadCollection(
    organizationId: string,
    source: ToolSource,
    capability: ToolCapability,
  ): Promise<void> {
    this.collectionRequest?.abort();
    const request = new AbortController();
    const context = `${organizationId}:${source}:${capability}`;
    this.collectionContext = context;
    this.collectionRequest = request;
    this.collectionErrorMessage = null;
    this.isCollectionLoading = true;
    this.items = [];
    this.clearSelected();

    try {
      const items = await this.service.list(
        organizationId,
        source,
        capability,
        request.signal,
      );
      if (request.signal.aborted || this.collectionContext !== context) {
        return;
      }
      runInAction(() => {
        this.items = items;
      });
    } catch (error) {
      if (!request.signal.aborted && this.collectionContext === context) {
        runInAction(() => {
          this.collectionErrorMessage = errorMessage(
            error,
            "Tools could not be loaded. Check the API connection and try again.",
          );
        });
      }
    } finally {
      if (this.collectionRequest === request) {
        runInAction(() => {
          this.collectionRequest = null;
          this.isCollectionLoading = false;
        });
      }
    }
  }

  async select(
    organizationId: string,
    toolId: string,
    source: ToolSource,
  ): Promise<void> {
    this.selectedRequest?.abort();
    this.selectedErrorMessage = null;
    this.actionErrorMessage = null;
    const local = this.items.find((item) => item.id === toolId) ?? null;
    if (source !== "managed") {
      this.selectedTool = local;
      if (local === null && !this.isCollectionLoading) {
        this.selectedErrorMessage = "This catalog tool is no longer available.";
      }
      return;
    }
    const request = new AbortController();
    this.selectedRequest = request;
    this.isSelectedLoading = true;
    this.selectedTool = local;
    try {
      const tool = await this.service.get(
        organizationId,
        toolId,
        request.signal,
      );
      if (!request.signal.aborted && this.selectedRequest === request) {
        runInAction(() => {
          this.selectedTool = tool;
        });
      }
    } catch (error) {
      if (!request.signal.aborted && this.selectedRequest === request) {
        runInAction(() => {
          this.selectedErrorMessage = errorMessage(
            error,
            "This tool could not be loaded.",
          );
        });
      }
    } finally {
      if (this.selectedRequest === request) {
        runInAction(() => {
          this.selectedRequest = null;
          this.isSelectedLoading = false;
        });
      }
    }
  }

  clearSelected(): void {
    this.selectedRequest?.abort();
    this.selectedRequest = null;
    this.selectedTool = null;
    this.selectedErrorMessage = null;
    this.actionErrorMessage = null;
    this.isSelectedLoading = false;
  }

  async publish(organizationId: string): Promise<boolean> {
    return this.runAction(async (tool) => {
      await this.service.publish(organizationId, tool);
      return await this.service.get(organizationId, tool.id);
    });
  }

  async withdraw(organizationId: string): Promise<boolean> {
    return this.runAction((tool) =>
      this.service.withdraw(organizationId, tool.id),
    );
  }

  async revoke(organizationId: string, reason: string): Promise<boolean> {
    return this.runAction(async (tool) => {
      await this.service.revoke(organizationId, tool, reason);
      return await this.service.get(organizationId, tool.id);
    });
  }

  async deleteSelected(organizationId: string): Promise<boolean> {
    const tool = this.selectedTool;
    if (tool === null || this.isActing) {
      return false;
    }
    this.isActing = true;
    this.actionErrorMessage = null;
    try {
      await this.service.delete(organizationId, tool.id);
      runInAction(() => {
        this.items = this.items.filter((item) => item.id !== tool.id);
        this.selectedTool = null;
      });
      return true;
    } catch (error) {
      runInAction(() => {
        this.actionErrorMessage = errorMessage(
          error,
          "The tool could not be deleted.",
        );
      });
      return false;
    } finally {
      runInAction(() => {
        this.isActing = false;
      });
    }
  }

  private async runAction(
    action: (tool: ToolRecord) => Promise<ToolRecord>,
  ): Promise<boolean> {
    const tool = this.selectedTool;
    if (tool === null || this.isActing) {
      return false;
    }
    this.isActing = true;
    this.actionErrorMessage = null;
    try {
      const updated = await action(tool);
      runInAction(() => {
        this.selectedTool = updated;
        this.items = this.items.map((item) =>
          item.id === updated.id ? updated : item,
        );
      });
      return true;
    } catch (error) {
      runInAction(() => {
        this.actionErrorMessage = errorMessage(
          error,
          "The tool action could not be completed.",
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

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ToolsServiceError ? error.message : fallback;
}

export { ToolsStore };
