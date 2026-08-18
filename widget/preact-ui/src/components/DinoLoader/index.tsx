import { useEffect, useRef, useState } from "preact/hooks";
import type { FC } from "preact/compat";
import { createInitialState, render, step } from "./dino-engine";
import styles from "./DinoLoader.module.css";

interface DinoLoaderProps {
  /** Whether the loader overlay is visible */
  visible?: boolean;
}

/**
 * DinoLoader — A Chrome Dino–style canvas animation for the thinking state.
 *
 * Renders as an absolute overlay. Always mounted, shown/hidden via CSS
 * to avoid layout thrash when toggling between thinking and input states.
 */
const DinoLoader: FC<DinoLoaderProps> = ({ visible = false }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);
  const stateRef = useRef(createInitialState());
  const spriteRef = useRef<HTMLImageElement | null>(null);
  const visibleRef = useRef(visible);
  const ctxRef = useRef<CanvasRenderingContext2D | null>(null);
  const [imgLoaded, setImgLoaded] = useState(false);

  // Keep ref in sync so the rAF loop can read it without re-mounting
  visibleRef.current = visible;

  // Start or resume the animation loop when visible AND image loaded
  useEffect(() => {
    if (!visible || !imgLoaded) return;

    const ctx = ctxRef.current;
    const img = spriteRef.current;
    const canvas = canvasRef.current;
    const state = stateRef.current;
    if (!ctx || !img || !canvas) return;

    const loop = () => {
      if (!visibleRef.current) return; // stop looping when hidden
      step(state);
      const dpr = window.devicePixelRatio || 1;
      render(ctx, state, img, canvas.width / dpr, canvas.height / dpr);
      animRef.current = requestAnimationFrame(loop);
    };

    animRef.current = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(animRef.current);
    };
  }, [visible, imgLoaded]);

  // One-time setup: load sprite, size canvas, set up resize observer
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctxRef.current = ctx;

    // Load sprite sheet — inlined as data URL so it works when embedded on any origin
    const img = new Image();
    img.src =
      "data:image/png;base64,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";
    spriteRef.current = img;

    // Size canvas to container with device pixel ratio
    const resizeCanvas = () => {
      const container = canvas.parentElement;
      if (!container) return;

      const dpr = window.devicePixelRatio || 1;
      const drawW = container.clientWidth;
      const drawH = container.clientHeight;

      canvas.style.width = `${drawW}px`;
      canvas.style.height = `${drawH}px`;
      canvas.width = Math.round(drawW * dpr);
      canvas.height = Math.round(drawH * dpr);

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const onImgLoad = () => {
      setImgLoaded(true);
      resizeCanvas();
    };

    if (img.complete) {
      onImgLoad();
    } else {
      img.onload = onImgLoad;
    }

    // Handle resize
    const ro = new ResizeObserver(() => resizeCanvas());
    ro.observe(canvas.parentElement!);

    return () => {
      cancelAnimationFrame(animRef.current);
      ro.disconnect();
      img.onload = null;
    };
  }, []);

  return (
    <div className={`${styles.dinoLoaderContainer} ${visible ? styles.dinoLoaderVisible : ""}`}>
      <canvas ref={canvasRef} className={styles.dinoCanvas} />
    </div>
  );
};

export default DinoLoader;
