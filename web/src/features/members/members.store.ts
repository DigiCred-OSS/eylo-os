import { makeAutoObservable, runInAction } from "mobx";

import { MembersService } from "@/features/members/members.service";
import type {
  Member,
  MemberCollectionQuery,
} from "@/features/members/members.types";

class MembersStore {
  collectionErrorMessage: string | null = null;
  hasMore = false;
  isCollectionLoading = false;
  isSelectedLoading = false;
  items: Member[] = [];
  limit = 20;
  page = 1;
  selectedErrorMessage: string | null = null;
  selectedMember: Member | null = null;
  total = 0;

  private collectionRequest: AbortController | null = null;
  private selectedRequest: AbortController | null = null;
  private readonly service: MembersService;

  constructor(service: MembersService) {
    this.service = service;
    makeAutoObservable<
      this,
      "collectionRequest" | "selectedRequest" | "service"
    >(
      this,
      {
        collectionRequest: false,
        selectedRequest: false,
        service: false,
      },
      { autoBind: true },
    );
  }

  async loadCollection(
    organizationId: string,
    query: MemberCollectionQuery,
  ): Promise<void> {
    this.collectionRequest?.abort();
    const request = new AbortController();
    this.collectionRequest = request;
    this.collectionErrorMessage = null;
    this.isCollectionLoading = true;
    try {
      const page = await this.service.listMembers(
        organizationId,
        query,
        request.signal,
      );
      if (request.signal.aborted) return;
      runInAction(() => {
        this.hasMore = page.hasMore === true;
        this.items = page.data;
        this.limit = page.limit;
        this.page = page.page;
        this.total = page.total ?? page.data.length;
      });
    } catch {
      if (!request.signal.aborted) {
        runInAction(() => {
          this.collectionErrorMessage =
            "Members could not be loaded. Check the API connection and try again.";
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

  async loadSelected(organizationId: string, memberId: string): Promise<void> {
    this.selectedRequest?.abort();
    const request = new AbortController();
    this.selectedRequest = request;
    this.selectedMember =
      this.items.find((member) => member.id === memberId) ?? null;
    this.selectedErrorMessage = null;
    this.isSelectedLoading = true;
    try {
      const member = await this.service.getMember(
        organizationId,
        memberId,
        request.signal,
      );
      if (request.signal.aborted) return;
      runInAction(() => {
        this.selectedMember = member;
      });
    } catch {
      if (!request.signal.aborted) {
        runInAction(() => {
          this.selectedMember = null;
          this.selectedErrorMessage =
            "This member could not be loaded. It may no longer exist.";
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
    this.selectedMember = null;
    this.selectedErrorMessage = null;
    this.isSelectedLoading = false;
  }
}

export { MembersStore };
