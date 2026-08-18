import type { TMessageWParticipant } from "../message/types";

export type TEyloBaseEntity = {
  externalId: string;
  organizationId: string;
};

export type TConversationChannel = "PHONE" | "CHAT" | "WEB" | "WIDGET" | "SMS" | "API";
export const ConversationChannels = {
  PHONE: "PHONE" as TConversationChannel,
  CHAT: "CHAT" as TConversationChannel,
  WEB: "WEB" as TConversationChannel,
  WIDGET: "WIDGET" as TConversationChannel,
  SMS: "SMS" as TConversationChannel,
  API: "API" as TConversationChannel,
};

export type TConversationStatus = "ACTIVE" | "COMPLETED" | "ABANDONED";
export const ConversationStatus = {
  ACTIVE: "ACTIVE" as TConversationStatus,
  COMPLETED: "COMPLETED" as TConversationStatus,
  ABANDONED: "ABANDONED" as TConversationStatus,
};

export type TConversation = TEyloBaseEntity & {
  id: string;
  status: TConversationStatus;
  channel: TConversationChannel;
  endedAt?: Date | null;
  meta?: Record<string, any> | null;
  title: string;
  messageCount?: number; // Total number of messages in conversation
  unreadCount?: number;
  createdAt: Date;
  updatedAt: Date;
};

export type TConversationCreate = {
  from: {
    kind: "CONTACT" | "AGENT";
    id?: string;
    externalId?: string;
  };
  to: {
    kind: "CONTACT" | "AGENT";
    id?: string;
    externalId?: string;
  };
  message: {
    content: Array<{
      kind: "TEXT";
      value: string;
    }>;
  };
  context?: Record<string, any>;
  externalId?: string;
  channel?: TConversationChannel;
};

export type TConversationContext = {
  conversation: TConversation;
  messages: Array<TMessageWParticipant>;
};

export type TConversationMessagePage = {
  conversationId: string;
  messages: Array<TMessageWParticipant>;
  totalMessageCount: number;
};

// Re-export aggregate types
export type {
  TAgentSummary,
  TContactSummary,
  TConversationAggregate,
  TMessageSummary,
  TParticipantSummary,
} from "./types/aggregate";
