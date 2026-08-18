import type { FC, JSX } from "preact/compat";
import { useState, useRef } from "preact/hooks";
import MessageInput from "../MessageInput";

interface ChatFooterProps {
  children?: JSX.Element | JSX.Element[];
  onSendMessage?: (message: string) => void;
  placeholder?: string;
  disabled?: boolean;
}

const ChatFooter: FC<ChatFooterProps> = ({
  children,
  onSendMessage,
  placeholder = "Type a message...",
  disabled = false,
}) => {
  const [message, setMessage] = useState("");
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  const handleSendMessage = () => {
    const trimmedMessage = message.trim();

    if (!trimmedMessage || !onSendMessage) return;

    onSendMessage(trimmedMessage);
    setMessage("");

    // Reset textarea height after sending
    if (inputRef.current) {
      inputRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // If children are provided, use them; otherwise render default MessageInput
  const content = children || (
    <MessageInput
      disabled={disabled}
      inputRef={inputRef}
      value={message}
      onChange={setMessage}
      onSend={handleSendMessage}
      onKeyDown={handleKeyDown}
      placeholder={placeholder}
    />
  );

  return (
    <div id="ew-chat-footer">
      <div className="container">{content}</div>
    </div>
  );
};

export default ChatFooter;
