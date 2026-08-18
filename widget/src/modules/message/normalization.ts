import {
  type TCompoundWidgetPayload,
  type TWidgetPayloadEnvelope,
  type TWidgetValidationResult,
  isCompoundWidgetPayload,
  validateCompoundWidgetPayload,
  validateWidgetPayload,
} from "../interface";
import { isRecord } from "@eylo/utils/type-guards";
import type { TMessage, TMessageWidgetMeta } from "./types";

const getWidgetPayloadCandidate = (message: TMessage): unknown => {
  if (!isRecord(message.content)) {
    return undefined;
  }

  // Single-component payload: { component, props }
  if ("component" in message.content && "props" in message.content) {
    return message.content;
  }

  // Compound payload: { components, root }
  if ("components" in message.content && "root" in message.content) {
    return message.content;
  }

  // Wrapped in { role, content: ... }
  if ("content" in message.content) {
    const inner = message.content.content;
    if (isRecord(inner)) {
      if ("component" in inner && "props" in inner) return inner;
      if ("components" in inner && "root" in inner) return inner;
    }
    return inner;
  }

  return undefined;
};

export const getWidgetPayloadValidation = (
  message: TMessage
): TWidgetValidationResult<TWidgetPayloadEnvelope | TCompoundWidgetPayload> => {
  if (message.contentKind !== "WIDGET") {
    return {
      ok: false,
      issues: [{ path: "$.contentKind", message: "Message is not a widget payload." }],
    };
  }

  const candidate = getWidgetPayloadCandidate(message);

  // Try compound validation first if it looks like a compound payload
  if (isCompoundWidgetPayload(candidate)) {
    return validateCompoundWidgetPayload(candidate);
  }

  // Fall back to single-component validation
  return validateWidgetPayload(candidate);
};

export const normalizeIncomingMessage = (message: TMessage): TMessage => {
  if (message.contentKind !== "WIDGET") {
    return message;
  }

  const validation = getWidgetPayloadValidation(message);
  const widgetMeta: TMessageWidgetMeta = validation.ok
    ? {
        widgetPayload: validation.value,
        widgetPayloadIssues: [],
      }
    : {
        widgetPayloadIssues: validation.issues,
      };

  return {
    ...message,
    meta: {
      ...(message.meta ?? {}),
      ...widgetMeta,
    },
    content: validation.ok
      ? {
          role: "assistant",
          content: validation.value,
        }
      : message.content,
  };
};
