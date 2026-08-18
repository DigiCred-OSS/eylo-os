/**
 * DRAMS for Astryx — minimal overrides
 *
 * DRAMS does not repaint Astryx. Astryx is a complete, neutral system with its
 * own opinion on colour, radius, elevation and type, and those opinions stand.
 *
 * DRAMS contributes exactly two things:
 *
 *   1. ACCENT — the brand seam. Opt-in, scoped, one group of tokens.
 *   2. GAP DEFAULTS — a value only where Astryx defines none.
 *
 * Everything else is inherited. An earlier version of this file set 49 tokens,
 * of which 48 were overriding an opinion Astryx already had — replacing its
 * radius scale, its neutrals, its shadows. That is a skin, not an extension,
 * and it made DRAMS look like a competing design system rather than a brand
 * layer that any Astryx app can adopt.
 *
 * The rule for anything added here: if Astryx already defines the token, DRAMS
 * does not touch it. Check before adding —
 *   grep -o '\--[a-z-]*:' node_modules/…/theme-neutral/dist/theme.css | sort -u
 *
 * NOTE: Astryx's own accent is already neutral — `light-dark(#262626, #ebebeb)`.
 * So the base theme has nothing to neutralise; brand enters only via
 * `dramsAccentTheme` below.
 *
 * Mirrors the shared Drams design tokens.
 */
import { defineTheme } from '@astryxdesign/core/theme'
import { neutralTheme } from '@astryxdesign/theme-neutral'

/**
 * THE BRAND LAYER — the only thing a brand overrides.
 *
 * Swap these five values and DRAMS becomes another brand's system. Braun
 * Orange is the default only because DRAMS takes its principles from Rams'
 * work at Braun; the system is named for the principles, not the colour.
 *
 * Mirrors `--brand-primary-*` in drams3/tokens/foundation.css.
 */
export const brand = {
    400: '#FF7733',
    500: '#FF5500',
    600: '#CC4400',
    alpha10: 'rgba(255,85,0,0.10)',
    alpha20: 'rgba(255,119,51,0.20)',
} as const

/**
 * DRAMS base.
 *
 * Astryx neutral, plus defaults for the tokens Astryx does not define. Nothing
 * here overrides an existing Astryx value — the visual result is deliberately
 * indistinguishable from plain Astryx until something opts into accent.
 */
export const dramsTheme = defineTheme({
    name: 'drams',
    extends: neutralTheme,
    tokens: {
        /* GAP: Astryx has surface / card / popover / muted, but no inverted
           surface. DRAMS uses one for inverse-on-surface treatments, so it
           supplies a default rather than leaving consumers to invent one. */
        '--color-background-inverted': ['#1C1917', '#FAFAF9'],
    },
})

/**
 * DRAMS + brand — the opt-in.
 *
 * Identical to `dramsTheme` except that the accent tokens resolve to the
 * brand. Wrap a region in this and that region's active states render in
 * brand; everything outside stays neutral.
 *
 * This is the Astryx-idiomatic equivalent of `class="accent"` in the CSS
 * system — and `components/accented.tsx` wraps it behind an `accent` prop so
 * callers never see a Theme.
 */
export const dramsAccentTheme = defineTheme({
    name: 'drams-accent',
    extends: dramsTheme,
    tokens: {
        '--color-accent': [brand[500], brand[400]],
        '--color-accent-muted': [brand.alpha10, brand.alpha20],
        '--color-on-accent': '#FFFFFF',
        '--color-icon-accent': [brand[500], brand[400]],
        '--color-text-accent': [brand[600], brand[400]],
        '--shadow-inset-selected': `inset 0 0 0 2px ${brand[500]}`,
        '--shadow-inset-hover': `inset 0 0 0 2px ${brand[500]}40`,
    },
})

export default dramsTheme
