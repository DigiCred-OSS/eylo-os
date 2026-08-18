import {
  getServerBaseUrl,
  getWidgetApiPrefix,
  getWidgetSessionHeaders,
  handleFetchError,
} from "@eylo/utils";

import type { TKnowledgeIngestion, TKnowledgeUploadCapability } from "./types";

type TCapabilityResponse = {
  allowed: boolean;
};

type TIngestionResponse = {
  id: string;
  document_id: string;
  state: string;
  title: string | null;
  source_uri: string | null;
  last_error: string | null;
};

const conversationKnowledgeUrl = (organizationId: string, conversationId: string): string =>
  `${getServerBaseUrl()}${getWidgetApiPrefix(organizationId, "conversations")}/${conversationId}/knowledgebases`;

export async function fetchKnowledgeUploadCapability(
  organizationId: string,
  conversationId: string,
  sessionId: string,
  userSessionId: string
): Promise<TKnowledgeUploadCapability> {
  const response = await fetch(`${conversationKnowledgeUrl(organizationId, conversationId)}/file-upload-capability`, {
    method: "GET",
    headers: {
      ...getWidgetSessionHeaders(sessionId),
      "X-Eylo-User-Session-ID": userSessionId,
    },
  });
  if (!response.ok) {
    await handleFetchError(response, "fetch Knowledge upload capability");
  }
  return (await response.json()) as TCapabilityResponse;
}

export async function uploadKnowledgeFile(
  organizationId: string,
  conversationId: string,
  file: File,
  sessionId: string,
  userSessionId: string
): Promise<TKnowledgeIngestion> {
  const response = await fetch(
    `${conversationKnowledgeUrl(organizationId, conversationId)}/files`,
    {
      method: "POST",
      headers: {
        ...getWidgetSessionHeaders(sessionId),
        "Content-Type": file.type || "application/octet-stream",
        "X-Eylo-Filename": encodeURIComponent(file.name),
        "X-Eylo-User-Session-ID": userSessionId,
      },
      body: file,
    }
  );
  if (!response.ok) {
    await handleFetchError(response, "upload Knowledge file");
  }
  return mapIngestion((await response.json()) as TIngestionResponse);
}

export async function fetchKnowledgeIngestion(
  organizationId: string,
  conversationId: string,
  jobId: string,
  sessionId: string,
  userSessionId: string
): Promise<TKnowledgeIngestion> {
  const response = await fetch(
    `${conversationKnowledgeUrl(organizationId, conversationId)}/ingestions/${jobId}`,
    {
      method: "GET",
      headers: {
        ...getWidgetSessionHeaders(sessionId),
        "X-Eylo-User-Session-ID": userSessionId,
      },
    }
  );
  if (!response.ok) {
    await handleFetchError(response, "fetch Knowledge ingestion status");
  }
  return mapIngestion((await response.json()) as TIngestionResponse);
}

function mapIngestion(payload: TIngestionResponse): TKnowledgeIngestion {
  return {
    jobId: payload.id,
    documentId: payload.document_id,
    state: payload.state,
    title: payload.title,
    sourceUri: payload.source_uri,
    lastError: payload.last_error,
  };
}
