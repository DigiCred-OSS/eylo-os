import { makeAutoObservable, runInAction } from "mobx";

import type { Agent } from "@/features/agents/agents.types";
import { SwarmDraftStorage } from "@/features/swarms/swarm-draft-storage";
import { SwarmFormStore } from "@/features/swarms/swarm-form.store";
import { applySwarmCollectionQuery } from "@/features/swarms/swarms.query";
import {
  SwarmsService,
  SwarmsServiceError,
} from "@/features/swarms/swarms.service";
import type {
  Swarm,
  SwarmCollectionQuery,
  SwarmMember,
  SwarmMemberView,
} from "@/features/swarms/swarms.types";

const COLLECTION_ERROR =
  "Swarms could not be loaded. Check the API connection and try again.";
const DETAIL_ERROR = "This Swarm could not be loaded. It may no longer exist.";

class SwarmsStore {
  actionErrorMessage: string | null = null;
  actionSuccessMessage: string | null = null;
  activeAction: string | null = null;
  availableAgents: Agent[] = [];
  collectionErrorMessage: string | null = null;
  deleteErrorMessage: string | null = null;
  isAvailableAgentsLoading = false;
  isCollectionLoading = false;
  isDeleting = false;
  isSelectedLoading = false;
  items: Swarm[] = [];
  limit = 20;
  page = 1;
  selectedErrorMessage: string | null = null;
  selectedMembers: SwarmMember[] = [];
  selectedSwarm: Swarm | null = null;
  total = 0;

  readonly form: SwarmFormStore;
  private collectionQuery: SwarmCollectionQuery | null = null;
  private collectionRequest: AbortController | null = null;
  private rawItems: Swarm[] = [];
  private selectedRequest: AbortController | null = null;
  private readonly service: SwarmsService;

  constructor(service: SwarmsService, draftStorage: SwarmDraftStorage) {
    this.service = service;
    this.form = new SwarmFormStore(service, draftStorage);
    makeAutoObservable<
      this,
      | "collectionQuery"
      | "collectionRequest"
      | "rawItems"
      | "selectedRequest"
      | "service"
    >(
      this,
      {
        collectionQuery: false,
        collectionRequest: false,
        form: false,
        rawItems: false,
        selectedRequest: false,
        service: false,
      },
      { autoBind: true },
    );
  }

  get hasMore(): boolean {
    return this.page * this.limit < this.total;
  }

  get isActing(): boolean {
    return this.activeAction !== null;
  }

  get selectedMemberViews(): SwarmMemberView[] {
    const agentsById = new Map(
      this.availableAgents.map((agent) => [agent.id, agent]),
    );
    return this.selectedMembers.map((mapping) => ({
      agent: agentsById.get(mapping.agentId) ?? null,
      mapping,
    }));
  }

  async loadCollection(
    organizationId: string,
    query: SwarmCollectionQuery,
  ): Promise<void> {
    this.collectionRequest?.abort();
    const request = new AbortController();
    this.collectionRequest = request;
    this.collectionQuery = query;
    this.collectionErrorMessage = null;
    this.isCollectionLoading = true;
    try {
      const swarms = await this.service.listSwarms(
        organizationId,
        request.signal,
      );
      if (request.signal.aborted) return;
      runInAction(() => {
        this.rawItems = swarms;
        this.projectCollection(query);
      });
    } catch {
      if (!request.signal.aborted) {
        runInAction(() => {
          this.collectionErrorMessage = COLLECTION_ERROR;
          this.items = [];
          this.total = 0;
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

  async loadSelected(organizationId: string, swarmId: string): Promise<void> {
    this.selectedRequest?.abort();
    const request = new AbortController();
    this.selectedRequest = request;
    this.selectedSwarm =
      this.rawItems.find((swarm) => swarm.id === swarmId) ?? null;
    this.selectedMembers = [];
    this.selectedErrorMessage = null;
    this.isSelectedLoading = true;
    try {
      const [swarm, members, agents] = await Promise.all([
        this.service.getSwarm(organizationId, swarmId, request.signal),
        this.service.listMembers(organizationId, swarmId, request.signal),
        this.service.listConversationalAgents(organizationId, request.signal),
      ]);
      if (request.signal.aborted) return;
      runInAction(() => {
        this.availableAgents = agents;
        this.selectedMembers = members;
        this.acceptSwarm(swarm);
      });
    } catch {
      if (!request.signal.aborted) {
        runInAction(() => {
          this.selectedSwarm = null;
          this.selectedMembers = [];
          this.selectedErrorMessage = DETAIL_ERROR;
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

  async loadAvailableAgents(organizationId: string): Promise<void> {
    if (this.isAvailableAgentsLoading) return;
    this.isAvailableAgentsLoading = true;
    this.actionErrorMessage = null;
    this.actionSuccessMessage = null;
    try {
      const agents =
        await this.service.listConversationalAgents(organizationId);
      runInAction(() => {
        this.availableAgents = agents;
      });
    } catch (error) {
      runInAction(() => {
        this.actionErrorMessage = errorMessage(
          error,
          "Conversational Agents could not be loaded.",
        );
      });
    } finally {
      runInAction(() => {
        this.isAvailableAgentsLoading = false;
      });
    }
  }

  clearSelected(): void {
    this.selectedRequest?.abort();
    this.selectedRequest = null;
    this.selectedSwarm = null;
    this.selectedMembers = [];
    this.selectedErrorMessage = null;
    this.isSelectedLoading = false;
    this.actionErrorMessage = null;
    this.actionSuccessMessage = null;
    this.activeAction = null;
  }

  clearDeleteError(): void {
    this.deleteErrorMessage = null;
  }

  clearActionError(): void {
    this.actionErrorMessage = null;
  }

  acceptSwarm(swarm: Swarm): void {
    const index = this.rawItems.findIndex(
      (candidate) => candidate.id === swarm.id,
    );
    if (index === -1) this.rawItems = [...this.rawItems, swarm];
    else {
      const nextItems = [...this.rawItems];
      nextItems[index] = swarm;
      this.rawItems = nextItems;
    }
    if (this.selectedSwarm?.id === swarm.id) this.selectedSwarm = swarm;
    this.form.synchronizeServerSwarm(swarm);
    if (this.collectionQuery !== null)
      this.projectCollection(this.collectionQuery);
  }

  async deleteSwarm(organizationId: string, swarmId: string): Promise<boolean> {
    if (this.isDeleting) return false;
    this.isDeleting = true;
    this.deleteErrorMessage = null;
    try {
      await this.service.deleteSwarm(organizationId, swarmId);
      runInAction(() => {
        this.rawItems = this.rawItems.filter((swarm) => swarm.id !== swarmId);
        if (this.selectedSwarm?.id === swarmId) this.clearSelected();
        if (this.collectionQuery !== null)
          this.projectCollection(this.collectionQuery);
      });
      return true;
    } catch (error) {
      runInAction(() => {
        this.deleteErrorMessage = errorMessage(
          error,
          "The Swarm could not be deleted. Try again.",
        );
      });
      return false;
    } finally {
      runInAction(() => {
        this.isDeleting = false;
      });
    }
  }

  async addMember(
    organizationId: string,
    agentId: string,
    description: string,
  ): Promise<boolean> {
    const swarm = this.selectedSwarm;
    if (swarm === null || this.isActing) return false;
    return this.runAction(
      "add-member",
      "Agent added to the Swarm draft.",
      async () => {
        await this.service.addMember(
          organizationId,
          swarm.id,
          agentId,
          nullable(description),
          swarm.draftVersion,
        );
        await this.refreshSelected(organizationId, swarm.id);
      },
    );
  }

  async removeMember(
    organizationId: string,
    agentId: string,
  ): Promise<boolean> {
    const swarm = this.selectedSwarm;
    if (swarm === null || this.isActing) return false;
    return this.runAction(
      `remove-member:${agentId}`,
      "Agent removed from the Swarm draft.",
      async () => {
        await this.service.removeMember(
          organizationId,
          swarm.id,
          agentId,
          swarm.draftVersion,
        );
        await this.refreshSelected(organizationId, swarm.id);
      },
    );
  }

  async publish(organizationId: string): Promise<boolean> {
    const swarm = this.selectedSwarm;
    if (swarm === null || this.isActing) return false;
    return this.runAction("publish", "Swarm topology published.", async () => {
      await this.service.publish(organizationId, swarm.id, swarm.draftVersion);
      await this.refreshSelected(organizationId, swarm.id);
    });
  }

  async withdraw(organizationId: string): Promise<boolean> {
    const swarm = this.selectedSwarm;
    if (swarm === null || this.isActing) return false;
    return this.runAction(
      "withdraw",
      "Swarm withdrawn from new work.",
      async () => {
        const updated = await this.service.withdraw(organizationId, swarm.id);
        runInAction(() => this.acceptSwarm(updated));
      },
    );
  }

  async revoke(organizationId: string, reason: string): Promise<boolean> {
    const swarm = this.selectedSwarm;
    if (
      swarm === null ||
      swarm.publishedRevision === null ||
      swarm.publishedRevision === undefined ||
      this.isActing
    ) {
      return false;
    }
    const revision = swarm.publishedRevision;
    return this.runAction(
      "revoke",
      `Swarm revision ${revision} revoked.`,
      async () => {
        await this.service.revoke(
          organizationId,
          swarm.id,
          revision,
          reason.trim(),
        );
        await this.refreshSelected(organizationId, swarm.id);
      },
    );
  }

  private async refreshSelected(
    organizationId: string,
    swarmId: string,
  ): Promise<void> {
    const [swarm, members] = await Promise.all([
      this.service.getSwarm(organizationId, swarmId),
      this.service.listMembers(organizationId, swarmId),
    ]);
    runInAction(() => {
      this.selectedMembers = members;
      this.acceptSwarm(swarm);
    });
  }

  private async runAction(
    action: string,
    successMessage: string,
    operation: () => Promise<void>,
  ): Promise<boolean> {
    this.activeAction = action;
    this.actionErrorMessage = null;
    this.actionSuccessMessage = null;
    try {
      await operation();
      runInAction(() => {
        this.actionSuccessMessage = successMessage;
      });
      return true;
    } catch (error) {
      runInAction(() => {
        this.actionErrorMessage = errorMessage(
          error,
          "The Swarm could not be changed. Try again.",
        );
      });
      return false;
    } finally {
      runInAction(() => {
        this.activeAction = null;
      });
    }
  }

  private projectCollection(query: SwarmCollectionQuery): void {
    const result = applySwarmCollectionQuery(this.rawItems, query);
    this.items = result.items;
    this.total = result.total;
    this.limit = query.limit;
    this.page = query.page;
  }
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof SwarmsServiceError ? error.message : fallback;
}

function nullable(value: string): string | null {
  const trimmed = value.trim();
  return trimmed === "" ? null : trimmed;
}

export { SwarmsStore };
