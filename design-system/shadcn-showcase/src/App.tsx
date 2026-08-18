import { useEffect, useState, type ReactNode } from 'react'
import {
    Button, Input, Textarea, Checkbox, Switch, Slider, RadioGroup, RadioGroupItem,
    Tabs, TabsList, TabsTrigger, Progress, Separator, Label, Badge, Card, Skeleton,
} from '@/components/ui'

const SECTIONS = [
    ['buttons', 'Buttons'], ['inputs', 'Inputs'], ['selection', 'Selection'],
    ['display', 'Display'], ['accent', 'Accent'],
] as const

function Showcase({ id, title, blurb, children }: {
    id: string; title: string; blurb: string; children: ReactNode
}) {
    return (
        <section className="showcase" id={id}>
            <h2>{title}</h2>
            <p className="blurb">{blurb}</p>
            <div className="grid-demos">{children}</div>
        </section>
    )
}

function Demo({ title, children, note, column }: {
    title: string; children: ReactNode; note?: string; column?: boolean
}) {
    return (
        <div className="demo">
            <h3>{title}</h3>
            <div className={column ? 'col' : 'row'}>{children}</div>
            {note ? <p className="note">{note}</p> : null}
        </div>
    )
}

export default function App() {
    const [mode, setMode] = useState<'light' | 'dark'>('light')
    const [checked, setChecked] = useState(true)
    const [accChecked, setAccChecked] = useState(true)
    const [on, setOn] = useState(true)
    const [accOn, setAccOn] = useState(true)
    const [radio, setRadio] = useState('a')
    const [slider, setSlider] = useState([60])

    useEffect(() => {
        document.documentElement.classList.toggle('dark', mode === 'dark')
    }, [mode])

    return (
        <div className="page">
            <header className="masthead">
                <div>
                    <h1>shadcn × DRAMS</h1>
                    <p>
                        Stock shadcn/ui — its own colours, its own <code>--radius</code>, its own
                        ring. DRAMS does not repaint it. DRAMS contributes one thing:{' '}
                        <code>accent</code>, the opt-in brand seam. Note the naming — shadcn
                        already uses <code>--accent</code> for hover greys, so the brand token
                        here is <code>--brand</code>.
                    </p>
                </div>
                <div className="controls">
                    <span className="controls-label">Mode</span>
                    <button className="toggle" aria-pressed={mode === 'light'} onClick={() => setMode('light')}>Light</button>
                    <button className="toggle" aria-pressed={mode === 'dark'} onClick={() => setMode('dark')}>Dark</button>
                </div>
            </header>

            <nav className="controls" style={{ marginBottom: 40 }}>
                {SECTIONS.map(([id, label]) => (
                    <a key={id} className="toggle" href={`#${id}`}>{label}</a>
                ))}
            </nav>

            <Showcase id="buttons" title="Buttons" blurb="Stock shadcn variants and sizes, untouched.">
                <Demo title="Variants">
                    <Button>Default</Button>
                    <Button variant="secondary">Secondary</Button>
                    <Button variant="outline">Outline</Button>
                    <Button variant="ghost">Ghost</Button>
                    <Button variant="destructive">Destructive</Button>
                    <Button variant="link">Link</Button>
                </Demo>
                <Demo title="Sizes">
                    <Button size="sm">Small</Button>
                    <Button>Default</Button>
                    <Button size="lg">Large</Button>
                </Demo>
                <Demo title="States">
                    <Button>Rest</Button>
                    <Button disabled>Disabled</Button>
                </Demo>
            </Showcase>

            <Showcase id="inputs" title="Inputs" blurb="Text entry, stock shadcn.">
                <Demo title="Input" column>
                    <Label htmlFor="a">Project</Label>
                    <Input id="a" placeholder="Type here" />
                    <Input placeholder="Disabled" disabled />
                </Demo>
                <Demo title="Textarea" column>
                    <Textarea placeholder="Longer text…" />
                </Demo>
                <Demo title="Slider" column>
                    <Slider value={slider} onValueChange={setSlider} max={100} step={1} />
                    <span className="text-sm text-muted-foreground">Value: {slider[0]}</span>
                </Demo>
            </Showcase>

            <Showcase id="selection" title="Selection" blurb="Every selected state is legible without colour.">
                <Demo title="Checkbox">
                    <Checkbox checked={checked} onCheckedChange={v => setChecked(!!v)} />
                    <Label>Checked</Label>
                </Demo>
                <Demo title="Switch">
                    <Switch checked={on} onCheckedChange={setOn} />
                    <Label>Notifications</Label>
                </Demo>
                <Demo title="Radio" column>
                    <RadioGroup value={radio} onValueChange={setRadio}>
                        <div className="flex items-center gap-2"><RadioGroupItem value="a" id="r1" /><Label htmlFor="r1">Starter</Label></div>
                        <div className="flex items-center gap-2"><RadioGroupItem value="b" id="r2" /><Label htmlFor="r2">Pro</Label></div>
                    </RadioGroup>
                </Demo>
                <Demo title="Tabs" column>
                    <Tabs defaultValue="a">
                        <TabsList>
                            <TabsTrigger value="a">Overview</TabsTrigger>
                            <TabsTrigger value="b">Activity</TabsTrigger>
                        </TabsList>
                    </Tabs>
                </Demo>
            </Showcase>

            <Showcase id="display" title="Display" blurb="Presentational surfaces.">
                <Demo title="Badge">
                    <Badge>Default</Badge>
                    <Badge variant="secondary">Secondary</Badge>
                    <Badge variant="outline">Outline</Badge>
                    <Badge variant="destructive">Destructive</Badge>
                </Demo>
                <Demo title="Progress" column>
                    <Progress value={60} />
                </Demo>
                <Demo title="Card" column>
                    <Card className="p-4 w-full">
                        <p className="text-sm font-medium">Card title</p>
                        <p className="text-sm text-muted-foreground">On the card surface.</p>
                    </Card>
                </Demo>
                <Demo title="Skeleton" column>
                    <Skeleton className="h-3 w-[220px]" />
                    <Skeleton className="h-3 w-[160px]" />
                </Demo>
                <Demo title="Separator" column>
                    <span className="text-sm">Above</span>
                    <Separator />
                    <span className="text-sm">Below</span>
                </Demo>
            </Showcase>

            <Showcase id="accent" title="Accent — the brand seam"
                blurb="Everything above is stock shadcn. accent is opt-in and the only thing that renders brand colour. Each pair is one component: neutral left, accent right.">
                <Demo title="Button">
                    <Button>Save</Button>
                    <Button accent>Save</Button>
                </Demo>
                <Demo title="Checkbox">
                    <Checkbox checked={checked} onCheckedChange={v => setChecked(!!v)} />
                    <Checkbox accent checked={accChecked} onCheckedChange={v => setAccChecked(!!v)} />
                </Demo>
                <Demo title="Switch">
                    <Switch checked={on} onCheckedChange={setOn} />
                    <Switch accent checked={accOn} onCheckedChange={setAccOn} />
                </Demo>
                <Demo title="Radio" column>
                    <RadioGroup value="a">
                        <div className="flex items-center gap-2"><RadioGroupItem value="a" id="n1" /><Label htmlFor="n1">Neutral</Label></div>
                    </RadioGroup>
                    <RadioGroup value="a">
                        <div className="flex items-center gap-2"><RadioGroupItem accent value="a" id="b1" /><Label htmlFor="b1">Brand</Label></div>
                    </RadioGroup>
                </Demo>
                <Demo title="Slider" column>
                    <Slider value={slider} onValueChange={setSlider} max={100} />
                    <Slider accent value={slider} onValueChange={setSlider} max={100} />
                </Demo>
                <Demo title="Progress" column>
                    <Progress value={60} />
                    <Progress accent value={60} />
                </Demo>
                <Demo title="Badge">
                    <Badge>Neutral</Badge>
                    <Badge accent>Brand</Badge>
                </Demo>
                <Demo title="Input" column note="Focus each field — the ring carries the brand.">
                    <Input placeholder="Focus me" />
                    <Input accent placeholder="Focus me" />
                </Demo>
            </Showcase>
        </div>
    )
}
