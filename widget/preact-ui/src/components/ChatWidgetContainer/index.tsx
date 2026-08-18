import type { FC } from "preact/compat";
import { useState } from "preact/hooks";

import { useConnectionStateManager } from "../../hooks/useEyloStore";
import { useWidgetActions } from "../../hooks/useActions";
import { useWidgetPosition } from "../../hooks/useWidgetPosition";
import { ChatFloatingButton } from "../ChatFloatingButton";
import ConnectionPanel from "../ConnectionPanel";
import ChatContent from "./ChatContent";
import ChatFooter from "./ChatFooter";
import ChatHeader from "./ChatHeader";
import styles from "./ChatWidgetContainer.module.css";

const ChatWidgetContainer: FC = (props) => {
  const connectionManager = useConnectionStateManager();
  const { openWidget, closeWidget } = useWidgetActions();
  const { setFloatingButtonPosition, widgetStyle } = useWidgetPosition();

  const isDev = process.env.NODE_ENV === "development";
  const [open, setOpen] = useState(isDev);

  const handleOpen = () => {
    try {
      openWidget();
      setOpen(true);
    } catch (error) {
      console.error("Error opening widget:", error);
    }
  };

  const handleClose = () => {
    try {
      closeWidget();
      setOpen(false);
    } catch (error) {
      console.error("Error closing widget:", error);
    }
  };

  const handleToggle = () => {
    if (open) {
      handleClose();
    } else {
      handleOpen();
    }
  };

  return (
    <>
      {open && (
        <div
          id="ew-chat-widget-container"
          className={` ${styles.widgetRoot} ${styles.chatContainer} ${styles.chatContainerProd} `}
          style={widgetStyle}
        >
          <div className={styles.contentWrapper}>{props.children}</div>
          {connectionManager && <ConnectionPanel connectionManager={connectionManager} />}
        </div>
      )}
      <ChatFloatingButton
        setDimensions={setFloatingButtonPosition}
        onClick={handleToggle}
        isOpen={open}
      />
    </>
  );
};

export default Object.assign(ChatWidgetContainer, {
  ChatHeader,
  ChatContent,
  ChatFooter,
});
