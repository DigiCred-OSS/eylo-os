import type { FC } from "preact/compat";

import type { TIcon } from "./types";

const DownArrowIcon: FC<TIcon> = ({ className, style }) => {
  return (
    <svg
      style={style}
      className={className}
      aria-hidden="true"
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      fill="none"
      viewBox="0 0 24 24"
    >
      <path
        stroke="currentColor"
        stroke-linecap="round"
        stroke-linejoin="round"
        stroke-width="1.5"
        d="m19 9-7 7-7-7"
      />
    </svg>
  );
};

export default DownArrowIcon;
