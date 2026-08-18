import type { TContact } from "../contact";
import type { TCompoundWidgetPayload, TWidgetPayloadEnvelope, TWidgetValidationIssue } from "../interface";
import type { TParticipant } from "../participant";

type TMessageKind = "USER" | "SYSTEM" | "ASSISTANT" | "TOOL_USE" | "TOOL_RESULT";

type TMessageContentKind =
  | "TEXT"
  | "IMAGE"
  | "VIDEO"
  | "AUDIO"
  | "TOOL"
  | "TOOL_RESULT"
  | "WIDGET"
  | "WIDGET_RESPONSE";

// Content block types
type TTextContent = {
  type: "text";
  text: string;
};

type TImageUrlContent = {
  type: "image_url";
  image_url: {
    url: string;
  };
};

type TTextMessageContentBlock = TTextContent | TImageUrlContent;

type TToolUseContent = {
  type: "tool_use";
  id: string;
  name: string;
  input: Record<string, unknown>;
};

type TToolResultContent = {
  type: "tool_result";
  tool_use_id: string;
  content: string | Array<TTextMessageContentBlock>;
  is_error?: boolean;
};

// Message content types based on Python schemas
type TUserMessageContent = {
  role: "user";
  content: TTextMessageContentBlock[];
};

type TAssistantMessageContent = {
  role: "assistant";
  content: TTextMessageContentBlock[];
};

type TToolUseMessageContent = {
  role: "assistant";
  content: TToolUseContent;
};

type TToolResultMessageContent = {
  role: "user";
  content: TToolResultContent[];
};

type TSystemMessageContent = {
  role: "system";
  content: TTextMessageContentBlock[];
};

type TWidgetMessageContent = {
  role: "assistant";
  content: TWidgetPayloadEnvelope | TCompoundWidgetPayload;
};

type TWidgetResponseData = {
  type: "widget_response";
  widget_message_id: string;
  component: string;
  action?: string;
  data: Record<string, unknown>;
};

type TWidgetResponseMessageContent = {
  role: "user";
  content: TWidgetResponseData;
};

type TMessageContent =
  | TUserMessageContent
  | TAssistantMessageContent
  | TToolUseMessageContent
  | TToolResultMessageContent
  | TSystemMessageContent
  | TWidgetMessageContent
  | TWidgetResponseMessageContent;

type TMessageWidgetMeta = {
  widgetPayload?: TWidgetPayloadEnvelope | TCompoundWidgetPayload;
  widgetPayloadIssues?: TWidgetValidationIssue[];
};

type TMessage = {
  id: string;
  conversationId: string;
  senderParticipantId: string;
  kind: TMessageKind;
  contentKind: TMessageContentKind;
  content: TMessageContent | Record<string, unknown>;
  htmlContent?: string;
  parentMessageId?: string;
  meta?: Record<string, unknown> & TMessageWidgetMeta;
  externalId?: string;
  requestId?: string;
  requestFeedback?: string;
  createdAt: Date;
};

type TMessageWParticipant = TMessage & {
  senderParticipant?: TParticipant;
  contact?: TContact;
};

type TMessageCreate = {
  conversationId: string;
  text: string;
  context?: Record<string, unknown>;
};

type TWidgetResponseMessageCreate = {
  conversationId: string;
  widgetMessageId: string;
  component: string;
  action: string;
  data: Record<string, unknown>;
};

export type {
  TAssistantMessageContent,
  TImageUrlContent,
  TMessage,
  TMessageContent,
  TMessageContentKind,
  TMessageCreate,
  TMessageKind, TMessageWidgetMeta, TMessageWParticipant,
  TSystemMessageContent,
  TTextMessageContentBlock,
  TTextContent,
  TToolResultContent,
  TToolResultMessageContent,
  TToolUseContent,
  TToolUseMessageContent,
  TUserMessageContent,
  TWidgetMessageContent, TWidgetResponseData,
  TWidgetResponseMessageContent, TWidgetResponseMessageCreate
};
