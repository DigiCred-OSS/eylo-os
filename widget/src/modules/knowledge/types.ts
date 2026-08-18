export type TKnowledgeUploadCapability = {
  allowed: boolean;
};

export type TKnowledgeIngestion = {
  jobId: string;
  documentId: string;
  state: string;
  title: string | null;
  sourceUri: string | null;
  lastError: string | null;
};
