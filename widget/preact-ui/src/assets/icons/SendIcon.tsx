import type { FC } from "preact/compat";

import type { TIcon } from "./types";

const SendIcon: FC<TIcon> = ({ className }) => {
  return (
    <svg
      className={className}
      aria-hidden="true"
      xmlns="http://www.w3.org/2000/svg"
      width="16"
      height="16"
      fill="none"
      viewBox="0 0 24 24"
    >
      <path
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M22 2L11 13"
      />
      <path
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M22 2L15 22L11 13L2 9L22 2Z"
      />
    </svg>
  );
};

export default SendIcon;
