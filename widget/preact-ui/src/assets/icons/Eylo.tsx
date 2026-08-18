import type { FC } from "preact/compat";

import type { TIcon } from "./types";

interface EyloIconProps extends TIcon {
  status?: "online" | "offline";
}

export const EyloIcon: FC<EyloIconProps> = ({ className, status }) => {
  // Determine fill color based on status
  const fillColor =
    status === "online"
      ? "oklch(var(--ew-success))"
      : status === "offline"
        ? "oklch(var(--ew-destructive))"
        : "currentColor";

  return (
    <svg
      className={`animated-logo ${className}`}
      width="30"
      height="30"
      viewBox="7 7 30 30"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        className="swish-1"
        fill-rule="evenodd"
        clip-rule="evenodd"
        d="M28.6629 6.92676L15.5042 14.7653C13.8358 15.7569 12.8127 17.5513 12.8127 19.503V22.777L25.9714 14.9384C27.6398 13.9468 28.6629 12.1525 28.6629 10.2007V6.92676Z"
        fill={fillColor}
      />
      <path
        className="swish-2"
        fill-rule="evenodd"
        clip-rule="evenodd"
        d="M23.2481 20.6213L15.4726 25.3119C13.8199 26.3035 12.8125 28.0979 12.8125 30.0339V33.3235L20.5881 28.633C22.2408 27.6414 23.2481 25.847 23.2481 23.911V20.6213Z"
        fill={fillColor}
      />
      <path
        className="swish-3"
        fill-rule="evenodd"
        clip-rule="evenodd"
        d="M24.2881 29.2468L32.0637 24.5563V27.8459C32.0637 29.7819 31.0563 31.5763 29.4036 32.5679L21.6281 37.2585V33.9688C21.6281 32.0328 22.6354 30.2384 24.2881 29.2468Z"
        fill={fillColor}
      />
    </svg>
  );
};
