import { useState } from 'react'
import { Theme } from '@astryxdesign/core/theme'
import { neutralTheme } from '@astryxdesign/theme-neutral'

import { Tab } from '@astryxdesign/core/TabList'
import { RadioListItem } from '@astryxdesign/core/RadioList'
import { Text } from '@astryxdesign/core/Text'
import { Code } from '@astryxdesign/core/Code'

import { dramsTheme } from './theme/dramsTheme'
import { Showcase, Demo } from './ui'
import { ActionSection, ContentSection, FeedbackSection } from './sections/partA'
import { DataInputSection, ContainerSection, LayoutSection } from './sections/partB'
import { NavigationSection, OverlaySection, DataSection } from './sections/partC'
import {
    IconSection, MediaSection, ShellSection, SearchSection, ChatSection,
} from './sections/partD'

// Astryx components extended with DRAMS' `accent` prop — same API as the CSS
// system (`class="accent"`) and the Preact adapter.
import {
    Button, Link, CheckboxInput, Switch, Slider, RadioList,
    TabList, TextInput, TextArea,
} from './components/accented'

const SECTIONS = [
    ['action', 'Action'], ['content2', 'Content'], ['datainput', 'Data input'],
    ['container', 'Container'], ['feedback2', 'Feedback'], ['layout2', 'Layout'],
    ['navigation2', 'Navigation'], ['overlay', 'Overlay'], ['data2', 'Data'],
    ['icons', 'Icons'], ['media', 'Media'], ['search', 'Search'],
    ['chat', 'Chat'], ['shell', 'Shell'], ['accent', 'Accent'],
] as const

export default function App() {
    const [mode, setMode] = useState<'light' | 'dark'>('light')
    const [useDrams, setUseDrams] = useState(true)

    return (
        <Theme theme={useDrams ? dramsTheme : neutralTheme} mode={mode}>
            <div className="page">
                <header className="masthead">
                    <div>
                        <h1>Astryx × DRAMS</h1>
                        <p>
                            Astryx, unchanged. DRAMS does not repaint it — Astryx keeps its own
                            colour, radius, elevation and type. DRAMS contributes exactly two
                            things: <em>accent</em>, the opt-in brand seam, and a default for the
                            one token Astryx does not define. Toggling the theme below should look
                            almost identical; that is the point.
                        </p>
                    </div>
                    <div className="controls">
                        <span className="controls-label">Theme</span>
                        <button className="toggle" aria-pressed={useDrams} onClick={() => setUseDrams(true)}>DRAMS</button>
                        <button className="toggle" aria-pressed={!useDrams} onClick={() => setUseDrams(false)}>Astryx neutral</button>
                        <span className="controls-label" style={{ marginLeft: 12 }}>Mode</span>
                        <button className="toggle" aria-pressed={mode === 'light'} onClick={() => setMode('light')}>Light</button>
                        <button className="toggle" aria-pressed={mode === 'dark'} onClick={() => setMode('dark')}>Dark</button>
                    </div>
                </header>

                <nav className="controls" style={{ marginBottom: 40 }}>
                    {SECTIONS.map(([id, label]) => (
                        <a key={id} className="toggle" href={`#${id}`}>{label}</a>
                    ))}
                </nav>

                <ActionSection />
                <ContentSection />
                <DataInputSection />
                <ContainerSection />
                <FeedbackSection />
                <LayoutSection />
                <NavigationSection />
                <OverlaySection />
                <DataSection />
                <IconSection />
                <MediaSection />
                <SearchSection />
                <ChatSection />
                <ShellSection />

                <Showcase id="accent" title="Accent — the brand seam"
                    blurb="Everything above is neutral. `accent` is opt-in and is the only thing that renders brand colour — the same prop the CSS system and the Preact adapter expose. Each pair is one component: neutral left, accent right.">
                    <Demo title="Button — primary">
                        <Button label="Save" variant="primary" />
                        <Button label="Save" variant="primary" accent />
                    </Demo>
                    <Demo title="Link">
                        <Link href="#accent">Neutral</Link>
                        <Link href="#accent" accent>Brand</Link>
                    </Demo>
                    <Demo title="Checkbox">
                        <CheckboxInput label="Neutral" value onChange={() => {}} />
                        <CheckboxInput label="Brand" value onChange={() => {}} accent />
                    </Demo>
                    <Demo title="Switch">
                        <Switch label="Neutral" value onChange={() => {}} />
                        <Switch label="Brand" value onChange={() => {}} accent />
                    </Demo>
                    <Demo title="Radio" column>
                        <RadioList label="Neutral" value="a" onChange={() => {}}>
                            <RadioListItem value="a" label="Selected" />
                        </RadioList>
                        <RadioList label="Brand" value="a" onChange={() => {}} accent>
                            <RadioListItem value="a" label="Selected" />
                        </RadioList>
                    </Demo>
                    <Demo title="Slider" column>
                        <Slider label="Neutral" value={60} min={0} max={100} />
                        <Slider label="Brand" value={60} min={0} max={100} accent />
                    </Demo>
                    <Demo title="Tabs" column>
                        <TabList value="a" onChange={() => {}}>
                            <Tab value="a" label="Neutral" />
                            <Tab value="b" label="Two" />
                        </TabList>
                        <TabList value="a" onChange={() => {}} accent>
                            <Tab value="a" label="Brand" />
                            <Tab value="b" label="Two" />
                        </TabList>
                    </Demo>
                    <Demo title="Text input" column
                        note="Focus each field — the ring is where accent reaches a text control.">
                        <TextInput label="Neutral" value="" placeholder="Focus me" />
                        <TextInput label="Brand" value="" placeholder="Focus me" accent />
                    </Demo>
                    <Demo title="Text area" column>
                        <TextArea label="Neutral" value="" placeholder="Focus me" />
                        <TextArea label="Brand" value="" placeholder="Focus me" accent />
                    </Demo>
                    <Demo title="Where accent does not reach" column
                        note="Not a gap in DRAMS — Astryx simply does not route --color-accent to these, so an accent prop on them would be a no-op. Measured in the running app, not assumed.">
                        <Text size="sm" color="secondary">
                            Secondary / ghost buttons, Icon button, ProgressBar, Breadcrumbs,
                            Badge, Avatar, Spinner and Banner render identically with and
                            without <Code>accent</Code>. Badge and Banner are status surfaces —
                            they report an outcome, so brand would be wrong there anyway.
                        </Text>
                    </Demo>
                    <Demo title="Swapping the brand" column
                        note="Braun Orange is only a default. A brand overrides the five values in `brand` and nothing else — no component CSS, no forks.">
                        <Text size="sm" color="secondary">
                            See <Code>src/theme/dramsTheme.ts</Code> → <Code>brand</Code>
                        </Text>
                    </Demo>
                </Showcase>
            </div>
        </Theme>
    )
}
