import { Agent } from "../../agent/model";
import type { TAgent } from "../../agent/types";
import { Contact } from "../../contact/model";
import type { TContact } from "../../contact/types";
import { Message } from "../../message/model";
import type { TMessage } from "../../message/types";
import { normalizeIncomingMessage } from "../../message/normalization";
import { Participant } from "../../participant/model";
import type { TParticipant } from "../../participant/types";
import type {
  TAgentSummary,
  TContactSummary,
  TMessageSummary,
  TParticipantSummary,
} from "../types/aggregate";

/**
 * Converts aggregate summary objects to full domain objects for storage
 */
export class AggregateConverter {
  /**
   * Convert ContactSummary to TContact
   */
  static contactSummaryToContact(summary: TContactSummary): Contact {
    return new Contact({
      id: summary.id,
      name: summary.name || "",
      primaryEmail: summary.primaryEmail,
      primaryPhone: summary.primaryPhone,
      externalId: undefined, // Not included in summary
      preferences: {}, // Not included in summary
    } as TContact);
  }

  /**
   * Convert AgentSummary to TAgent
   */
  static agentSummaryToAgent(summary: TAgentSummary): Agent {
    return new Agent({
      id: summary.id,
      name: summary.name,
      status: summary.status,
      externalId: summary.slug, // Using slug as externalId
    } as TAgent);
  }

  /**
   * Convert ParticipantSummary to TParticipant
   */
  static participantSummaryToParticipant(
    summary: TParticipantSummary,
    conversationId: string
  ): Participant {
    return new Participant({
      id: summary.id,
      entityKind: summary.entityKind,
      entityId: summary.entityId,
      hasInitiated: summary.hasInitiated,
      isActive: summary.isActive,
      joinedAt:
        typeof summary.joinedAt === "string" ? new Date(summary.joinedAt) : summary.joinedAt,
      leftAt: summary.leftAt
        ? typeof summary.leftAt === "string"
          ? new Date(summary.leftAt)
          : summary.leftAt
        : undefined,
      conversationId,
    } as TParticipant);
  }

  /**
   * Convert MessageSummary to TMessage
   */
  static messageSummaryToMessage(summary: TMessageSummary, conversationId: string): Message {
    return new Message(
      normalizeIncomingMessage({
      id: summary.id,
      conversationId,
      senderParticipantId: summary.senderParticipantId,
      kind: summary.kind as any,
      contentKind: summary.contentKind as any,
      content: summary.content,
      htmlContent: summary.htmlContent,
      createdAt:
        typeof summary.createdAt === "string" ? new Date(summary.createdAt) : summary.createdAt,
      meta: {},
      externalId: undefined,
      parentMessageId: undefined,
      requestId: summary.requestId || undefined,
      requestFeedback: summary.requestFeedback || undefined,
      } as TMessage)
    );
  }
}
