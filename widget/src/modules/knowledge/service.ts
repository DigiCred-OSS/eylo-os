import type { EyloStore } from "@eylo/store";

import {
  fetchKnowledgeIngestion,
  fetchKnowledgeUploadCapability,
  uploadKnowledgeFile,
} from "./http";
import type { TKnowledgeIngestion, TKnowledgeUploadCapability } from "./types";

export class KnowledgeService {
  private readonly store: EyloStore;

  constructor(store: EyloStore) {
    this.store = store;
  }

  public getUploadCapability(
    conversationId: string
  ): Promise<TKnowledgeUploadCapability> {
    const { organizationId, sessionId, userSessionId } = this.authority();
    return fetchKnowledgeUploadCapability(
      organizationId,
      conversationId,
      sessionId,
      userSessionId
    );
  }

  public uploadFile(
    conversationId: string,
    file: File
  ): Promise<TKnowledgeIngestion> {
    const { organizationId, sessionId, userSessionId } = this.authority();
    return uploadKnowledgeFile(
      organizationId,
      conversationId,
      file,
      sessionId,
      userSessionId
    );
  }

  public getIngestion(
    conversationId: string,
    jobId: string
  ): Promise<TKnowledgeIngestion> {
    const { organizationId, sessionId, userSessionId } = this.authority();
    return fetchKnowledgeIngestion(
      organizationId,
      conversationId,
      jobId,
      sessionId,
      userSessionId
    );
  }

  private authority(): {
    organizationId: string;
    sessionId: string;
    userSessionId: string;
  } {
    const organizationId = this.store.organizationId;
    const sessionId = this.store.sessionId;
    const userSessionId = this.store.userSessionId;
    if (!organizationId || !sessionId || !userSessionId) {
      throw new Error("An active widget session is required for Knowledge files.");
    }
    return { organizationId, sessionId, userSessionId };
  }
}
