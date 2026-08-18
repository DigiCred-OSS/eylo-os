import { makeAutoObservable, runInAction } from "mobx";

import {
  TelephonyService,
  TelephonyServiceError,
} from "@/features/telephony/telephony.service";
import type {
  AvailableNumber,
  AvailableNumberSearch,
  DeletionJob,
  NumberPurchase,
  PhoneNumber,
  PhoneNumberCreate,
  PhoneNumberUpdate,
  TelephonyAgent,
  TelephonyCall,
  TelephonyConfig,
} from "@/features/telephony/telephony.types";

class PhoneNumbersStore {
  actionErrorMessage: string | null = null;
  availableNumbers: AvailableNumber[] = [];
  collectionErrorMessage: string | null = null;
  isActing = false;
  isCollectionLoading = false;
  isSearching = false;
  isSelectedLoading = false;
  items: PhoneNumber[] = [];
  searchErrorMessage: string | null = null;
  selectedErrorMessage: string | null = null;
  selectedNumber: PhoneNumber | null = null;
  private collectionRequest: AbortController | null = null;
  private searchRequest: AbortController | null = null;
  private selectedRequest: AbortController | null = null;
  private readonly service: TelephonyService;

  constructor(service: TelephonyService) {
    this.service = service;
    makeAutoObservable<
      this,
      "collectionRequest" | "searchRequest" | "selectedRequest" | "service"
    >(
      this,
      {
        collectionRequest: false,
        searchRequest: false,
        selectedRequest: false,
        service: false,
      },
      { autoBind: true },
    );
  }

  async loadCollection(): Promise<void> {
    this.collectionRequest?.abort();
    const request = new AbortController();
    this.collectionRequest = request;
    this.isCollectionLoading = true;
    this.collectionErrorMessage = null;
    try {
      const items = await this.service.listPhoneNumbers(request.signal);
      if (!request.signal.aborted && this.collectionRequest === request) {
        runInAction(() => {
          this.items = items;
        });
      }
    } catch (error) {
      if (!request.signal.aborted && this.collectionRequest === request) {
        runInAction(() => {
          this.collectionErrorMessage = message(
            error,
            "Phone numbers could not be loaded.",
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

  async loadSelected(id: string): Promise<void> {
    this.clearSelected();
    const request = new AbortController();
    this.selectedRequest = request;
    this.isSelectedLoading = true;
    try {
      const number = await this.service.getPhoneNumber(id, request.signal);
      if (!request.signal.aborted && this.selectedRequest === request) {
        runInAction(() => {
          this.selectedNumber = number;
        });
      }
    } catch (error) {
      if (!request.signal.aborted && this.selectedRequest === request) {
        runInAction(() => {
          this.selectedErrorMessage = message(
            error,
            "This phone number could not be loaded.",
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

  async register(input: PhoneNumberCreate): Promise<PhoneNumber | null> {
    return this.perform(async () => this.service.registerPhoneNumber(input));
  }

  async update(
    id: string,
    input: PhoneNumberUpdate,
  ): Promise<PhoneNumber | null> {
    return this.perform(async () => this.service.updatePhoneNumber(id, input));
  }

  async remove(id: string): Promise<boolean> {
    if (this.isActing) return false;
    this.isActing = true;
    this.actionErrorMessage = null;
    try {
      await this.service.deletePhoneNumber(id);
      runInAction(() => {
        this.items = this.items.filter((item) => item.id !== id);
        if (this.selectedNumber?.id === id) this.selectedNumber = null;
      });
      return true;
    } catch (error) {
      runInAction(() => {
        this.actionErrorMessage = message(
          error,
          "The phone number could not be removed from Eylo.",
        );
      });
      return false;
    } finally {
      runInAction(() => {
        this.isActing = false;
      });
    }
  }

  async search(configId: string, search: AvailableNumberSearch): Promise<void> {
    this.searchRequest?.abort();
    const request = new AbortController();
    this.searchRequest = request;
    this.isSearching = true;
    this.searchErrorMessage = null;
    this.availableNumbers = [];
    try {
      const numbers = await this.service.searchAvailableNumbers(
        configId,
        search,
        request.signal,
      );
      if (!request.signal.aborted && this.searchRequest === request) {
        runInAction(() => {
          this.availableNumbers = numbers;
        });
      }
    } catch (error) {
      if (!request.signal.aborted && this.searchRequest === request) {
        runInAction(() => {
          this.searchErrorMessage = message(
            error,
            "Available numbers could not be searched.",
          );
        });
      }
    } finally {
      if (this.searchRequest === request) {
        runInAction(() => {
          this.searchRequest = null;
          this.isSearching = false;
        });
      }
    }
  }

  async purchase(
    configId: string,
    input: NumberPurchase,
    idempotencyKey: string,
  ): Promise<PhoneNumber | null> {
    return this.perform(async () =>
      this.service.purchaseNumber(configId, input, idempotencyKey),
    );
  }

  clearSearch(): void {
    this.searchRequest?.abort();
    this.searchRequest = null;
    this.availableNumbers = [];
    this.searchErrorMessage = null;
    this.isSearching = false;
  }

  clearSelected(): void {
    this.selectedRequest?.abort();
    this.selectedRequest = null;
    this.selectedNumber = null;
    this.selectedErrorMessage = null;
    this.actionErrorMessage = null;
    this.isSelectedLoading = false;
  }

  private async perform(
    operation: () => Promise<PhoneNumber>,
  ): Promise<PhoneNumber | null> {
    if (this.isActing) return null;
    this.isActing = true;
    this.actionErrorMessage = null;
    try {
      const number = await operation();
      runInAction(() => {
        const existing = this.items.some((item) => item.id === number.id);
        this.items = existing
          ? this.items.map((item) => (item.id === number.id ? number : item))
          : [number, ...this.items];
        if (this.selectedNumber?.id === number.id) this.selectedNumber = number;
      });
      return number;
    } catch (error) {
      runInAction(() => {
        this.actionErrorMessage = message(
          error,
          "The phone number change failed.",
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

class TelephonyCallsStore {
  actionErrorMessage: string | null = null;
  collectionErrorMessage: string | null = null;
  deletionJob: DeletionJob | null = null;
  isActing = false;
  isCollectionLoading = false;
  isSelectedLoading = false;
  items: TelephonyCall[] = [];
  selectedErrorMessage: string | null = null;
  selectedCall: TelephonyCall | null = null;
  private collectionRequest: AbortController | null = null;
  private selectedRequest: AbortController | null = null;
  private readonly service: TelephonyService;

  constructor(service: TelephonyService) {
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

  async loadCollection(): Promise<void> {
    this.collectionRequest?.abort();
    const request = new AbortController();
    this.collectionRequest = request;
    this.isCollectionLoading = true;
    this.collectionErrorMessage = null;
    try {
      const items = await this.service.listCalls(request.signal);
      if (!request.signal.aborted && this.collectionRequest === request)
        runInAction(() => {
          this.items = items;
        });
    } catch (error) {
      if (!request.signal.aborted && this.collectionRequest === request)
        runInAction(() => {
          this.collectionErrorMessage = message(
            error,
            "Calls could not be loaded.",
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

  async loadSelected(id: string): Promise<void> {
    this.clearSelected();
    const request = new AbortController();
    this.selectedRequest = request;
    this.isSelectedLoading = true;
    try {
      const call = await this.service.getCall(id, request.signal);
      if (!request.signal.aborted && this.selectedRequest === request)
        runInAction(() => {
          this.selectedCall = call;
        });
    } catch (error) {
      if (!request.signal.aborted && this.selectedRequest === request)
        runInAction(() => {
          this.selectedErrorMessage = message(
            error,
            "This call could not be loaded.",
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

  async requestDeletion(id: string): Promise<boolean> {
    if (this.isActing) return false;
    this.isActing = true;
    this.actionErrorMessage = null;
    try {
      const job = await this.service.deleteCall(id);
      runInAction(() => {
        this.deletionJob = job;
      });
      return true;
    } catch (error) {
      runInAction(() => {
        this.actionErrorMessage = message(
          error,
          "Call deletion could not be requested.",
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
    this.selectedCall = null;
    this.selectedErrorMessage = null;
    this.actionErrorMessage = null;
    this.deletionJob = null;
    this.isSelectedLoading = false;
  }
}

class TelephonyStore {
  agents: TelephonyAgent[] = [];
  configs: TelephonyConfig[] = [];
  isReferencesLoading = false;
  readonly calls: TelephonyCallsStore;
  readonly numbers: PhoneNumbersStore;
  referenceErrorMessage: string | null = null;
  private readonly service: TelephonyService;

  constructor(service: TelephonyService) {
    this.service = service;
    this.calls = new TelephonyCallsStore(service);
    this.numbers = new PhoneNumbersStore(service);
    makeAutoObservable<this, "service">(
      this,
      { calls: false, numbers: false, service: false },
      { autoBind: true },
    );
  }

  async loadReferences(organizationId: string): Promise<void> {
    this.isReferencesLoading = true;
    this.referenceErrorMessage = null;
    try {
      const [configs, agents] = await Promise.all([
        this.service.listConfigs(),
        this.service.listAgents(organizationId),
      ]);
      runInAction(() => {
        this.configs = configs;
        this.agents = agents;
      });
    } catch (error) {
      runInAction(() => {
        this.referenceErrorMessage = message(
          error,
          "Telephony references could not be loaded.",
        );
      });
    } finally {
      runInAction(() => {
        this.isReferencesLoading = false;
      });
    }
  }

  agentName(id: string | null | undefined): string {
    if (id === null || id === undefined) return "Not assigned";
    return (
      this.agents.find((agent) => agent.id === id)?.name ??
      `Agent …${id.slice(-12)}`
    );
  }

  configName(id: string): string {
    return (
      this.configs.find((config) => config.id === id)?.name ??
      `Config …${id.slice(-12)}`
    );
  }
}

function message(error: unknown, fallback: string): string {
  return error instanceof TelephonyServiceError ? error.message : fallback;
}

export { TelephonyStore };
