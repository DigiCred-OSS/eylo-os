/**
 * Full Astryx inventory — the remainder: Chat, Media, Shell, Search.
 *
 * These are the components that need real scaffolding rather than a bare
 * instance: a search source, a media list, a filter config. Each demo builds
 * the minimum real structure rather than faking it.
 */
import { useState } from 'react'
import { Showcase, Demo } from '../ui'

import { Icon } from '@astryxdesign/core/Icon'
import { Citation } from '@astryxdesign/core/Citation'
import { Carousel } from '@astryxdesign/core/Carousel'
import { Lightbox } from '@astryxdesign/core/Lightbox'
import { MobileNav } from '@astryxdesign/core/MobileNav'
import { CommandPalette } from '@astryxdesign/core/CommandPalette'
import { Tokenizer } from '@astryxdesign/core/Tokenizer'
import { createStaticSource } from '@astryxdesign/core/Typeahead/utils'
import {
    ChatComposer, ChatMessage, ChatMessageList, ChatSystemMessage,
} from '@astryxdesign/core/Chat'
import { Text } from '@astryxdesign/core/Text'
import { Card } from '@astryxdesign/core/Card'

import { Button } from '../components/accented'

/* A real image rather than a network request. */
const swatch = (hex: string) =>
    'data:image/svg+xml;utf8,' + encodeURIComponent(
        `<svg xmlns="http://www.w3.org/2000/svg" width="240" height="160">` +
        `<rect width="240" height="160" fill="${hex}"/></svg>`)

const MEDIA = [
    { src: swatch('%23E7E5E4'), alt: 'Neutral 200', caption: 'Neutral 200' },
    { src: swatch('%23A8A29E'), alt: 'Neutral 400', caption: 'Neutral 400' },
    { src: swatch('%2344403C'), alt: 'Neutral 700', caption: 'Neutral 700' },
]

const PEOPLE = createStaticSource([
    { id: 'a', label: 'Ada Lovelace' },
    { id: 'b', label: 'Grace Hopper' },
    { id: 'c', label: 'Alan Turing' },
])

const COMMANDS = createStaticSource([
    { id: 'new', label: 'New project' },
    { id: 'open', label: 'Open…' },
    { id: 'theme', label: 'Toggle theme' },
])

const ICON_NAMES = [
    'search', 'close', 'check', 'calendar', 'clock', 'menu',
    'copy', 'wrench', 'funnel', 'microphone',
] as const

export function IconSection() {
    return (
        <Showcase id="icons" title="Icons & citations"
            blurb="Astryx ships a built-in icon set, so no registry configuration is needed for the standard names.">
            <Demo title="Built-in icons">
                {ICON_NAMES.map(n => <Icon key={n} icon={n} label={n} />)}
            </Demo>
            <Demo title="Icon sizes">
                <Icon icon="search" label="Small" size="sm" />
                <Icon icon="search" label="Medium" size="md" />
                <Icon icon="search" label="Large" size="lg" />
            </Demo>
            <Demo title="Citation" column>
                <Citation number={1} source={{ title: 'Dieter Rams, Ten Principles', url: '#' }} />
                <Citation number={2} variant="label"
                    source={{ title: 'Braun ET66', url: '#' }} />
            </Demo>
        </Showcase>
    )
}

export function MediaSection() {
    const [lightbox, setLightbox] = useState(false)
    return (
        <Showcase id="media" title="Media"
            blurb="Carousel scrolls in place; Lightbox takes over the viewport. Both keep the same neutral surface language.">
            <Demo title="Carousel" column>
                <Carousel hasButtons hasSnap gap={2}>
                    {MEDIA.map(m => (
                        <img key={m.alt} src={m.src} alt={m.alt}
                            style={{ width: 180, borderRadius: 'var(--radius-container)' }} />
                    ))}
                </Carousel>
            </Demo>
            <Demo title="Lightbox" column>
                <Button label="Open lightbox" onClick={() => setLightbox(true)} />
                <Lightbox isOpen={lightbox} onOpenChange={setLightbox} media={MEDIA} hasZoom />
            </Demo>
        </Showcase>
    )
}

export function ShellSection() {
    const [nav, setNav] = useState(false)
    return (
        <Showcase id="shell" title="Shell"
            blurb="Application chrome. AppShell composes header, side nav and content; MobileNav is its small-screen drawer.">
            <Demo title="Mobile nav" column
                note="AppShell is a full-page frame, so it is not embedded here — it composes SideNav + TopNav + content and would take over the showcase layout.">
                <Button label="Open mobile nav" onClick={() => setNav(true)} />
                <MobileNav isOpen={nav} onOpenChange={setNav} label="Menu">
                    <Text size="sm">Overview</Text>
                    <Text size="sm">Projects</Text>
                    <Text size="sm">Settings</Text>
                </MobileNav>
            </Demo>
        </Showcase>
    )
}

export function SearchSection() {
    const [palette, setPalette] = useState(false)
    const [tokens, setTokens] = useState<{ id: string; label: string }[]>([])
    return (
        <Showcase id="search" title="Search"
            blurb="Search surfaces are driven by a SearchSource — createStaticSource() wraps a plain array for local data.">
            <Demo title="Command palette" column>
                <Button label="Open palette" onClick={() => setPalette(true)} />
                <CommandPalette isOpen={palette} onOpenChange={setPalette}
                    searchSource={COMMANDS} />
            </Demo>
            <Demo title="Tokenizer" column>
                <Tokenizer label="Recipients" searchSource={PEOPLE}
                    value={tokens} onChange={items => setTokens(items)} />
            </Demo>
        </Showcase>
    )
}

export function ChatSection() {
    const [sent, setSent] = useState<string[]>([])
    return (
        <Showcase id="chat" title="Chat"
            blurb="A composed surface rather than a single component — message list, messages, system notices and a composer.">
            <Demo title="Message list" column>
                <Card>
                    <ChatMessageList>
                        <ChatMessage sender="user" name="Ada">
                            <Text size="sm">Is the accent opt-in per element?</Text>
                        </ChatMessage>
                        <ChatMessage sender="assistant">
                            <Text size="sm">Yes — neutral until something asks for it.</Text>
                        </ChatMessage>
                        {sent.map((m, i) => (
                            <ChatMessage key={i} sender="assistant"><Text size="sm">{m}</Text></ChatMessage>
                        ))}
                    </ChatMessageList>
                </Card>
            </Demo>
            <Demo title="System message" column>
                <ChatSystemMessage>Conversation started</ChatSystemMessage>
            </Demo>
            <Demo title="Composer" column>
                <ChatComposer placeholder="Type a message…"
                    onSubmit={v => setSent(s => [...s, v])} />
            </Demo>
        </Showcase>
    )
}
