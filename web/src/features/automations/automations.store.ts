import { makeAutoObservable, runInAction } from "mobx";

import {
  AutomationsService,
  AutomationsServiceError,
} from "@/features/automations/automations.service";
import type {
  ScheduleAgent,
  ScheduleCreateInput,
  ScheduleRecord,
  ScheduleRun,
  ScheduleUpdateInput,
} from "@/features/automations/automations.types";

class AutomationsStore {
  actionErrorMessage: string | null = null;
  actions: string[] = [];
  agents: ScheduleAgent[] = [];
  collectionErrorMessage: string | null = null;
  isActing = false;
  isCollectionLoading = false;
  isReferencesLoading = false;
  isSelectedLoading = false;
  items: ScheduleRecord[] = [];
  runs: ScheduleRun[] = [];
  runsErrorMessage: string | null = null;
  selectedErrorMessage: string | null = null;
  selectedSchedule: ScheduleRecord | null = null;

  private collectionRequest: AbortController | null = null;
  private referenceRequest: AbortController | null = null;
  private selectedRequest: AbortController | null = null;
  private readonly service: AutomationsService;

  constructor(service: AutomationsService) {
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
      if (!request.signal.aborted && this.collectionRequest === request) {
        runInAction(() => {
          this.items = items;
        });
      }
    } catch (error) {
      if (!request.signal.aborted && this.collectionRequest === request) {
        runInAction(() => {
          this.collectionErrorMessage = errorMessage(
            error,
            "Automations could not be loaded.",
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

  async loadReferences(organizationId: string): Promise<void> {
    this.referenceRequest?.abort();
    const request = new AbortController();
    this.referenceRequest = request;
    this.isReferencesLoading = true;
    try {
      const [actions, agents] = await Promise.all([
        this.service.actions(organizationId, request.signal),
        this.service.agents(organizationId, request.signal),
      ]);
      if (!request.signal.aborted && this.referenceRequest === request) {
        runInAction(() => {
          this.actions = actions;
          this.agents = agents;
        });
      }
    } catch (error) {
      if (!request.signal.aborted && this.referenceRequest === request) {
        runInAction(() => {
          this.actionErrorMessage = errorMessage(
            error,
            "Automation references could not be loaded.",
          );
        });
      }
    } finally {
      if (this.referenceRequest === request) {
        runInAction(() => {
          this.referenceRequest = null;
          this.isReferencesLoading = false;
        });
      }
    }
  }

  async loadSelected(
    organizationId: string,
    scheduleId: string,
  ): Promise<void> {
    this.clearSelected();
    const request = new AbortController();
    this.selectedRequest = request;
    this.isSelectedLoading = true;
    try {
      const [schedule, runs] = await Promise.all([
        this.service.get(organizationId, scheduleId, request.signal),
        this.service.runs(organizationId, scheduleId, request.signal),
      ]);
      if (!request.signal.aborted && this.selectedRequest === request) {
        runInAction(() => {
          this.selectedSchedule = schedule;
          this.runs = runs;
        });
      }
    } catch (error) {
      if (!request.signal.aborted && this.selectedRequest === request) {
        runInAction(() => {
          this.selectedErrorMessage = errorMessage(
            error,
            "This automation could not be loaded.",
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
    this.selectedSchedule = null;
    this.selectedErrorMessage = null;
    this.runs = [];
    this.runsErrorMessage = null;
    this.actionErrorMessage = null;
    this.isSelectedLoading = false;
  }

  async create(
    organizationId: string,
    input: ScheduleCreateInput,
  ): Promise<ScheduleRecord | null> {
    return this.runMutation(async () => {
      const created = await this.service.create(organizationId, input);
      runInAction(() => {
        this.items = [created, ...this.items];
      });
      return created;
    });
  }

  async update(
    organizationId: string,
    scheduleId: string,
    input: ScheduleUpdateInput,
  ): Promise<ScheduleRecord | null> {
    return this.runMutation(async () => {
      const updated = await this.service.update(
        organizationId,
        scheduleId,
        input,
      );
      runInAction(() => {
        this.items = this.items.map((item) =>
          item.id === updated.id ? updated : item,
        );
        this.selectedSchedule = updated;
      });
      return updated;
    });
  }

  async cancelSelected(organizationId: string): Promise<boolean> {
    const schedule = this.selectedSchedule;
    if (schedule === null) return false;
    const result = await this.runMutation(async () => {
      await this.service.cancel(organizationId, schedule.id);
      runInAction(() => {
        this.items = this.items.filter((item) => item.id !== schedule.id);
        this.selectedSchedule = null;
        this.runs = [];
      });
      return schedule;
    });
    return result !== null;
  }

  async revokeSelected(
    organizationId: string,
    reason: string,
  ): Promise<boolean> {
    const schedule = this.selectedSchedule;
    if (schedule === null) return false;
    const result = await this.runMutation(async () => {
      await this.service.revoke(organizationId, schedule, reason);
      const revoked = await this.service.get(organizationId, schedule.id);
      runInAction(() => {
        this.selectedSchedule = revoked;
        this.items = this.items.map((item) =>
          item.id === revoked.id ? revoked : item,
        );
      });
      return revoked;
    });
    return result !== null;
  }

  private async runMutation(
    action: () => Promise<ScheduleRecord>,
  ): Promise<ScheduleRecord | null> {
    if (this.isActing) return null;
    this.isActing = true;
    this.actionErrorMessage = null;
    try {
      return await action();
    } catch (error) {
      runInAction(() => {
        this.actionErrorMessage = errorMessage(
          error,
          "The automation action could not be completed.",
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

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof AutomationsServiceError ? error.message : fallback;
}

export { AutomationsStore };
