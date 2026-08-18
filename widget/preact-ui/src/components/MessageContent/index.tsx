// components/MessageContent/index.tsx
import type { FC } from "preact/compat";
import { cm } from "../../design-system/utils";
import styles from "./MessageContent.module.css";

interface MessageContentProps {
  content: string;
  className?: string;
}

/**
 * Component that renders message content as HTML
 *
 * Simple wrapper around dangerouslySetInnerHTML for message rendering
 * Includes beautiful typography styling for lists, headings, code, etc.
 */
const MessageContent: FC<MessageContentProps> = ({ content, className = "" }) => {
  return (
    <div
      className={cm(styles.messageContent, className)}
      dangerouslySetInnerHTML={{ __html: content }}
    />
  );
};

export default MessageContent;
