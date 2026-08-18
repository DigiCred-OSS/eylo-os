import type { FC } from "preact/compat";
import type { RefObject } from "preact";
import { useEffect, useRef } from "preact/hooks";
import { FaMicrophone, FaPaperclip } from "react-icons/fa";
import SendIcon from "../../assets/icons/SendIcon";
import { Button } from "../../design-system/components/Button";
import { Flex } from "../../design-system/components/Flex";
import { Textarea } from "../../design-system/components/Textarea";

interface MessageInputProps {
  inputRef?: RefObject<HTMLTextAreaElement>;
  value?: string;
  onChange?: (value: string) => void;
  onSend: () => void;
  onKeyDown?: (event: KeyboardEvent) => void;
  onVoiceToggle?: () => void;
  isVoiceActive?: boolean;
  disabled?: boolean;
  placeholder?: string;
  onKnowledgeUpload?: () => void;
  knowledgeUploadDisabled?: boolean;
  knowledgeUploadBusy?: boolean;
}

// Subcomponent for voice toggle button
const VoiceButton: FC<{
  isActive: boolean;
  disabled?: boolean;
  onToggle: () => void;
}> = ({ isActive, disabled, onToggle }) => (
  <Button
    type="button"
    size="icon"
    variant={isActive ? "default" : "secondary"}
    disabled={disabled}
    onClick={onToggle}
    aria-label="Toggle voice mode"
    title={isActive ? "End voice call" : "Start voice call"}
  >
    <FaMicrophone />
  </Button>
);

const MessageInput: FC<MessageInputProps> = ({
  inputRef,
  value,
  onChange,
  onSend,
  onKeyDown,
  placeholder,
  disabled,
  onVoiceToggle,
  isVoiceActive = false,
  onKnowledgeUpload,
  knowledgeUploadDisabled,
  knowledgeUploadBusy,
}) => {
  const internalRef = useRef<HTMLTextAreaElement | null>(null);
  const textareaRef = inputRef || internalRef;

  // Auto-resize textarea based on content
  const adjustTextareaHeight = () => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      textarea.style.height = `${Math.min(textarea.scrollHeight, 150)}px`;
    }
  };

  useEffect(() => {
    adjustTextareaHeight();
  }, [value]);

  const handleInput = (e: Event) => {
    const target = e.target as HTMLTextAreaElement;
    if (onChange) {
      onChange(target.value);
    }
    adjustTextareaHeight();
  };

  return (
    <Flex gap="xs" align="center" width="full">
      {onVoiceToggle && (
        <VoiceButton isActive={isVoiceActive} disabled={disabled} onToggle={onVoiceToggle} />
      )}

      {onKnowledgeUpload && (
        <Button
          type="button"
          size="icon"
          variant="secondary"
          disabled={knowledgeUploadDisabled}
          onClick={onKnowledgeUpload}
          aria-label="Add a Knowledge file"
          title={knowledgeUploadBusy ? "Knowledge file is indexing" : "Add a Knowledge file"}
        >
          <FaPaperclip />
        </Button>
      )}

      <Textarea
        ref={textareaRef as any}
        value={value}
        placeholder={placeholder}
        onKeyDown={onKeyDown}
        onInput={handleInput}
        disabled={disabled}
        autoFocus
        rows={1}
        minHeight="sm"
        maxHeight="2xl"
      />

      <Button
        type="button"
        size="icon"
        disabled={disabled}
        onClick={onSend}
        aria-label="Send message"
      >
        <SendIcon />
      </Button>
    </Flex>
  );
};

export default MessageInput;
