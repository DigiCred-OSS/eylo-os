import { makeAutoObservable, runInAction } from "mobx";

import type { ApiClient } from "@/api/client";
import { ProviderReferencesStore } from "@/features/providers/provider-references.store";
import { VoiceConfigDraftStorage } from "@/features/voice/voice-draft-storage";
import { VoiceConfigFormStore } from "@/features/voice/voice-form.store";
import {
  VoiceConfigService,
  VoiceConfigServiceError,
} from "@/features/voice/voice.service";
import type {
  VoiceConfigCompatibility,
  VoiceConfigRecord,
} from "@/features/voice/voice.types";

const COLLECTION_ERROR =
  "Voice Configs could not be loaded. Check the API connection and try again.";
const DETAIL_ERROR =
  "This Voice Config could not be loaded. It may no longer exist.";
const COMPATIBILITY_ERROR = "Provider capability details could not be loaded.";
const DELETE_ERROR = "The Voice Config could not be deleted.";

class VoiceConfigStore {
  collectionErrorMessage: string | null = null;
  compatibilityErrorMessage: string | null = null;
  deleteErrorMessage: string | null = null;
  isCollectionLoading = false;
  isCompatibilityLoading = false;
  isDeleting = false;
  isSelectedLoading = false;
  items: VoiceConfigRecord[] = [];
  selectedCompatibility: VoiceConfigCompatibility | null = null;
  selectedErrorMessage: string | null = null;
  selectedVoiceConfig: VoiceConfigRecord | null = null;

  readonly form: VoiceConfigFormStore;
  readonly references: ProviderReferencesStore;

  private activeOrganizationId: string | null = null;
  private collectionRequest: AbortController | null = null;
  private compatibilityRequest: AbortController | null = null;
  private selectedRequest: AbortController | null = null;
  private readonly service: VoiceConfigService;

  constructor(
    api: ApiClient,
    service: VoiceConfigService,
    draftStorage: VoiceConfigDraftStorage,
  ) {
    this.service = service;
    this.references = new ProviderReferencesStore(api);
    this.form = new VoiceConfigFormStore(
      service,
      draftStorage,
      this.references,
    );
    makeAutoObservable<
      this,
      | "activeOrganizationId"
      | "collectionRequest"
      | "compatibilityRequest"
      | "selectedRequest"
      | "service"
    >(
      this,
      {
        activeOrganizationId: false,
        collectionRequest: false,
        compatibilityRequest: false,
        form: false,
        references: false,
        selectedRequest: false,
        service: false,
      },
      { autoBind: true },
    );
  }

  get isCollectionStale(): boolean {
    return this.collectionErrorMessage !== null && this.items.length > 0;
  }

  async loadCollection(organizationId: string): Promise<void> {
    this.collectionRequest?.abort();
    const request = new AbortController();
    const contextChanged = this.activeOrganizationId !== organizationId;
    this.collectionRequest = request;
    this.activeOrganizationId = organizationId;
    this.collectionErrorMessage = null;
    this.isCollectionLoading = true;
    if (contextChanged) {
      this.items = [];
      this.clearSelected();
    }
    try {
      const items = await this.service.list(organizationId, request.signal);
      if (
        request.signal.aborted ||
        this.activeOrganizationId !== organizationId
      ) {
        return;
      }
      runInAction(() => {
        this.items = items;
      });
    } catch (error) {
      if (
        !request.signal.aborted &&
        this.activeOrganizationId === organizationId
      ) {
        runInAction(() => {
          this.collectionErrorMessage = serviceErrorMessage(
            error,
            COLLECTION_ERROR,
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

  async loadSelected(
    organizationId: string,
    voiceConfigId: string,
  ): Promise<void> {
    this.selectedRequest?.abort();
    this.compatibilityRequest?.abort();
    const request = new AbortController();
    this.selectedRequest = request;
    this.selectedVoiceConfig =
      this.items.find((item) => item.id === voiceConfigId) ?? null;
    this.selectedCompatibility = null;
    this.selectedErrorMessage = null;
    this.compatibilityErrorMessage = null;
    this.isSelectedLoading = true;
    try {
      const voiceConfig = await this.service.get(
        organizationId,
        voiceConfigId,
        request.signal,
      );
      if (request.signal.aborted) {
        return;
      }
      runInAction(() => {
        this.selectedVoiceConfig = voiceConfig;
        this.upsert(voiceConfig);
      });
      void this.loadCompatibility(organizationId, voiceConfigId);
    } catch (error) {
      if (!request.signal.aborted) {
        runInAction(() => {
          this.selectedVoiceConfig = null;
          this.selectedErrorMessage = serviceErrorMessage(error, DETAIL_ERROR);
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
    this.compatibilityRequest?.abort();
    this.selectedRequest = null;
    this.compatibilityRequest = null;
    this.selectedVoiceConfig = null;
    this.selectedCompatibility = null;
    this.selectedErrorMessage = null;
    this.compatibilityErrorMessage = null;
    this.isSelectedLoading = false;
    this.isCompatibilityLoading = false;
  }

  clearDeleteError(): void {
    this.deleteErrorMessage = null;
  }

  async deleteVoiceConfig(
    organizationId: string,
    voiceConfigId: string,
  ): Promise<boolean> {
    if (this.isDeleting) {
      return false;
    }
    this.isDeleting = true;
    this.deleteErrorMessage = null;
    try {
      await this.service.delete(organizationId, voiceConfigId);
      if (this.activeOrganizationId !== organizationId) {
        return false;
      }
      runInAction(() => {
        this.items = this.items.filter((item) => item.id !== voiceConfigId);
        if (this.selectedVoiceConfig?.id === voiceConfigId) {
          this.clearSelected();
        }
      });
      return true;
    } catch (error) {
      if (this.activeOrganizationId === organizationId) {
        runInAction(() => {
          this.deleteErrorMessage = serviceErrorMessage(error, DELETE_ERROR);
        });
      }
      return false;
    } finally {
      runInAction(() => {
        this.isDeleting = false;
      });
    }
  }

  upsert(voiceConfig: VoiceConfigRecord): void {
    const index = this.items.findIndex((item) => item.id === voiceConfig.id);
    this.items =
      index === -1
        ? [voiceConfig, ...this.items]
        : this.items.map((item) =>
            item.id === voiceConfig.id ? voiceConfig : item,
          );
    if (this.selectedVoiceConfig?.id === voiceConfig.id) {
      this.selectedVoiceConfig = voiceConfig;
    }
  }

  private async loadCompatibility(
    organizationId: string,
    voiceConfigId: string,
  ): Promise<void> {
    this.compatibilityRequest?.abort();
    const request = new AbortController();
    this.compatibilityRequest = request;
    this.isCompatibilityLoading = true;
    try {
      const compatibility = await this.service.getCompatibility(
        organizationId,
        voiceConfigId,
        request.signal,
      );
      if (
        request.signal.aborted ||
        this.selectedVoiceConfig?.id !== voiceConfigId
      ) {
        return;
      }
      runInAction(() => {
        this.selectedCompatibility = compatibility;
        this.compatibilityErrorMessage = null;
      });
    } catch (error) {
      if (
        !request.signal.aborted &&
        this.selectedVoiceConfig?.id === voiceConfigId
      ) {
        runInAction(() => {
          this.compatibilityErrorMessage = serviceErrorMessage(
            error,
            COMPATIBILITY_ERROR,
          );
        });
      }
    } finally {
      if (this.compatibilityRequest === request) {
        runInAction(() => {
          this.compatibilityRequest = null;
          this.isCompatibilityLoading = false;
        });
      }
    }
  }
}

function serviceErrorMessage(error: unknown, fallback: string): string {
  return error instanceof VoiceConfigServiceError ? error.message : fallback;
}

export { VoiceConfigStore };
