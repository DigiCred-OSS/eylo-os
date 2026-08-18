import { useEffect, useRef, type FC } from "preact/compat";

import DownArrowIcon from "../../assets/icons/DownArrow";
import styles from "./ChatFloatingButton.module.css";
import { EyloIcon } from "../../assets/icons/Eylo";

export type TChatButtonDimensions = {
  x: number;
  y: number;
  width: number;
  height: number;
};

export type TChatFloatingButton = {
  setDimensions?: (d: TChatButtonDimensions) => void;
  onClick?: () => void;
  isOpen?: boolean;
};

const ChatFloatingButton: FC<TChatFloatingButton> = ({ setDimensions, onClick, isOpen }) => {
  const buttonRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (buttonRef.current && setDimensions) {
      const rect = buttonRef.current.getBoundingClientRect();
      setDimensions({
        x: rect.left,
        y: rect.top,
        width: rect.width,
        height: rect.height,
      });
    }
  }, [buttonRef.current]);

  return (
    <div
      id={"ew-chat-floating-button"}
      className={styles.floatingButtonContainer}
      ref={buttonRef}
      data-state={isOpen}
    >
      <div className={styles.buttonInner} onClick={onClick}>
        {isOpen ? <DownArrowIcon className={styles.icon} /> : <EyloIcon className={styles.icon} />}
      </div>
    </div>
  );
};

export default ChatFloatingButton;
export { ChatFloatingButton };
