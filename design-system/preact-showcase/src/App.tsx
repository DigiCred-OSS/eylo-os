import { useEffect, useState } from 'preact/hooks'
import type { ComponentChildren } from 'preact'
import {
    Button, ButtonGroup, Heading, Text, Code, Kbd, Avatar, Badge,
    Input, Textarea, Field, Slider, Checkbox, Switch, RadioGroup,
    Card, CardHeader, CardTitle, CardDescription, CardContent, Collapsible,
    Alert, Spinner, Skeleton, Progress, Stack, Row, Separator,
    Tabs, Breadcrumbs, List,
} from './components'

const SECTIONS = [
    ['buttons', 'Buttons'], ['content', 'Content'], ['inputs', 'Inputs'],
    ['selection', 'Selection'], ['containers', 'Containers'], ['feedback', 'Feedback'],
    ['layout', 'Layout'], ['navigation', 'Navigation'], ['data', 'Data'],
    ['accent', 'Accent'],
] as const

function Showcase({ id, title, blurb, children }: {
    id: string; title: string; blurb: string; children: ComponentChildren
}) {
    return (
        <section class="showcase" id={id}>
            <h2>{title}</h2>
            <p class="blurb">{blurb}</p>
            <div class="grid">{children}</div>
        </section>
    )
}

function Demo({ title, children, note, column }: {
    title: string; children: ComponentChildren; note?: string; column?: boolean
}) {
    return (
        <div class="demo">
            <h3>{title}</h3>
            <div class={column ? 'col' : 'row'}>{children}</div>
            {note ? <p class="note">{note}</p> : null}
        </div>
    )
}

export default function App() {
    const [mode, setMode] = useState<'light' | 'dark'>('light')
    const [theme, setTheme] = useState<'default' | 'skeuomorphic' | 'neumorphic'>('default')
    const [checked, setChecked] = useState(true)
    const [accentChecked, setAccentChecked] = useState(true)
    const [on, setOn] = useState(true)
    const [accentOn, setAccentOn] = useState(true)
    const [radio, setRadio] = useState('rest')
    const [slider, setSlider] = useState(60)

    // Two independent axes: data-mode carries light/dark, data-theme carries
    // the named theme. Both work with every theme — an earlier version set the
    // `dark` class instead, because data-mode did not reach the default theme.
    useEffect(() => {
        const r = document.documentElement
        r.setAttribute('data-mode', mode)
        if (theme === 'default') r.removeAttribute('data-theme')
        else r.setAttribute('data-theme', theme)
    }, [mode, theme])

    return (
        <div class="page">
            <header class="masthead">
                <div>
                    <h1>DRAMS × Preact</h1>
                    <p>
                        The same design system, driven by Preact instead of React. No Radix,
                        no headless dependency, no shared code with the React showcase — just
                        components emitting <code>.drams-*</code> classes and the documented
                        data attributes. Neutral by default; brand only where a component
                        opts into <code>accent</code>.
                    </p>
                </div>
                <div class="controls">
                    <span class="controls-label">Theme</span>
                    {(['default', 'skeuomorphic', 'neumorphic'] as const).map(t => (
                        <button key={t} class="toggle" aria-pressed={theme === t}
                            onClick={() => setTheme(t)}>
                            {t === 'default' ? 'Default' : t === 'skeuomorphic' ? 'Skeuo' : 'Neumo'}
                        </button>
                    ))}
                    <span class="controls-label" style={{ marginLeft: 12 }}>Mode</span>
                    <button class="toggle" aria-pressed={mode === 'light'} onClick={() => setMode('light')}>Light</button>
                    <button class="toggle" aria-pressed={mode === 'dark'} onClick={() => setMode('dark')}>Dark</button>
                </div>
            </header>

            <nav class="controls" style={{ marginBottom: 40 }}>
                {SECTIONS.map(([id, label]) => (
                    <a key={id} class="toggle" href={`#${id}`}>{label}</a>
                ))}
            </nav>

            <Showcase id="buttons" title="Buttons"
                blurb="Press compresses the surface — shadow and position only, never the label.">
                <Demo title="Variants">
                    <Button>Primary</Button>
                    <Button variant="secondary">Secondary</Button>
                    <Button variant="outline">Outline</Button>
                    <Button variant="ghost">Ghost</Button>
                    <Button variant="destructive">Destructive</Button>
                </Demo>
                <Demo title="Sizes">
                    <Button size="sm">Small</Button>
                    <Button>Medium</Button>
                    <Button size="lg">Large</Button>
                </Demo>
                <Demo title="States" note="Tab to a button to see the focus ring.">
                    <Button>Rest</Button>
                    <Button disabled>Disabled</Button>
                </Demo>
                <Demo title="Button group">
                    <ButtonGroup>
                        <Button variant="secondary">Day</Button>
                        <Button variant="secondary">Week</Button>
                        <Button variant="secondary">Month</Button>
                    </ButtonGroup>
                </Demo>
                <Demo title="Link">
                    <Button variant="link">A text link</Button>
                </Demo>
                <Demo title="Kbd">
                    <Kbd>⌘</Kbd><Kbd>K</Kbd>
                </Demo>
            </Showcase>

            <Showcase id="content" title="Content"
                blurb="Hierarchy through size and weight first. Colour is the last resort, never the first.">
                <Demo title="Headings" column>
                    <Heading level={1}>Heading level 1</Heading>
                    <Heading level={2}>Heading level 2</Heading>
                    <Heading level={3}>Heading level 3</Heading>
                </Demo>
                <Demo title="Text" column>
                    <Text>Primary body text</Text>
                    <Text tone="secondary">Secondary supporting text</Text>
                    <Text tone="muted">Muted text</Text>
                </Demo>
                <Demo title="Code">
                    <Code>--control-active</Code>
                </Demo>
                <Demo title="Avatar">
                    <Avatar name="Ada Lovelace" />
                    <Avatar name="Grace Hopper" status="success" />
                </Demo>
                <Demo title="Badge" note="Status reports an outcome — never an interaction state.">
                    <Badge>Neutral</Badge>
                    <Badge variant="outline">Outline</Badge>
                </Demo>
            </Showcase>

            <Showcase id="inputs" title="Inputs"
                blurb="Inputs read as recessed — the inverse of a raised control.">
                <Demo title="Text input" column>
                    <Input placeholder="Type here" />
                    <Input placeholder="Disabled" disabled />
                </Demo>
                <Demo title="Text area" column>
                    <Textarea placeholder="Longer text…" rows={3} />
                </Demo>
                <Demo title="Field" column>
                    <Field label="Email">
                        <Input type="email" placeholder="you@example.com" />
                    </Field>
                </Demo>
                <Demo title="Slider" column>
                    <Slider label="Contrast" min={0} max={100} value={slider}
                        onInput={(e: any) => setSlider(Number(e.currentTarget.value))} />
                    <Text size="sm" tone="secondary">Value: {slider}</Text>
                </Demo>
            </Showcase>

            <Showcase id="selection" title="Selection"
                blurb="Every selected state is legible without colour — shape and fill carry it.">
                <Demo title="Checkbox" column>
                    <Checkbox label="Checked" checked={checked} onToggle={setChecked} />
                    <Checkbox label="Unchecked" checked={false} onToggle={() => {}} />
                    <Checkbox label="Disabled" checked={false} onToggle={() => {}} disabled />
                </Demo>
                <Demo title="Switch" column>
                    <Switch label="Notifications" checked={on} onToggle={setOn} />
                </Demo>
                <Demo title="Radio" column>
                    <RadioGroup value={radio} onChange={setRadio} options={[
                        { value: 'rest', label: 'Rest' },
                        { value: 'hover', label: 'Hover' },
                        { value: 'active', label: 'Active' },
                    ]} />
                </Demo>
            </Showcase>

            <Showcase id="containers" title="Containers"
                blurb="Surfaces stack: page → surface → card → overlay.">
                <Demo title="Card" column>
                    <Card>
                        <CardHeader>
                            <CardTitle>Card title</CardTitle>
                            <CardDescription>Cards sit on a raised surface.</CardDescription>
                        </CardHeader>
                        <CardContent><Text size="sm" tone="secondary">Content.</Text></CardContent>
                    </Card>
                </Demo>
                <Demo title="Collapsible" column>
                    <Collapsible trigger="Show details">
                        <Text size="sm" tone="secondary">Disclosed content.</Text>
                    </Collapsible>
                </Demo>
            </Showcase>

            <Showcase id="feedback" title="Feedback"
                blurb="Status colours report outcomes. They are never used for interaction state.">
                <Demo title="Alert" column>
                    <Alert title="Informational message" />
                    <Alert variant="destructive" title="That email is invalid" />
                </Demo>
                <Demo title="Spinner"><Spinner /></Demo>
                <Demo title="Skeleton" column>
                    <Skeleton width={220} height={12} />
                    <Skeleton width={160} height={12} />
                </Demo>
                <Demo title="Progress" column>
                    <Progress value={60} />
                </Demo>
            </Showcase>

            <Showcase id="layout" title="Layout"
                blurb="Whitespace is structure, on a 4px rhythm.">
                <Demo title="Stacks" column>
                    <Row><Badge>One</Badge><Badge>Two</Badge><Badge>Three</Badge></Row>
                    <Stack gap={2}>
                        <Text size="sm">Vertical A</Text>
                        <Text size="sm">Vertical B</Text>
                    </Stack>
                </Demo>
                <Demo title="Divider" column>
                    <Text size="sm">Above</Text>
                    <Separator />
                    <Text size="sm">Below</Text>
                </Demo>
            </Showcase>

            <Showcase id="navigation" title="Navigation"
                blurb="The selected item is an active control — neutral until accent is opted in.">
                <Demo title="Tabs" column>
                    <Tabs tabs={[
                        { value: 'rest', label: 'Rest' },
                        { value: 'hover', label: 'Hover' },
                        { value: 'active', label: 'Active' },
                    ]} />
                </Demo>
                <Demo title="Breadcrumbs" column>
                    <Breadcrumbs items={['Design system', 'DRAMS', 'Preact']} />
                </Demo>
            </Showcase>

            <Showcase id="data" title="Data"
                blurb="Dense information stays calm: no zebra stripes, no decorative rules.">
                <Demo title="Table" column>
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                            <tr>
                                <th style={{ textAlign: 'left', padding: 'var(--space-2)' }}>Token</th>
                                <th style={{ textAlign: 'left', padding: 'var(--space-2)' }}>Role</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td style={{ padding: 'var(--space-2)' }}><Code>--accent</Code></td>
                                <td style={{ padding: 'var(--space-2)' }}>brand, opt-in</td>
                            </tr>
                            <tr>
                                <td style={{ padding: 'var(--space-2)' }}><Code>--control-active</Code></td>
                                <td style={{ padding: 'var(--space-2)' }}>engaged, neutral</td>
                            </tr>
                        </tbody>
                    </table>
                </Demo>
                <Demo title="List" column>
                    <List items={['Unobtrusive', 'Honest', 'Long-lasting']} />
                </Demo>
            </Showcase>

            <Showcase id="accent" title="Accent"
                blurb="DRAMS ships neutral and complete. Nothing renders brand colour until a component opts in with accent. Each pair is the same component: default left, accent right.">
                <Demo title="Button">
                    <Button>Save</Button>
                    <Button accent>Save</Button>
                </Demo>
                <Demo title="Checkbox">
                    <Checkbox label="default" checked={checked} onToggle={setChecked} />
                    <Checkbox label="accent" checked={accentChecked} onToggle={setAccentChecked} accent />
                </Demo>
                <Demo title="Switch">
                    <Switch checked={on} onToggle={setOn} />
                    <Switch checked={accentOn} onToggle={setAccentOn} accent />
                </Demo>
                <Demo title="Slider" column>
                    <Slider label="Contrast" min={0} max={100} value={slider}
                        onInput={(e: any) => setSlider(Number(e.currentTarget.value))} />
                    <Slider label="Contrast (accent)" min={0} max={100} value={slider} accent
                        onInput={(e: any) => setSlider(Number(e.currentTarget.value))} />
                </Demo>
                <Demo title="Progress" column>
                    <Progress value={60} />
                    <Progress value={60} accent />
                </Demo>
                <Demo title="Tabs" column>
                    <Tabs tabs={[{ value: 'a', label: 'Neutral' }, { value: 'b', label: 'Two' }]} />
                    <Tabs accent tabs={[{ value: 'a', label: 'Accent' }, { value: 'b', label: 'Two' }]} />
                </Demo>
            </Showcase>
        </div>
    )
}
