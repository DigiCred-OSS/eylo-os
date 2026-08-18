/**
 * DinoLoader — Chrome Dino Runner canvas animation used as a thinking indicator.
 *
 * Non-playable, deterministic, looping. The dino runs, obstacles scroll,
 * jumps are pre-timed to clear each cactus. All from a precomputed timeline.
 *
 * Sprite source: /public/sprite.png (Chrome Dino sprite sheet)
 */

// ─── Sprite Atlas ───────────────────────────────────────────────────
// All coordinates reference sprite.png at 1× resolution.

export const SPRITES = {
  ground: { x: 0, y: 104, w: 2404, h: 18 },
  trexRun1: { x: 1514, y: 0, w: 88, h: 94 },
  trexRun2: { x: 1602, y: 0, w: 88, h: 94 },
  trexJump: { x: 1338, y: 0, w: 88, h: 94 },
  // Small cacti: 34px wide each, 70px tall, starts at x=446
  cactusSmallA: { x: 446, y: 2, w: 34, h: 70 },
  cactusSmallB: { x: 548, y: 2, w: 34, h: 70 },
  // Big cacti: 49px wide each, 100px tall, starts at x=652
  cactusBigA: { x: 652, y: 2, w: 49, h: 100 },
  cactusBigB: { x: 802, y: 2, w: 49, h: 100 },
} as const;

// ─── World Constants ────────────────────────────────────────────────
// Canonical world: the scene is authored in these units, then scaled to fit.

/** Draw sprites at this fraction of their native size */
export const SPRITE_SCALE = 0.5;

export const WORLD = {
  width: 600,
  height: 150,
  groundY: 130, // ground surface Y (top of ground strip)
  gravity: 0.6,
  jumpVelocity: -8, // scaled down from -13 so arc fits half-size dino
  gameSpeed: 6,
  /** How many world-frames per run-frame toggle (~every 6 ticks at 60fps) */
  runFrameInterval: 6,
} as const;

// ─── Timeline ───────────────────────────────────────────────────────
// Obstacles spawn at fixed positions in the loop. The dino jumps at fixed times.
// The entire loop is `LOOP_FRAMES` frames long at 60 FPS.

/** Total loop length in frames (60fps). ~4 seconds. */
export const LOOP_FRAMES = 240;

export interface ObstacleEntry {
  /** Frame at which obstacle appears at right edge */
  spawnFrame: number;
  sprite: keyof typeof SPRITES;
  /** How many multiples wide (1, 2, or 3 grouped) */
  count: number;
}

export interface JumpEntry {
  /** Frame at which the dino starts its jump */
  frame: number;
}

/**
 * A scene is one variation of the looping animation.
 * Each has its own obstacle layout and matching jump timings.
 *
 * Timing math (at SPRITE_SCALE 0.5):
 *   Jump arc: velocity -8, gravity 0.6 → peak ~13 frames, air time ~27 frames.
 *   Obstacle reaches dino x=60 from spawn x=600: (600-60)/6 = 90 frames.
 *   Jump starts ~13 frames before arrival → spawnFrame + 77.
 *   Obstacle clears screen in ~103 frames → last spawn by frame 137.
 */
export interface Scene {
  name: string;
  obstacles: ObstacleEntry[];
  jumps: JumpEntry[];
}

export const SCENES: Scene[] = [
  {
    // Two obstacles: small pair, then one big
    name: "v1",
    obstacles: [
      { spawnFrame: 0, sprite: "cactusSmallA", count: 2 },
      { spawnFrame: 120, sprite: "cactusBigA", count: 1 },
    ],
    jumps: [{ frame: 77 }, { frame: 197 }],
  },
  {
    // Two obstacles: big cactus, then small triple
    name: "v2",
    obstacles: [
      { spawnFrame: 0, sprite: "cactusBigB", count: 1 },
      { spawnFrame: 100, sprite: "cactusSmallB", count: 3 },
    ],
    jumps: [{ frame: 77 }, { frame: 177 }],
  },
  {
    // Three obstacles: small, big, small — evenly spaced
    name: "v3",
    obstacles: [
      { spawnFrame: 0, sprite: "cactusSmallB", count: 1 },
      { spawnFrame: 80, sprite: "cactusBigA", count: 1 },
      { spawnFrame: 130, sprite: "cactusSmallA", count: 1 },
    ],
    jumps: [{ frame: 77 }, { frame: 157 }, { frame: 207 }],
  },
  {
    // Peaceful: just running, no obstacles
    name: "v4",
    obstacles: [],
    jumps: [],
  },
];

function randomScene(): Scene {
  return SCENES[Math.floor(Math.random() * SCENES.length)];
}

// ─── Runtime State ──────────────────────────────────────────────────

export interface DinoState {
  /** Current frame within the loop [0, LOOP_FRAMES) */
  frame: number;
  /** Dino Y position (bottom-anchored to groundY) */
  dinoY: number;
  /** Dino vertical velocity */
  dinoVY: number;
  /** Whether dino is on ground */
  onGround: boolean;
  /** Run animation toggle counter */
  runCounter: number;
  /** Current run frame (true = frame1, false = frame2) */
  runToggle: boolean;
  /** Ground scroll offset */
  groundScroll: number;
  /** Active obstacles with their current x position */
  activeObstacles: Array<{
    sprite: keyof typeof SPRITES;
    count: number;
    x: number;
  }>;
  /** Set of jump frames already triggered this loop */
  triggeredJumps: Set<number>;
  /** Active scene for this loop iteration */
  scene: Scene;
}

export function createInitialState(): DinoState {
  return {
    frame: -1, // first step() increments to 0, triggering spawnFrame 0 immediately
    dinoY: WORLD.groundY - SPRITES.trexRun1.h * SPRITE_SCALE,
    dinoVY: 0,
    onGround: true,
    runCounter: 0,
    runToggle: false,
    groundScroll: 0,
    activeObstacles: [],
    triggeredJumps: new Set(),
    scene: randomScene(),
  };
}

// ─── Simulation Step ────────────────────────────────────────────────

export function step(state: DinoState): void {
  const { gameSpeed, groundY, gravity, jumpVelocity, runFrameInterval } = WORLD;
  const dinoH = SPRITES.trexRun1.h * SPRITE_SCALE;

  // Advance frame (loop)
  state.frame = (state.frame + 1) % LOOP_FRAMES;
  if (state.frame === 0) {
    state.triggeredJumps.clear();
    state.scene = randomScene();
  }

  // Check for jump triggers
  for (const jump of state.scene.jumps) {
    if (state.frame === jump.frame && !state.triggeredJumps.has(jump.frame) && state.onGround) {
      state.dinoVY = jumpVelocity;
      state.onGround = false;
      state.triggeredJumps.add(jump.frame);
    }
  }

  // Apply gravity
  if (!state.onGround) {
    state.dinoVY += gravity;
    state.dinoY += state.dinoVY;
  }

  // Ground collision
  if (state.dinoY >= groundY - dinoH) {
    state.dinoY = groundY - dinoH;
    state.dinoVY = 0;
    state.onGround = true;
  }

  // Run animation frame toggle
  state.runCounter++;
  if (state.runCounter >= runFrameInterval) {
    state.runToggle = !state.runToggle;
    state.runCounter = 0;
  }

  // Ground scroll (loop the 2404px strip)
  state.groundScroll = (state.groundScroll + gameSpeed) % SPRITES.ground.w;

  // Spawn obstacles at their scheduled frames
  for (const obs of state.scene.obstacles) {
    if (state.frame === obs.spawnFrame) {
      state.activeObstacles.push({
        sprite: obs.sprite,
        count: obs.count,
        x: WORLD.width,
      });
    }
  }

  // Move obstacles left
  for (const obs of state.activeObstacles) {
    obs.x -= gameSpeed;
  }

  // Remove offscreen obstacles
  state.activeObstacles = state.activeObstacles.filter((obs) => {
    const spriteW = SPRITES[obs.sprite].w * obs.count;
    return obs.x + spriteW > -20;
  });
}

// ─── Renderer ───────────────────────────────────────────────────────

export function render(
  ctx: CanvasRenderingContext2D,
  state: DinoState,
  spriteImg: HTMLImageElement,
  canvasWidth: number,
  canvasHeight: number
): void {
  const scaleX = canvasWidth / WORLD.width;
  const scaleY = canvasHeight / WORLD.height;

  ctx.clearRect(0, 0, canvasWidth, canvasHeight);
  ctx.save();
  ctx.scale(scaleX, scaleY);

  // Clip to world bounds so oversized sprites (ground strip) don't bleed
  ctx.beginPath();
  ctx.rect(0, 0, WORLD.width, WORLD.height);
  ctx.clip();

  const S = SPRITE_SCALE;

  // ── Ground ──
  const g = SPRITES.ground;
  const gH = g.h * S;
  const groundDrawY = WORLD.groundY;
  // Draw two copies of ground strip for seamless scroll
  const gx1 = -state.groundScroll;
  ctx.drawImage(spriteImg, g.x, g.y, g.w, g.h, Math.round(gx1), groundDrawY, g.w, gH);
  ctx.drawImage(spriteImg, g.x, g.y, g.w, g.h, Math.round(gx1 + g.w), groundDrawY, g.w, gH);

  // ── Obstacles ──
  for (const obs of state.activeObstacles) {
    const sp = SPRITES[obs.sprite];
    const drawW = sp.w * obs.count * S;
    const drawH = sp.h * S;
    const obsY = WORLD.groundY - drawH;
    ctx.drawImage(
      spriteImg,
      sp.x,
      sp.y,
      sp.w * obs.count,
      sp.h,
      Math.round(obs.x),
      obsY,
      drawW,
      drawH
    );
  }

  // ── T-Rex ──
  const dinoX = 60;
  let dinoSprite: (typeof SPRITES)[keyof typeof SPRITES];
  if (!state.onGround) {
    dinoSprite = SPRITES.trexJump;
  } else if (state.runToggle) {
    dinoSprite = SPRITES.trexRun1;
  } else {
    dinoSprite = SPRITES.trexRun2;
  }
  const dW = dinoSprite.w * S;
  const dH = dinoSprite.h * S;
  ctx.drawImage(
    spriteImg,
    dinoSprite.x,
    dinoSprite.y,
    dinoSprite.w,
    dinoSprite.h,
    dinoX,
    Math.round(state.dinoY),
    dW,
    dH
  );

  ctx.restore();
}
