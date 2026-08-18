// components/ConversationDetails/NewMessagesIndicator.tsx
import type { FC } from "preact/compat";
import { Button } from "../../design-system/components/Button";
import { FaArrowDown } from "react-icons/fa";

interface NewMessagesIndicatorProps {
  show: boolean;
  onClick: () => void;
}

/**
 * Floating indicator shown when new messages arrive while user has scrolled up
 */
const NewMessagesIndicator: FC<NewMessagesIndicatorProps> = ({ show, onClick }) => {
  if (!show) return null;

  return (
    <div
      style={{
        position: "absolute",
        bottom: "80px",
        left: "50%",
        transform: "translateX(-50%)",
        zIndex: 10,
      }}
    >
      <Button variant="default" size="sm" onClick={onClick}>
        <FaArrowDown size={12} />
        New messages
      </Button>
    </div>
  );
};

export default NewMessagesIndicator;
