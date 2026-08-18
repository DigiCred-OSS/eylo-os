/**
 * Astryx components, extended with `accent`
 *
 * DRAMS gives every control an `accent` opt-in. The CSS system does it with a
 * class, the Preact adapter with a prop. Astryx has neither — its
 * `--color-accent` is a single global token — so this layer adds the same prop
 * to Astryx's components and keeps the API identical across all three
 * consumers:
 *
 *   <Button label="Save" />           // neutral
 *   <Button label="Save" accent />    // brand
 *
 * Underneath, `accent` mounts a scoped Theme that overrides exactly one group
 * of tokens. That is an implementation detail — callers never see a Theme, and
 * never have to know that Astryx models brand globally rather than per element.
 *
 * The wrapper inherits the surrounding colour mode via `useTheme()`, so an
 * accented control inside a dark region stays dark.
 */
import type { ComponentType } from 'react'
import { Theme, useTheme } from '@astryxdesign/core/theme'
import { dramsAccentTheme } from '../theme/dramsTheme'

import { Button as AButton } from '@astryxdesign/core/Button'
import { IconButton as AIconButton } from '@astryxdesign/core/IconButton'
import { Link as ALink } from '@astryxdesign/core/Link'
import { Badge as ABadge } from '@astryxdesign/core/Badge'
import { Avatar as AAvatar } from '@astryxdesign/core/Avatar'
import { Spinner as ASpinner } from '@astryxdesign/core/Spinner'
import { ProgressBar as AProgressBar } from '@astryxdesign/core/ProgressBar'
import { TextInput as ATextInput } from '@astryxdesign/core/TextInput'
import { TextArea as ATextArea } from '@astryxdesign/core/TextArea'
import { CheckboxInput as ACheckboxInput } from '@astryxdesign/core/CheckboxInput'
import { Switch as ASwitch } from '@astryxdesign/core/Switch'
import { Slider as ASlider } from '@astryxdesign/core/Slider'
import { RadioList as ARadioList } from '@astryxdesign/core/RadioList'
import { TabList as ATabList } from '@astryxdesign/core/TabList'
import { Breadcrumbs as ABreadcrumbs } from '@astryxdesign/core/Breadcrumbs'
import { Banner as ABanner } from '@astryxdesign/core/Banner'
import { Card as ACard } from '@astryxdesign/core/Card'

/** Scopes the brand to its subtree, inheriting the ambient colour mode. */
function AccentRegion({ children }: { children: React.ReactNode }) {
    const { mode } = useTheme()
    return <Theme theme={dramsAccentTheme} mode={mode}>{children}</Theme>
}

/** Adds `accent` to any component without touching its own props. */
function withAccent<P extends object>(Comp: ComponentType<P>, displayName: string) {
    const Wrapped = ({ accent, ...props }: P & { accent?: boolean }) =>
        accent
            ? <AccentRegion><Comp {...(props as P)} /></AccentRegion>
            : <Comp {...(props as P)} />
    Wrapped.displayName = `Accented(${displayName})`
    return Wrapped
}

export const Button = withAccent(AButton, 'Button')
export const IconButton = withAccent(AIconButton, 'IconButton')
export const Link = withAccent(ALink, 'Link')
export const Badge = withAccent(ABadge, 'Badge')
export const Avatar = withAccent(AAvatar, 'Avatar')
export const Spinner = withAccent(ASpinner, 'Spinner')
export const ProgressBar = withAccent(AProgressBar, 'ProgressBar')
export const TextInput = withAccent(ATextInput, 'TextInput')
export const TextArea = withAccent(ATextArea, 'TextArea')
export const CheckboxInput = withAccent(ACheckboxInput, 'CheckboxInput')
export const Switch = withAccent(ASwitch, 'Switch')
export const Slider = withAccent(ASlider, 'Slider')
export const RadioList = withAccent(ARadioList, 'RadioList')
export const TabList = withAccent(ATabList, 'TabList')
export const Breadcrumbs = withAccent(ABreadcrumbs, 'Breadcrumbs')
export const Banner = withAccent(ABanner, 'Banner')
export const Card = withAccent(ACard, 'Card')
