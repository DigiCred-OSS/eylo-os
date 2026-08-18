import { EYLO_EVENTS } from "@eylo/events";
import type { TWsMessage } from "@eylo/net";
import { WS_ACTIONS } from "@eylo/net/constants";
import type { EyloStore } from "@eylo/store";
import { logger } from "@eylo/utils";
import { isRecord } from "@eylo/utils/type-guards";

import type { ConversationStore } from "../conversation";
import type { TCompoundWidgetPayload, TWidgetPayloadEnvelope, TWidgetValidationResult } from "../interface";
import { ParticipantService } from "../participant/service";
import { Message } from "./model";
import { getWidgetPayloadValidation, normalizeIncomingMessage } from "./normalization";
import type { MessageStore } from "./store";
import type {
  TAssistantMessageContent,
  TMessage,
  TMessageCreate,
  TMessageWParticipant,
  TSystemMessageContent,
  TTextContent,
  TToolResultMessageContent,
  TToolUseMessageContent,
  TUserMessageContent,
  TWidgetResponseData,
  TWidgetResponseMessageCreate,
} from "./types";

// let _instance: MessageService | undefined = undefined;

class MessageService {
  private static _instance: MessageService | undefined = undefined;
  // @ts-ignore
  private _eyloStore: EyloStore;
  // @ts-ignore
  private _messageStore: MessageStore;
  // @ts-ignore
  private _conversationStore: ConversationStore;
  constructor(eyloStore: EyloStore) {
    if (!MessageService._instance) {
      this._eyloStore = eyloStore;
      this._conversationStore = this._eyloStore.conversationStore;
      this._messageStore = this._conversationStore.messageStore;
      this._installHandlers();
      MessageService._instance = this;
    }
    return MessageService._instance;
  }

  private _messageCreatedHandler = () => {
    this._eyloStore.cm.registerMessageHandler(WS_ACTIONS.MESSAGE_CREATED, (message) => {
      if (message.data) {
        const newMessage = new Message(normalizeIncomingMessage(message.data as TMessage));
        const replacedTransient = this._removeMatchingTransient(newMessage);
        const isNewMessage = !this._messageStore.get_(newMessage.id);
        this._messageStore.add_(newMessage);
        if (!isNewMessage) {
          return;
        }
        if (!replacedTransient) {
          this._recordMessageActivity(newMessage);
        }
        this._eyloStore.ee.emit(EYLO_EVENTS.MESSAGE_CREATED, newMessage);
      } else {
        logger.warn("Received message created without data.");
      }
    });
  };

  private _messageTranscriptHandler = () => {
    this._eyloStore.cm.registerMessageHandler(WS_ACTIONS.MESSAGE_TRANSCRIPT, (message) => {
      if (!message.data) {
        logger.warn("Received live transcript without data.");
        return;
      }
      const transcript = new Message(normalizeIncomingMessage(message.data as TMessage));
      if (
        transcript.meta?.transient !== true ||
        (transcript.kind !== "USER" && transcript.kind !== "ASSISTANT") ||
        !transcript.externalId
      ) {
        logger.warn("Ignored an invalid live transcript projection.");
        return;
      }

      const existing = this._messageStore.get_byExternalId(transcript.externalId);
      const isNewLogicalMessage = !existing;
      if (existing) {
        // A committed, redacted message always wins over a delayed raw delta.
        if (existing.meta?.transient !== true) {
          return;
        }
        this._messageStore.delete_(existing.id);
      }
      this._messageStore.add_(transcript);
      if (isNewLogicalMessage) {
        this._recordMessageActivity(transcript);
      }
      this._eyloStore.ee.emit(EYLO_EVENTS.MESSAGE_TRANSCRIPT, transcript);
    });
  };

  private _messageQueryHandler = () => {
    const _handler = (message: TWsMessage) => {
      if (message.data) {
        message.data.forEach((m: TMessage) => {
          const normalizedMessage = new Message(normalizeIncomingMessage(m));
          this._messageStore.add_(normalizedMessage);
          this._eyloStore.ee.emit(EYLO_EVENTS.MESSAGE_CREATED, normalizedMessage);
        });
      } else {
        logger.warn("Received conversation updated message without data.");
      }
    };
    this._eyloStore.cm.registerMessageHandler(WS_ACTIONS.MESSAGE_QUERY, _handler);
  };

  private _messageFeedbackHandler = () => {
    this._eyloStore.cm.registerMessageHandler(WS_ACTIONS.MESSAGE_FEEDBACK, (message) => {
      if (!message.data) {
        logger.warn("Received message feedback acknowledgement without data.");
        return;
      }

      const updatedMessage = new Message(
        normalizeIncomingMessage(message.data as TMessage)
      );
      if (this._messageStore.get_(updatedMessage.id)) {
        this._messageStore.update_(updatedMessage);
      } else {
        this._messageStore.add_(updatedMessage);
      }
      this._eyloStore.ee.emit(EYLO_EVENTS.MESSAGE_FEEDBACK, updatedMessage);
    });
  };

  private _installHandlers = (): void => {
    this._messageCreatedHandler();
    this._messageTranscriptHandler();
    this._messageQueryHandler();
    this._messageFeedbackHandler();
  };

  private _removeMatchingTransient = (message: Message): boolean => {
    if (!message.externalId) {
      return false;
    }
    const existing = this._messageStore.get_byExternalId(message.externalId);
    if (
      !existing ||
      existing.id === message.id ||
      existing.meta?.transient !== true
    ) {
      return false;
    }
    this._messageStore.delete_(existing.id);
    return true;
  };

  private _recordMessageActivity = (message: Message): void => {
    const conversation = this._conversationStore.get_(message.conversationId);
    if (!conversation) {
      logger.debug(
        `Conversation with ID ${message.conversationId} is not hydrated for message activity.`
      );
      return;
    }
    this._conversationStore.recordMessageActivity(
      message.conversationId,
      message.createdAt,
      message.kind === "ASSISTANT"
    );
  };

  public sendMessage = (data: TMessageCreate, requestId: string): boolean => {
    const message = {
      text: data.text,
      conversationId: data.conversationId,
      ...(data.context && { context: data.context }),
    } as TMessageCreate;

    return this._eyloStore.cm.send({
      kind: WS_ACTIONS.MESSAGE_CREATED,
      data: message,
      requestId,
    } as TWsMessage);
  };

  public sendWidgetResponse = (
    data: TWidgetResponseMessageCreate,
    requestId: string
  ): boolean => {
    return this._eyloStore.cm.send({
      kind: WS_ACTIONS.MESSAGE_CREATED,
      data: {
        conversationId: data.conversationId,
        parentMessageId: data.widgetMessageId,
        contentKind: "WIDGET_RESPONSE",
        content: {
          role: "user",
          content: {
            type: "widget_response",
            widget_message_id: data.widgetMessageId,
            component: data.component,
            action: data.action,
            data: data.data,
          },
        },
      },
      requestId,
    } as TWsMessage);
  };

  public sendFeedback = (
    conversationId: string,
    requestId: string,
    feedback: "positive" | "negative"
  ) => {
    return this._eyloStore.cm.send({
      kind: WS_ACTIONS.MESSAGE_FEEDBACK,
      data: {
        conversationId,
        messageRequestId: requestId,
        requestFeedback: feedback,
      },
    } as TWsMessage);
  };

  private _resolveParticipant = (participantId: string) => {
    const participant = this._eyloStore.participantStore.get_(participantId);
    if (!participant) {
      logger.debug(`Participant with ID ${participantId} is not hydrated.`);
      return {
        participant: undefined,
        contact: undefined,
      };
    }
    const agentOrContact = new ParticipantService(this._eyloStore).resolveParticipant_byID(
      participantId
    );
    return {
      participant,
      contact: agentOrContact,
    };
  };

  private _model_to_type = (message: Message): TMessage => {
    return {
      id: message.id,
      externalId: message.externalId,
      content: message.content,
      htmlContent: message.htmlContent,
      contentKind: message.contentKind,
      kind: message.kind,
      conversationId: message.conversationId,
      senderParticipantId: message.senderParticipantId,
      parentMessageId: message.parentMessageId,
      meta: message.meta,
      requestId: message.requestId,
      requestFeedback: message.requestFeedback,
      createdAt: message.createdAt,
    } as TMessage;
  };

  public resolveMessage_byId = (messageId: string): TMessageWParticipant | undefined => {
    const message = this._messageStore.get_(messageId);
    if (!message) {
      this._eyloStore.cm.send({
        kind: WS_ACTIONS.MESSAGE_QUERY,
        data: {
          filters: {
            messageIds: [messageId],
          },
        },
        requestId: messageId,
      } as TWsMessage);
      logger.warn(`Message with ID ${messageId} not found.`);
      return;
    }
    const { participant, contact } = this._resolveParticipant(message.senderParticipantId);
    return {
      ...this._model_to_type(message),
      senderParticipant: participant,
      contact,
    };
  };

  public resolveMessage(message: Message): TMessageWParticipant {
    const { participant, contact } = this._resolveParticipant(message.senderParticipantId);
    return {
      ...this._model_to_type(message),
      senderParticipant: participant,
      contact,
    };
  }

  public resolve_byConversationId(conversationId: string): Array<TMessageWParticipant> {
    const messages: Array<Message> = this._messageStore.list_();
    return messages
      .filter((message) => message.conversationId === conversationId)
      .sort((a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime())
      .map((message) => this.resolveMessage(message));
  }

  /**
   * Utility method to extract readable text content from a message
   * Handles different message content structures (USER, ASSISTANT, SYSTEM, TOOL_USE, TOOL_RESULT)
   * @param message - The message object to extract content from
   * @returns A string representation of the message content
   */
  public getMessageContent(message: TMessage): string {
    // Handle null/undefined content
    if (!message.content) {
      return "No content";
    }

    if (message.htmlContent) {
      return message.htmlContent;
    }

    const content = message.content;

    try {
      if (message.contentKind === "WIDGET") {
        const widgetValidation = this.getWidgetPayload(message);
        return widgetValidation.ok ? "[Interactive widget]" : "Invalid widget payload";
      }

      if (message.contentKind === "WIDGET_RESPONSE") {
        const widgetResponse = this.getWidgetResponseData(message);
        if (widgetResponse) {
          const actionSuffix = widgetResponse.action ? `: ${widgetResponse.action}` : "";
          return `Widget response submitted (${widgetResponse.component}${actionSuffix})`;
        }
        return "Widget response submitted";
      }

      switch (message.kind) {
        case "USER": {
          const userContent = content as TUserMessageContent;
          if (Array.isArray(userContent.content)) {
            return userContent.content
              .filter((block): block is TTextContent => block.type === "text")
              .map((block) => block.text)
              .join(" ");
          }
          return "No content";
        }

        case "ASSISTANT": {
          const assistantContent = content as TAssistantMessageContent;
          if (Array.isArray(assistantContent.content)) {
            return assistantContent.content
              .filter((block): block is TTextContent => block.type === "text")
              .map((block) => block.text)
              .join(" ");
          }
          return "No content";
        }

        case "TOOL_USE": {
          const toolUseContent = content as TToolUseMessageContent;
          if (toolUseContent.content && toolUseContent.content.type === "tool_use") {
            return JSON.stringify(toolUseContent.content, null, 2);
          }
          return "Tool use";
        }

        case "TOOL_RESULT": {
          const toolResultContent = content as TToolResultMessageContent;
          if (Array.isArray(toolResultContent.content) && toolResultContent.content.length > 0) {
            return JSON.stringify(toolResultContent.content, null, 2);
          }
          return "Tool result";
        }

        case "SYSTEM": {
          const systemContent = content as TSystemMessageContent;
          if (Array.isArray(systemContent.content)) {
            return systemContent.content
              .filter((block): block is TTextContent => block.type === "text")
              .map((block) => block.text)
              .join(" ");
          }
          return "System message";
        }

        default:
          return "Unknown message type";
      }
    } catch (error) {
      console.error("Error parsing message content:", error);
      return "Error displaying message";
    }
  }

  /**
   * Strip HTML tags from a string
   */
  private stripHtml(html: string): string {
    // Create a temporary div element to parse HTML
    const tmp = document.createElement("div");
    tmp.innerHTML = html;
    return tmp.textContent || tmp.innerText || "";
  }

  /**
   * Get plain text content from a message, stripping HTML from USER and ASSISTANT messages
   * @param message - The message object to extract content from
   * @returns Plain text string
   */
  public getMessageContentPlainText(message: TMessage): string {
    // Handle null/undefined content
    if (!message.content) {
      return "No content";
    }

    const content = message.content;

    try {
      if (message.contentKind === "WIDGET") {
        const widgetValidation = this.getWidgetPayload(message);
        return widgetValidation.ok ? "[Interactive widget]" : "Invalid widget payload";
      }

      if (message.contentKind === "WIDGET_RESPONSE") {
        return this.getMessageContent(message);
      }

      switch (message.kind) {
        case "USER": {
          const userContent = content as TUserMessageContent;
          if (Array.isArray(userContent.content)) {
            return userContent.content
              .filter((block): block is TTextContent => block.type === "text")
              .map((block) => this.stripHtml(block.text))
              .join(" ");
          }
          return "No content";
        }

        case "ASSISTANT": {
          const assistantContent = content as TAssistantMessageContent;
          if (Array.isArray(assistantContent.content)) {
            return assistantContent.content
              .filter((block): block is TTextContent => block.type === "text")
              .map((block) => this.stripHtml(block.text))
              .join(" ");
          }
          return "No content";
        }

        // For other message types, use the existing getMessageContent method
        case "TOOL_USE":
        case "TOOL_RESULT":
        case "SYSTEM":
        default:
          return this.getMessageContent(message);
      }
    } catch (error) {
      console.error("Error parsing message content:", error);
      return "Error displaying message";
    }
  }

  public getWidgetPayload = (
    message: TMessage
  ): TWidgetValidationResult<TWidgetPayloadEnvelope | TCompoundWidgetPayload> => {
    if (message.contentKind !== "WIDGET") {
      return {
        ok: false,
        issues: [{ path: "$.contentKind", message: "Message is not a widget payload." }],
      };
    }

    const metaPayload = message.meta?.widgetPayload;
    if (metaPayload) {
      return {
        ok: true,
        value: metaPayload,
        issues: [],
      };
    }

    const metaIssues = message.meta?.widgetPayloadIssues;
    if (metaIssues && metaIssues.length > 0) {
      return {
        ok: false,
        issues: metaIssues,
      };
    }

    return getWidgetPayloadValidation(message);
  };

  public getWidgetResponseData(message: TMessage): TWidgetResponseData | null {
    if (message.contentKind !== "WIDGET_RESPONSE" || !isRecord(message.content)) {
      return null;
    }

    const candidate = isRecord(message.content.content) ? message.content.content : message.content;
    if (!isRecord(candidate)) {
      return null;
    }

    const candidateRecord: Record<string, unknown> = candidate;

    if (
      typeof candidateRecord.widget_message_id !== "string" ||
      typeof candidateRecord.component !== "string" ||
      !isRecord(candidateRecord.data)
    ) {
      return null;
    }

    return {
      type: "widget_response",
      widget_message_id: candidateRecord.widget_message_id,
      component: candidateRecord.component,
      action: typeof candidateRecord.action === "string" ? candidateRecord.action : undefined,
      data: candidateRecord.data,
    };
  }
}

export { MessageService };
