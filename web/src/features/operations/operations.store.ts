import { makeAutoObservable, runInAction } from "mobx";

import {
  OperationsService,
  OperationsServiceError,
} from "@/features/operations/operations.service";
import type {
  AgentInputRequest,
  AgentRun,
  EventHealth,
  ExecutionBudget,
  ExecutionBudgetInput,
  OperationAgent,
  ServiceHealth,
  VoiceSession,
  VoiceSessionDetail,
} from "@/features/operations/operations.types";

class AgentRunsOperationsStore {
  actionErrorMessage: string | null = null;
  budget: ExecutionBudget | null = null;
  budgetErrorMessage: string | null = null;
  collectionErrorMessage: string | null = null;
  isActing = false;
  isBudgetLoading = false;
  isCollectionLoading = false;
  isSelectedLoading = false;
  items: AgentRun[] = [];
  selectedErrorMessage: string | null = null;
  selectedRun: AgentRun | null = null;
  private collectionRequest: AbortController | null = null;
  private selectedRequest: AbortController | null = null;
  private readonly service: OperationsService;

  constructor(service: OperationsService) {
    this.service = service;
    makeAutoObservable<
      this,
      "collectionRequest" | "selectedRequest" | "service"
    >(
      this,
      { collectionRequest: false, selectedRequest: false, service: false },
      { autoBind: true },
    );
  }

  async loadCollection(organizationId: string): Promise<void> {
    this.collectionRequest?.abort();
    const request = new AbortController();
    this.collectionRequest = request;
    this.isCollectionLoading = true;
    this.collectionErrorMessage = null;
    try {
      const items = await this.service.listAgentRuns(
        organizationId,
        request.signal,
      );
      if (!request.signal.aborted && this.collectionRequest === request)
        runInAction(() => {
          this.items = items;
        });
    } catch (error) {
      if (!request.signal.aborted && this.collectionRequest === request)
        runInAction(() => {
          this.collectionErrorMessage = message(
            error,
            "Agent runs could not be loaded.",
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

  async loadSelected(organizationId: string, runId: string): Promise<void> {
    this.clearSelected();
    const request = new AbortController();
    this.selectedRequest = request;
    this.isSelectedLoading = true;
    try {
      const run = await this.service.getAgentRun(
        organizationId,
        runId,
        request.signal,
      );
      if (!request.signal.aborted && this.selectedRequest === request)
        runInAction(() => {
          this.selectedRun = run;
        });
    } catch (error) {
      if (!request.signal.aborted && this.selectedRequest === request)
        runInAction(() => {
          this.selectedErrorMessage = message(
            error,
            "This Agent run could not be loaded.",
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

  async loadBudget(organizationId: string): Promise<void> {
    this.isBudgetLoading = true;
    this.budgetErrorMessage = null;
    try {
      const budget = await this.service.getBudget(organizationId);
      runInAction(() => {
        this.budget = budget;
      });
    } catch (error) {
      runInAction(() => {
        this.budgetErrorMessage = message(
          error,
          "Execution budget could not be loaded.",
        );
      });
    } finally {
      runInAction(() => {
        this.isBudgetLoading = false;
      });
    }
  }

  async saveBudget(
    organizationId: string,
    input: ExecutionBudgetInput,
  ): Promise<boolean> {
    if (this.isActing) return false;
    this.isActing = true;
    this.budgetErrorMessage = null;
    try {
      const budget = await this.service.putBudget(organizationId, input);
      runInAction(() => {
        this.budget = budget;
      });
      return true;
    } catch (error) {
      runInAction(() => {
        this.budgetErrorMessage = message(
          error,
          "Execution budget could not be saved.",
        );
      });
      return false;
    } finally {
      runInAction(() => {
        this.isActing = false;
      });
    }
  }

  async cancel(organizationId: string): Promise<boolean> {
    const run = this.selectedRun;
    if (run === null || this.isActing) return false;
    this.isActing = true;
    this.actionErrorMessage = null;
    try {
      const updated = await this.service.cancelAgentRun(organizationId, run);
      runInAction(() => {
        this.replace(updated);
      });
      return true;
    } catch (error) {
      runInAction(() => {
        this.actionErrorMessage = message(
          error,
          "The Agent run could not be cancelled.",
        );
      });
      return false;
    } finally {
      runInAction(() => {
        this.isActing = false;
      });
    }
  }

  async answer(
    organizationId: string,
    request: AgentInputRequest,
    response: unknown,
  ): Promise<boolean> {
    const run = this.selectedRun;
    if (run === null || this.isActing) return false;
    this.isActing = true;
    this.actionErrorMessage = null;
    try {
      await this.service.answerAgentInput(
        organizationId,
        run,
        request,
        response,
      );
      const updated = await this.service.getAgentRun(organizationId, run.id);
      runInAction(() => {
        this.replace(updated);
      });
      return true;
    } catch (error) {
      runInAction(() => {
        this.actionErrorMessage = message(
          error,
          "The response could not be submitted.",
        );
      });
      return false;
    } finally {
      runInAction(() => {
        this.isActing = false;
      });
    }
  }

  clearSelected(): void {
    this.selectedRequest?.abort();
    this.selectedRequest = null;
    this.selectedRun = null;
    this.selectedErrorMessage = null;
    this.actionErrorMessage = null;
    this.isSelectedLoading = false;
  }
  private replace(run: AgentRun): void {
    this.selectedRun = run;
    this.items = this.items.map((item) => (item.id === run.id ? run : item));
  }
}

class VoiceSessionsOperationsStore {
  collectionErrorMessage: string | null = null;
  isCollectionLoading = false;
  isSelectedLoading = false;
  items: VoiceSession[] = [];
  selectedErrorMessage: string | null = null;
  selectedSession: VoiceSessionDetail | null = null;
  private collectionRequest: AbortController | null = null;
  private selectedRequest: AbortController | null = null;
  private readonly service: OperationsService;
  constructor(service: OperationsService) {
    this.service = service;
    makeAutoObservable<
      this,
      "collectionRequest" | "selectedRequest" | "service"
    >(
      this,
      { collectionRequest: false, selectedRequest: false, service: false },
      { autoBind: true },
    );
  }
  async loadCollection(organizationId: string): Promise<void> {
    this.collectionRequest?.abort();
    const request = new AbortController();
    this.collectionRequest = request;
    this.isCollectionLoading = true;
    this.collectionErrorMessage = null;
    try {
      const items = await this.service.listVoiceSessions(
        organizationId,
        request.signal,
      );
      if (!request.signal.aborted && this.collectionRequest === request)
        runInAction(() => {
          this.items = items;
        });
    } catch (error) {
      if (!request.signal.aborted && this.collectionRequest === request)
        runInAction(() => {
          this.collectionErrorMessage = message(
            error,
            "Voice sessions could not be loaded.",
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
  async loadSelected(organizationId: string, sessionId: string): Promise<void> {
    this.clearSelected();
    const request = new AbortController();
    this.selectedRequest = request;
    this.isSelectedLoading = true;
    try {
      const session = await this.service.getVoiceSession(
        organizationId,
        sessionId,
        request.signal,
      );
      if (!request.signal.aborted && this.selectedRequest === request)
        runInAction(() => {
          this.selectedSession = session;
        });
    } catch (error) {
      if (!request.signal.aborted && this.selectedRequest === request)
        runInAction(() => {
          this.selectedErrorMessage = message(
            error,
            "This voice session could not be loaded.",
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
  clearSelected(): void {
    this.selectedRequest?.abort();
    this.selectedRequest = null;
    this.selectedSession = null;
    this.selectedErrorMessage = null;
    this.isSelectedLoading = false;
  }
}

class HealthOperationsStore {
  errorMessage: string | null = null;
  eventHealth: EventHealth | null = null;
  isLoading = false;
  serviceHealth: ServiceHealth | null = null;
  private request: AbortController | null = null;
  private readonly service: OperationsService;
  constructor(service: OperationsService) {
    this.service = service;
    makeAutoObservable<this, "request" | "service">(
      this,
      { request: false, service: false },
      { autoBind: true },
    );
  }
  async load(mode: "events" | "system"): Promise<void> {
    this.request?.abort();
    const request = new AbortController();
    this.request = request;
    this.isLoading = true;
    this.errorMessage = null;
    try {
      if (mode === "events") {
        const health = await this.service.eventHealth(request.signal);
        if (!request.signal.aborted && this.request === request)
          runInAction(() => {
            this.eventHealth = health;
          });
      } else {
        const [serviceHealth, eventHealth] = await Promise.all([
          this.service.serviceHealth(request.signal),
          this.service.eventHealth(request.signal),
        ]);
        if (!request.signal.aborted && this.request === request)
          runInAction(() => {
            this.serviceHealth = serviceHealth;
            this.eventHealth = eventHealth;
          });
      }
    } catch (error) {
      if (!request.signal.aborted && this.request === request)
        runInAction(() => {
          this.errorMessage = message(
            error,
            "Platform health could not be loaded.",
          );
        });
    } finally {
      if (this.request === request)
        runInAction(() => {
          this.request = null;
          this.isLoading = false;
        });
    }
  }
}

class OperationsStore {
  agentReferences: OperationAgent[] = [];
  referenceErrorMessage: string | null = null;
  readonly agentRuns: AgentRunsOperationsStore;
  readonly health: HealthOperationsStore;
  readonly voiceSessions: VoiceSessionsOperationsStore;
  private readonly service: OperationsService;
  constructor(service: OperationsService) {
    this.service = service;
    this.agentRuns = new AgentRunsOperationsStore(service);
    this.health = new HealthOperationsStore(service);
    this.voiceSessions = new VoiceSessionsOperationsStore(service);
    makeAutoObservable<this, "service">(
      this,
      { agentRuns: false, health: false, service: false, voiceSessions: false },
      { autoBind: true },
    );
  }
  async loadAgentReferences(organizationId: string): Promise<void> {
    this.referenceErrorMessage = null;
    try {
      const agents = await this.service.agents(organizationId);
      runInAction(() => {
        this.agentReferences = agents;
      });
    } catch (error) {
      runInAction(() => {
        this.referenceErrorMessage = message(
          error,
          "Agent names could not be loaded.",
        );
      });
    }
  }
  agentName(agentId: string | null | undefined): string {
    if (agentId === null || agentId === undefined) return "No Agent";
    return (
      this.agentReferences.find((agent) => agent.id === agentId)?.name ??
      `Agent …${agentId.slice(-12)}`
    );
  }
}

function message(error: unknown, fallback: string): string {
  return error instanceof OperationsServiceError ? error.message : fallback;
}

export { OperationsStore };
