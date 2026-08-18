import { makeAutoObservable, runInAction } from "mobx";

import {
  CampaignsService,
  CampaignsServiceError,
} from "@/features/campaigns/campaigns.service";
import type {
  Campaign,
  CampaignAgent,
  CampaignAnalytics,
  CampaignContact,
  CampaignCreate,
  CampaignEmailConfig,
  CampaignPreparation,
  CampaignTemplate,
  CampaignUpdate,
  CampaignUploadContact,
  OrganizationContact,
} from "@/features/campaigns/campaigns.types";

class CampaignsStore {
  actionErrorMessage: string | null = null;
  agents: CampaignAgent[] = [];
  analytics: CampaignAnalytics | null = null;
  collectionErrorMessage: string | null = null;
  contacts: CampaignContact[] = [];
  emailConfigs: CampaignEmailConfig[] = [];
  isActing = false;
  isCollectionLoading = false;
  isPreparationLoading = false;
  isReferencesLoading = false;
  isSelectedLoading = false;
  items: Campaign[] = [];
  organizationContacts: OrganizationContact[] = [];
  preparation: CampaignPreparation | null = null;
  referenceErrorMessage: string | null = null;
  selectedCampaign: Campaign | null = null;
  selectedErrorMessage: string | null = null;
  templates: CampaignTemplate[] = [];
  private collectionRequest: AbortController | null = null;
  private referenceRequest: AbortController | null = null;
  private selectedRequest: AbortController | null = null;
  private readonly service: CampaignsService;

  constructor(service: CampaignsService) {
    this.service = service;
    makeAutoObservable<
      this,
      "collectionRequest" | "referenceRequest" | "selectedRequest" | "service"
    >(
      this,
      {
        collectionRequest: false,
        referenceRequest: false,
        selectedRequest: false,
        service: false,
      },
      { autoBind: true },
    );
  }

  async loadCollection(organizationId: string): Promise<void> {
    this.collectionRequest?.abort();
    const request = new AbortController();
    this.collectionRequest = request;
    this.collectionErrorMessage = null;
    this.isCollectionLoading = true;
    try {
      const items = await this.service.list(organizationId, request.signal);
      if (!request.signal.aborted && this.collectionRequest === request)
        runInAction(() => {
          this.items = items;
        });
    } catch (error) {
      if (!request.signal.aborted && this.collectionRequest === request)
        runInAction(() => {
          this.collectionErrorMessage = message(
            error,
            "Campaigns could not be loaded.",
          );
        });
    } finally {
      if (this.collectionRequest === request)
        runInAction(() => {
          this.collectionRequest = null;
          this.isCollectionLoading = false;
        });
    }
  }

  async loadReferences(organizationId: string): Promise<void> {
    this.referenceRequest?.abort();
    const request = new AbortController();
    this.referenceRequest = request;
    this.referenceErrorMessage = null;
    this.isReferencesLoading = true;
    try {
      const [agents, templates, emailConfigs, organizationContacts] =
        await Promise.all([
          this.service.agents(organizationId, request.signal),
          this.service.templates(request.signal),
          this.service.emailConfigs(request.signal),
          this.service.organizationContacts(organizationId, request.signal),
        ]);
      if (!request.signal.aborted && this.referenceRequest === request)
        runInAction(() => {
          this.agents = agents;
          this.templates = templates;
          this.emailConfigs = emailConfigs;
          this.organizationContacts = organizationContacts;
        });
    } catch (error) {
      if (!request.signal.aborted && this.referenceRequest === request)
        runInAction(() => {
          this.referenceErrorMessage = message(
            error,
            "Campaign references could not be loaded.",
          );
        });
    } finally {
      if (this.referenceRequest === request)
        runInAction(() => {
          this.referenceRequest = null;
          this.isReferencesLoading = false;
        });
    }
  }

  async loadSelected(
    organizationId: string,
    campaignId: string,
  ): Promise<void> {
    this.clearSelected();
    const request = new AbortController();
    this.selectedRequest = request;
    this.isSelectedLoading = true;
    try {
      const [campaign, contacts, analytics, preparation] = await Promise.all([
        this.service.get(organizationId, campaignId, request.signal),
        this.service.contacts(organizationId, campaignId, request.signal),
        this.service.analytics(organizationId, campaignId, request.signal),
        this.service.preparation(organizationId, campaignId, request.signal),
      ]);
      if (!request.signal.aborted && this.selectedRequest === request)
        runInAction(() => {
          this.selectedCampaign = campaign;
          this.contacts = contacts;
          this.analytics = analytics;
          this.preparation = preparation;
        });
    } catch (error) {
      if (!request.signal.aborted && this.selectedRequest === request)
        runInAction(() => {
          this.selectedErrorMessage = message(
            error,
            "This campaign could not be loaded.",
          );
        });
    } finally {
      if (this.selectedRequest === request)
        runInAction(() => {
          this.selectedRequest = null;
          this.isSelectedLoading = false;
        });
    }
  }

  async loadDefinition(
    organizationId: string,
    campaignId: string,
  ): Promise<void> {
    this.clearSelected();
    const request = new AbortController();
    this.selectedRequest = request;
    this.isSelectedLoading = true;
    try {
      const campaign = await this.service.get(
        organizationId,
        campaignId,
        request.signal,
      );
      if (!request.signal.aborted && this.selectedRequest === request)
        runInAction(() => {
          this.selectedCampaign = campaign;
        });
    } catch (error) {
      if (!request.signal.aborted && this.selectedRequest === request)
        runInAction(() => {
          this.selectedErrorMessage = message(
            error,
            "This campaign could not be loaded.",
          );
        });
    } finally {
      if (this.selectedRequest === request)
        runInAction(() => {
          this.selectedRequest = null;
          this.isSelectedLoading = false;
        });
    }
  }

  async refreshSelected(organizationId: string): Promise<void> {
    if (this.selectedCampaign === null) return;
    await this.loadSelected(organizationId, this.selectedCampaign.id);
  }

  async refreshPreparation(organizationId: string): Promise<void> {
    const campaign = this.selectedCampaign;
    if (campaign === null) return;
    this.isPreparationLoading = true;
    this.actionErrorMessage = null;
    try {
      const preparation = await this.service.preparation(
        organizationId,
        campaign.id,
      );
      runInAction(() => {
        this.preparation = preparation;
      });
    } catch (error) {
      runInAction(() => {
        this.actionErrorMessage = message(
          error,
          "Campaign preparation could not be loaded.",
        );
      });
    } finally {
      runInAction(() => {
        this.isPreparationLoading = false;
      });
    }
  }

  async create(
    organizationId: string,
    input: CampaignCreate,
  ): Promise<Campaign | null> {
    return this.mutate(async () => {
      const campaign = await this.service.create(organizationId, input);
      runInAction(() => {
        this.items = [campaign, ...this.items];
      });
      return campaign;
    });
  }

  async update(
    organizationId: string,
    campaignId: string,
    input: CampaignUpdate,
  ): Promise<Campaign | null> {
    return this.mutate(async () => {
      const campaign = await this.service.update(
        organizationId,
        campaignId,
        input,
      );
      runInAction(() => {
        this.replace(campaign);
      });
      return campaign;
    });
  }

  async transition(
    organizationId: string,
    action: "cancel" | "pause" | "start",
  ): Promise<boolean> {
    const campaign = this.selectedCampaign;
    if (campaign === null) return false;
    const result = await this.mutate(async () => {
      const updated = await this.service.transition(
        organizationId,
        campaign.id,
        action,
      );
      runInAction(() => {
        this.replace(updated);
      });
      return updated;
    });
    return result !== null;
  }

  async removeSelected(organizationId: string): Promise<boolean> {
    const campaign = this.selectedCampaign;
    if (campaign === null || this.isActing) return false;
    this.isActing = true;
    this.actionErrorMessage = null;
    try {
      await this.service.remove(organizationId, campaign.id);
      runInAction(() => {
        this.items = this.items.filter((item) => item.id !== campaign.id);
        this.selectedCampaign = null;
      });
      return true;
    } catch (error) {
      runInAction(() => {
        this.actionErrorMessage = message(
          error,
          "The campaign could not be deleted.",
        );
      });
      return false;
    } finally {
      runInAction(() => {
        this.isActing = false;
      });
    }
  }

  async revokeSelected(
    organizationId: string,
    reason: string,
  ): Promise<boolean> {
    const campaign = this.selectedCampaign;
    if (campaign === null || this.isActing) return false;
    this.isActing = true;
    this.actionErrorMessage = null;
    try {
      await this.service.revoke(organizationId, campaign, reason);
      const updated = await this.service.get(organizationId, campaign.id);
      runInAction(() => {
        this.replace(updated);
      });
      return true;
    } catch (error) {
      runInAction(() => {
        this.actionErrorMessage = message(
          error,
          "The campaign revision could not be revoked.",
        );
      });
      return false;
    } finally {
      runInAction(() => {
        this.isActing = false;
      });
    }
  }

  async addExistingContacts(
    organizationId: string,
    ids: string[],
  ): Promise<boolean> {
    const campaign = this.selectedCampaign;
    if (campaign === null || ids.length === 0) return false;
    const result = await this.mutate(async () => {
      await this.service.selectContacts(organizationId, campaign.id, ids);
      return campaign;
    });
    if (result === null) return false;
    await this.loadSelected(organizationId, campaign.id);
    return true;
  }

  async addAddresses(
    organizationId: string,
    contacts: CampaignUploadContact[],
  ): Promise<boolean> {
    const campaign = this.selectedCampaign;
    if (campaign === null || contacts.length === 0) return false;
    const result = await this.mutate(async () => {
      await this.service.uploadContacts(organizationId, campaign.id, contacts);
      return campaign;
    });
    if (result === null) return false;
    await this.loadSelected(organizationId, campaign.id);
    return true;
  }

  clearSelected(): void {
    this.selectedRequest?.abort();
    this.selectedRequest = null;
    this.selectedCampaign = null;
    this.selectedErrorMessage = null;
    this.contacts = [];
    this.analytics = null;
    this.preparation = null;
    this.actionErrorMessage = null;
    this.isSelectedLoading = false;
  }

  agentName(id: string): string {
    return (
      this.agents.find((agent) => agent.id === id)?.name ??
      `Agent …${id.slice(-12)}`
    );
  }
  templateName(id: string | null | undefined): string {
    if (id === null || id === undefined) return "No initial message template";
    return (
      this.templates.find((template) => template.id === id)?.name ??
      `Template …${id.slice(-12)}`
    );
  }
  emailConfigName(id: string | null | undefined): string {
    if (id === null || id === undefined) return "Not configured";
    return (
      this.emailConfigs.find((config) => config.id === id)?.name ??
      `Email config …${id.slice(-12)}`
    );
  }

  private replace(campaign: Campaign): void {
    this.selectedCampaign = campaign;
    this.items = this.items.map((item) =>
      item.id === campaign.id ? campaign : item,
    );
  }

  private async mutate(
    operation: () => Promise<Campaign>,
  ): Promise<Campaign | null> {
    if (this.isActing) return null;
    this.isActing = true;
    this.actionErrorMessage = null;
    try {
      return await operation();
    } catch (error) {
      runInAction(() => {
        this.actionErrorMessage = message(
          error,
          "The campaign action could not be completed.",
        );
      });
      return null;
    } finally {
      runInAction(() => {
        this.isActing = false;
      });
    }
  }
}

function message(error: unknown, fallback: string): string {
  return error instanceof CampaignsServiceError ? error.message : fallback;
}

export { CampaignsStore };
