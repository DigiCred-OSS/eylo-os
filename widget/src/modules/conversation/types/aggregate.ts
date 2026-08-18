import type { TAgent } from "../../agent/types";
import type { TContact } from "../../contact/types";
import type { TMessage } from "../../message/types";
import type { TParticipant } from "../../participant/types";

/**
 * Contact summary from aggregate response
 */
export type TContactSummary = {
  id: string;
  name: string | null;
  primaryEmail: string | null;
  primaryPhone: string | null;
};

/**
 * Agent summary from aggregate response
 */
export type TAgentSummary = {
  id: string;
  name: string;
  slug: string;
  status: string;
};

/**
 * Participant summary from aggregate response with resolved entity info
 */
export type TParticipantSummary = {
  id: string;
  entityKind: "AGENT" | "CONTACT" | "MEMBER";
  entityId: string;
  hasInitiated: boolean;
  isActive: boolean;
  isPrimary: boolean;
  joinedAt: Date | string;
  leftAt: Date | string | null;
  entityName: string | null;
};

/**
 * Message summary from aggregate response
 */
export type TMessageSummary = {
  id: string;
  kind: string;
  contentKind: string;
  content: Record<string, any>;
  htmlContent: string;
  senderParticipantId: string;
  senderKind: "AGENT" | "CONTACT" | "MEMBER" | null;
  requestId: string | null;
  requestFeedback: string | null;
  createdAt: Date | string;
};

/**
 * Conversation aggregate response from backend
 * Contains conversation with all related data (contacts, agents, messages, participants)
 */
export type TConversationAggregate = {
  id: string;
  organizationId: string;
  channel: string;
  status: string;
  title: string | null;
  endedAt: Date | string | null;
  meta: Record<string, any> | null;
  createdAt: Date | string;
  updatedAt: Date | string;
  contact: TContactSummary | null;
  primaryAgent: TAgentSummary | null;
  allAgents: TAgentSummary[];
  participants: TParticipantSummary[];
  messages: TMessageSummary[];
  messageCount: number;
  unreadCount: number;
};

/**
 * Converts aggregate summary to full types for storage
 */
export type AggregateConversionHelpers = {
  contactSummaryToContact: (summary: TContactSummary) => TContact;
  agentSummaryToAgent: (summary: TAgentSummary) => TAgent;
  participantSummaryToParticipant: (summary: TParticipantSummary) => TParticipant;
  messageSummaryToMessage: (summary: TMessageSummary, conversationId: string) => TMessage;
};
