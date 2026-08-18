import type { JSX } from "preact/compat";
import { forwardRef } from "preact/compat";
import styles from "./ChatContent.module.css";

export interface MessageProps {
  content: string;
  sender: "user" | "bot";
  timestamp?: Date;
  avatar?: string;
  status?: "sent" | "delivered" | "read" | "error";
}

interface ChatContentProps extends JSX.HTMLAttributes<HTMLDivElement> {
  messages?: MessageProps[];
}

// Subcomponent for individual message display
const Message = ({ message }: { message: MessageProps }) => {
  const isUser = message.sender === "user";
  const time = message.timestamp
    ? new Date(message.timestamp).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      })
    : "";

  return (
    <div
      className={`${styles.messageWrapper} ${isUser ? styles.userMessageWrapper : styles.botMessageWrapper}`}
    >
      <div className={isUser ? styles.userMessage : styles.botMessage}>{message.content}</div>
      {time && <div className={styles.timestamp}>{time}</div>}
    </div>
  );
};

const ChatContent = forwardRef<HTMLDivElement, ChatContentProps>(
  ({ children, messages, className, ...props }, ref) => {
    return (
      <div
        id="ew-chat-content"
        {...props}
        ref={ref}
        className={`${styles.content} ${className || ""}`}
      >
        {messages?.map((message, index) => (
          <Message key={index} message={message} />
        ))}
        {children}
      </div>
    );
  }
);

export default ChatContent;
