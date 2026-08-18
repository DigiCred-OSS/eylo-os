import { useState, useEffect } from 'react'
import {
    // Controls
    Button,
    ButtonGroup,
    ButtonGroupSeparator,
    ButtonGroupText,
    Input,
    Textarea,
    Checkbox,
    RadioGroup,
    RadioGroupItem,
    Switch,
    Label,
    Select,
    SelectContent,
    SelectGroup,
    SelectItem,
    SelectLabel,
    SelectSeparator,
    SelectTrigger,
    SelectValue,
    Toggle,
    Slider,

    // Compositions
    Badge,

    // Structural
    Section,
    Article,
    Header,
    Footer,
    Nav,
    Aside,

    // Layout
    Box,
    Flex,
    Grid,
    Stack,
    AspectRatio,
    ScrollArea,
    ScrollBar,

    // Typography
    Heading,
    Text,
    Caption,
    Code,
    Kbd,
    KbdGroup,

    // Form
    Form,
    FormField,
    FormDescription,
    FormMessage,
    Fieldset,
    Legend,

    // Feedback
    Avatar,
    AvatarImage,
    AvatarFallback,
    AvatarBadge,
    AvatarGroup,
    AvatarGroupCount,
    Image,
    Progress,
    Separator,
    Skeleton,
    Spinner,

    // Card
    Card,
    CardHeader,
    CardTitle,
    CardDescription,
    CardAction,
    CardContent,
    CardFooter,

    // Dropdown Menu
    DropdownMenu,
    DropdownMenuTrigger,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuCheckboxItem,
    DropdownMenuRadioItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuShortcut,
    DropdownMenuSub,
    DropdownMenuSubContent,
    DropdownMenuSubTrigger,
    DropdownMenuRadioGroup,

    // Tooltip
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,

    // Tabs
    Tabs,
    TabsList,
    TabsTrigger,
    TabsContent,

    // Dialog
    Dialog,
    DialogTrigger,
    DialogContent,
    DialogHeader,
    DialogFooter,
    DialogTitle,
    DialogDescription,
    DialogClose,

    // Alert Dialog
    AlertDialog,
    AlertDialogTrigger,
    AlertDialogContent,
    AlertDialogHeader,
    AlertDialogFooter,
    AlertDialogTitle,
    AlertDialogDescription,
    AlertDialogAction,
    AlertDialogCancel,

    // Popover
    Popover,
    PopoverTrigger,
    PopoverContent,

    // Sheet
    Sheet,
    SheetTrigger,
    SheetContent,
    SheetHeader,
    SheetFooter,
    SheetTitle,
    SheetDescription,
    SheetClose,

    // Alert
    Alert,
    AlertTitle,
    AlertDescription,
} from './components'

/**
 * DRAMS3 Showcase
 *
 * Demonstrates the design system principles:
 * - Physical surfaces (raised vs pressed)
 * - Accent color ONLY on interaction states
 * - Status colors ONLY for semantic feedback
 * - Visible state differences without labels
 */
export default function App() {
    const [radioValue, setRadioValue] = useState('option1')
    const [checkboxChecked, setCheckboxChecked] = useState(false)
    const [switchOn, setSwitchOn] = useState(false)
    const [togglePressed, setTogglePressed] = useState(false)
    const [sliderValue, setSliderValue] = useState([50])
    const [rangeValue, setRangeValue] = useState([25, 75])
    const [progressValue, setProgressValue] = useState(45)
    const [colorMode, setColorMode] = useState<'light' | 'dark' | 'system'>('system')
    const [theme, setTheme] = useState<'default' | 'skeuomorphic' | 'neumorphic'>('default')

    // Two independent axes: data-mode carries light/dark, data-theme carries
    // the named theme. Removing data-mode hands control back to
    // prefers-color-scheme.
    //
    // This used to set the `light`/`dark` class as well, because data-mode
    // reached the named themes but not the default one. The default theme now
    // honours it too, so one attribute is enough. (.dark still works — it is
    // kept in semantic.css as an equivalent for Tailwind-style consumers.)
    useEffect(() => {
        const root = document.documentElement

        if (colorMode === 'system') root.removeAttribute('data-mode')
        else root.setAttribute('data-mode', colorMode)

        if (theme === 'default') root.removeAttribute('data-theme')
        else root.setAttribute('data-theme', theme)
    }, [colorMode, theme])

    return (
        <div className="drams-page">
            <div className="showcase-page">
                {/* Header */}
                <header className="showcase-header">
                    <Flex justify="between" align="center" style={{ marginBottom: 'var(--space-4)' }}>
                        <h1 className="showcase-title">DRAMS3</h1>
                        <Flex gap={4} align="center">
                            {/* Theme Selector */}
                            <Flex gap={1} align="center">
                                <Text size="sm" color="muted" style={{ marginRight: '4px' }}>Theme:</Text>
                                <Button
                                    size="sm"
                                    variant={theme === 'default' ? 'default' : 'ghost'}
                                    onClick={() => setTheme('default')}
                                >
                                    Default
                                </Button>
                                <Button
                                    size="sm"
                                    variant={theme === 'skeuomorphic' ? 'default' : 'ghost'}
                                    onClick={() => setTheme('skeuomorphic')}
                                >
                                    Skeuomorphic
                                </Button>
                                <Button
                                    size="sm"
                                    variant={theme === 'neumorphic' ? 'default' : 'ghost'}
                                    onClick={() => setTheme('neumorphic')}
                                >
                                    Neumorphic
                                </Button>
                            </Flex>
                            <Separator orientation="vertical" style={{ height: '24px' }} />
                            {/* Color Mode Selector */}
                            <Flex gap={1} align="center">
                                <Button
                                    size="sm"
                                    variant={colorMode === 'light' ? 'default' : 'ghost'}
                                    onClick={() => setColorMode('light')}
                                >
                                    ☀️
                                </Button>
                                <Button
                                    size="sm"
                                    variant={colorMode === 'dark' ? 'default' : 'ghost'}
                                    onClick={() => setColorMode('dark')}
                                >
                                    🌙
                                </Button>
                                <Button
                                    size="sm"
                                    variant={colorMode === 'system' ? 'default' : 'ghost'}
                                    onClick={() => setColorMode('system')}
                                >
                                    💻
                                </Button>
                            </Flex>
                        </Flex>
                    </Flex>
                    <p className="showcase-subtitle">
                        A design system grounded in Dieter Rams' philosophy — "less, but better".
                        Physical, restrained, and honest. UI elements feel like machined Braun controls,
                        not flat graphics.
                    </p>
                </header>

                {/* Accent — the brand seam */}
                <section className="showcase-section">
                    <h2 className="showcase-section-title">Accent — the brand seam</h2>
                    <p className="showcase-section-description">
                        DRAMS ships neutral and complete. Nothing renders brand colour until a
                        component opts in with <code className="drams-code">accent</code>. Each pair
                        below is the same component: default on the left, accent on the right.
                        Strip every accent from a product and it must still be fully usable.
                    </p>

                    <div className="showcase-grid">
                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Button</h3>
                            <Flex gap={3} align="center">
                                <Button>Save</Button>
                                <Button accent>Save</Button>
                            </Flex>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Checkbox</h3>
                            <Flex gap={4} align="center">
                                <Checkbox defaultChecked id="acc-cb-neutral" />
                                <Checkbox defaultChecked accent id="acc-cb-brand" />
                                <Text size="sm" color="muted">default · accent</Text>
                            </Flex>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Switch</h3>
                            <Flex gap={4} align="center">
                                <Switch defaultChecked />
                                <Switch defaultChecked accent />
                                <Text size="sm" color="muted">default · accent</Text>
                            </Flex>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Radio</h3>
                            <Flex gap={4} align="center">
                                <RadioGroup defaultValue="a">
                                    <RadioGroupItem value="a" id="acc-r-neutral" />
                                </RadioGroup>
                                <RadioGroup defaultValue="a">
                                    <RadioGroupItem value="a" accent id="acc-r-brand" />
                                </RadioGroup>
                                <Text size="sm" color="muted">default · accent</Text>
                            </Flex>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Input</h3>
                            <Stack gap={3}>
                                <Input placeholder="Focus me — neutral ring" />
                                <Input accent placeholder="Focus me — brand ring" />
                            </Stack>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Slider</h3>
                            <Stack gap={4}>
                                <Slider defaultValue={[60]} max={100} />
                                <Slider defaultValue={[60]} max={100} accent />
                            </Stack>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Progress</h3>
                            <Stack gap={3}>
                                <Progress value={60} />
                                <Progress value={60} accent />
                            </Stack>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Tabs</h3>
                            <Stack gap={3}>
                                <Tabs defaultValue="a">
                                    <TabsList variant="line">
                                        <TabsTrigger value="a">Neutral</TabsTrigger>
                                        <TabsTrigger value="b">Two</TabsTrigger>
                                    </TabsList>
                                </Tabs>
                                <Tabs defaultValue="a">
                                    <TabsList variant="line" accent>
                                        <TabsTrigger value="a">Accent</TabsTrigger>
                                        <TabsTrigger value="b">Two</TabsTrigger>
                                    </TabsList>
                                </Tabs>
                            </Stack>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Toggle</h3>
                            <Flex gap={3} align="center">
                                <Toggle defaultPressed>Neutral</Toggle>
                                <Toggle defaultPressed accent>Accent</Toggle>
                            </Flex>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Swapping the brand</h3>
                            <Text size="sm" color="muted">
                                Braun Orange is a default, not a requirement. Override the five{' '}
                                <code className="drams-code">--brand-primary-*</code> values in{' '}
                                <code className="drams-code">tokens/foundation.css</code> and the whole
                                system becomes another brand — no component CSS, no forks.
                            </Text>
                        </div>
                    </div>
                </section>

                {/* Surface Physics Demo */}
                <section className="showcase-section">
                    <h2 className="showcase-section-title">Surface Physics</h2>
                    <p className="showcase-section-description">
                        Interactive controls appear raised from the background. When pressed, they compress inward.
                        This creates affordance — you can tell what's clickable by looking.
                    </p>

                    <div className="showcase-grid">
                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Button States</h3>
                            <p className="drams-text--sm drams-text--muted" style={{ marginBottom: 'var(--space-4)' }}>
                                Hover to see lift. Click to see compression.
                                Press changes shadow only — no text/border changes.
                            </p>
                            <div className="showcase-stack">
                                <div className="showcase-row">
                                    <Button>Rest</Button>
                                    <span className="drams-caption">← Hover me, click me</span>
                                </div>
                                <div className="showcase-row">
                                    <Button disabled>Disabled</Button>
                                    <span className="drams-caption">← Flat, no depth</span>
                                </div>
                            </div>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Button Variants (shadcn API + accent)</h3>
                            <p className="drams-text--sm drams-text--muted" style={{ marginBottom: 'var(--space-4)' }}>
                                shadcn-compatible + "accent" modifier (DRAMS3 extension).
                                All variants follow physical press metaphor.
                            </p>
                            <div className="showcase-stack">
                                <div className="showcase-row">
                                    <Button>Default</Button>
                                    <Button accent>Accent</Button>
                                    <Button variant="outline">Outline</Button>
                                    <Button variant="outline" accent>Outline Accent</Button>
                                </div>
                                <div className="showcase-row">
                                    <Button variant="secondary">Secondary</Button>
                                    <Button variant="ghost">Ghost</Button>
                                    <Button variant="destructive">Destructive</Button>
                                </div>
                                <div className="showcase-row">
                                    <Button variant="link">Link</Button>
                                </div>
                            </div>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Button Sizes</h3>
                            <p className="drams-text--sm drams-text--muted" style={{ marginBottom: 'var(--space-4)' }}>
                                From xs (28px) to lg (44px). Icon sizes for square buttons.
                            </p>
                            <div className="showcase-stack">
                                <div className="showcase-row" style={{ alignItems: 'center' }}>
                                    <Button size="xs">XS</Button>
                                    <Button size="sm">Small</Button>
                                    <Button>Default</Button>
                                    <Button size="lg">Large</Button>
                                </div>
                                <div className="showcase-row" style={{ alignItems: 'center' }}>
                                    <Button size="icon-xs">⚙</Button>
                                    <Button size="icon-sm">⚙</Button>
                                    <Button size="icon">⚙</Button>
                                    <Button size="icon-lg">⚙</Button>
                                    <span className="drams-caption">← Icon sizes</span>
                                </div>
                            </div>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Button Groups (shadcn API)</h3>
                            <p className="drams-text--sm drams-text--muted" style={{ marginBottom: 'var(--space-4)' }}>
                                Group related buttons with connected styling.
                                Supports horizontal and vertical orientations.
                            </p>
                            <div className="showcase-stack">
                                <div className="showcase-row" style={{ alignItems: 'center' }}>
                                    <ButtonGroup>
                                        <Button >Left</Button>
                                        <Button >Center</Button>
                                        <Button >Right</Button>
                                    </ButtonGroup>
                                    <span className="drams-caption">← Horizontal (default)</span>
                                </div>
                                <div className="showcase-row" style={{ alignItems: 'flex-start' }}>
                                    <ButtonGroup orientation="vertical">
                                        <Button variant="outline">Top</Button>
                                        <Button variant="outline">Middle</Button>
                                        <Button variant="outline">Bottom</Button>
                                    </ButtonGroup>
                                    <span className="drams-caption">← Vertical</span>
                                </div>
                                <div className="showcase-row" style={{ alignItems: 'center' }}>
                                    <ButtonGroup>
                                        <Button>Save</Button>
                                        <ButtonGroupSeparator />
                                        <Button size="icon">▼</Button>
                                    </ButtonGroup>
                                    <span className="drams-caption">← Split button with separator</span>
                                </div>
                                <div className="showcase-row" style={{ alignItems: 'center' }}>
                                    <ButtonGroup>
                                        <ButtonGroupText>Label:</ButtonGroupText>
                                        <Input placeholder="Enter value..." style={{ width: 160 }} />
                                        <Button>Submit</Button>
                                    </ButtonGroup>
                                    <span className="drams-caption">← With input and text</span>
                                </div>
                                <div className="showcase-row" style={{ alignItems: 'center' }}>
                                    <ButtonGroup>
                                        <ButtonGroup>
                                            <Button variant="outline">A</Button>
                                            <Button variant="outline">B</Button>
                                        </ButtonGroup>
                                        <ButtonGroup>
                                            <Button variant="outline">C</Button>
                                            <Button variant="outline">D</Button>
                                        </ButtonGroup>
                                    </ButtonGroup>
                                    <span className="drams-caption">← Nested groups</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </section>

                {/* Accent Color Rules */}
                <section className="showcase-section">
                    <h2 className="showcase-section-title">Accent Color Rules</h2>
                    <p className="showcase-section-description">
                        Braun Orange (#FF5500) appears ONLY when something becomes active, selected, or enabled.
                        It never appears on resting states. It's never decorative.
                    </p>

                    <div className="showcase-grid">
                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Checkbox</h3>
                            <div className="showcase-stack">
                                <div className="comparison">
                                    <div className="comparison-item">
                                        <Checkbox />
                                        <div className="comparison-label">Unselected (neutral)</div>
                                    </div>
                                    <div className="comparison-item">
                                        <Checkbox defaultChecked />
                                        <div className="comparison-label">Selected (default)</div>
                                    </div>
                                    <div className="comparison-item">
                                        <Checkbox defaultChecked accent />
                                        <div className="comparison-label">Selected (accent)</div>
                                    </div>
                                </div>
                                <label className="drams-checkbox-label">
                                    <Checkbox
                                        checked={checkboxChecked}
                                        onCheckedChange={(checked) => setCheckboxChecked(checked === true)}
                                    />
                                    <span>Interactive checkbox — click me</span>
                                </label>
                            </div>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Radio</h3>
                            <div className="showcase-stack">
                                <div className="comparison">
                                    <div className="comparison-item">
                                        <div className="drams-radio" />
                                        <div className="comparison-label">Unselected (neutral)</div>
                                    </div>
                                    <div className="comparison-item">
                                        <div className="drams-radio" data-state="checked">
                                            <span className="drams-radio-indicator" />
                                        </div>
                                        <div className="comparison-label">Selected (default)</div>
                                    </div>
                                    <div className="comparison-item">
                                        <div className="drams-radio accent" data-state="checked">
                                            <span className="drams-radio-indicator" />
                                        </div>
                                        <div className="comparison-label">Selected (accent)</div>
                                    </div>
                                </div>
                                <RadioGroup value={radioValue} onValueChange={setRadioValue}>
                                    <label className="drams-radio-label">
                                        <RadioGroupItem value="option1" />
                                        <span>Option 1</span>
                                    </label>
                                    <label className="drams-radio-label">
                                        <RadioGroupItem value="option2" />
                                        <span>Option 2</span>
                                    </label>
                                    <label className="drams-radio-label">
                                        <RadioGroupItem value="option3" />
                                        <span>Option 3</span>
                                    </label>
                                </RadioGroup>
                            </div>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Switch</h3>
                            <div className="showcase-stack">
                                <div className="comparison">
                                    <div className="comparison-item">
                                        <div className="drams-switch">
                                            <span className="drams-switch-thumb" />
                                        </div>
                                        <div className="comparison-label">OFF (neutral)</div>
                                    </div>
                                    <div className="comparison-item">
                                        <div className="drams-switch" data-state="checked">
                                            <span className="drams-switch-thumb" />
                                        </div>
                                        <div className="comparison-label">ON (default)</div>
                                    </div>
                                    <div className="comparison-item">
                                        <div className="drams-switch accent" data-state="checked">
                                            <span className="drams-switch-thumb" />
                                        </div>
                                        <div className="comparison-label">ON (accent)</div>
                                    </div>
                                </div>
                                <label className="drams-switch-label">
                                    <Switch
                                        checked={switchOn}
                                        onCheckedChange={setSwitchOn}
                                    />
                                    <span>Enable feature</span>
                                </label>
                            </div>
                        </div>
                    </div>
                </section>

                {/* Status Colors */}
                <section className="showcase-section">
                    <h2 className="showcase-section-title">Status Colors — Semantic Feedback Only</h2>
                    <p className="showcase-section-description">
                        Green, red, and blue appear ONLY to communicate outcomes: success, error, information.
                        They never appear on buttons by default. They never indicate interaction states.
                    </p>

                    <div className="showcase-grid">
                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Alerts (shadcn API)</h3>
                            <div className="showcase-stack">
                                <Alert>
                                    <AlertTitle>Heads up!</AlertTitle>
                                    <AlertDescription>You can add components using the CLI.</AlertDescription>
                                </Alert>
                                <Alert variant="destructive">
                                    <AlertTitle>Error</AlertTitle>
                                    <AlertDescription>Something went wrong. Please try again.</AlertDescription>
                                </Alert>
                            </div>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Badges</h3>
                            <div className="showcase-stack">
                                <div className="showcase-row">
                                    <Badge>Default</Badge>
                                    <Badge variant="secondary">Secondary</Badge>
                                    <Badge variant="destructive">Destructive</Badge>
                                    <Badge variant="outline">Outline</Badge>
                                </div>
                                <div className="showcase-row">
                                    <Badge active>Active</Badge>
                                    <Badge variant="outline" active>Outline Active</Badge>
                                    <span className="drams-caption">← Active state (selected)</span>
                                </div>
                            </div>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Input Validation</h3>
                            <div className="showcase-stack">
                                <div>
                                    <Label htmlFor="input-default">Default</Label>
                                    <Input id="input-default" placeholder="Normal input" />
                                </div>
                                <div>
                                    <Label htmlFor="input-accent">Accent Focus</Label>
                                    <Input id="input-accent" accent placeholder="Accent focus ring" />
                                </div>
                                <div>
                                    <Label htmlFor="input-error">Invalid</Label>
                                    <Input id="input-error" aria-invalid placeholder="Invalid input" defaultValue="bad@" />
                                    <span className="drams-field-error">Please enter a valid email address</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </section>

                {/* Input States */}
                <section className="showcase-section">
                    <h2 className="showcase-section-title">Form Input States</h2>
                    <p className="showcase-section-description">
                        Inputs appear as inset surfaces — ready for content. Focus shows accent border.
                        All states are visually distinct without labels.
                    </p>

                    <div className="showcase-grid">
                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Text Input</h3>
                            <div className="showcase-stack">
                                <div>
                                    <Label htmlFor="demo-input">Label</Label>
                                    <Input id="demo-input" placeholder="Click to focus..." />
                                    <span className="drams-field-helper">Helper text appears here</span>
                                </div>
                                <div>
                                    <Label htmlFor="demo-disabled">Disabled</Label>
                                    <Input id="demo-disabled" disabled placeholder="Cannot edit" />
                                </div>
                            </div>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Size Variants</h3>
                            <div className="showcase-stack">
                                <Input data-size="sm" placeholder="Small input" />
                                <Input placeholder="Default input" />
                                <Input data-size="lg" placeholder="Large input" />
                            </div>
                        </div>
                    </div>
                </section>

                {/* Side-by-Side Comparison */}
                <section className="showcase-section">
                    <h2 className="showcase-section-title">State Comparison</h2>
                    <p className="showcase-section-description">
                        Every state must be visually distinguishable without reading labels.
                        If two states look the same, the design has failed.
                    </p>

                    <div className="demo-area">
                        <div className="showcase-grid">
                            <div>
                                <h3 className="showcase-card-title" style={{ marginBottom: 'var(--space-4)' }}>Button States</h3>
                                <div className="showcase-stack">
                                    <div className="state-demo">
                                        <span className="state-label">Rest:</span>
                                        <Button>Button</Button>
                                    </div>
                                    <div className="state-demo">
                                        <span className="state-label">Destructive:</span>
                                        <Button variant="destructive">Button</Button>
                                    </div>
                                    <div className="state-demo">
                                        <span className="state-label">Secondary:</span>
                                        <Button variant="secondary">Button</Button>
                                    </div>
                                    <div className="state-demo">
                                        <span className="state-label">Ghost:</span>
                                        <Button variant="ghost">Button</Button>
                                    </div>
                                    <div className="state-demo">
                                        <span className="state-label">Disabled:</span>
                                        <Button disabled>Button</Button>
                                    </div>
                                </div>
                            </div>

                            <div>
                                <h3 className="showcase-card-title" style={{ marginBottom: 'var(--space-4)' }}>Toggle Controls</h3>
                                <div className="showcase-stack">
                                    <div className="state-demo">
                                        <span className="state-label">Unchecked:</span>
                                        <Checkbox />
                                        <div className="drams-radio" />
                                        <div className="drams-switch"><span className="drams-switch-thumb" /></div>
                                    </div>
                                    <div className="state-demo">
                                        <span className="state-label">Checked:</span>
                                        <Checkbox defaultChecked />
                                        <div className="drams-radio" data-state="checked"><span className="drams-radio-indicator" /></div>
                                        <div className="drams-switch" data-state="checked"><span className="drams-switch-thumb" /></div>
                                    </div>
                                    <div className="state-demo">
                                        <span className="state-label">Disabled:</span>
                                        <Checkbox disabled />
                                        <div className="drams-radio" data-disabled />
                                        <div className="drams-switch" data-disabled><span className="drams-switch-thumb" /></div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </section>

                {/* Structural Primitives */}
                <section className="showcase-section">
                    <h2 className="showcase-section-title">Structural Primitives</h2>
                    <p className="showcase-section-description">
                        Semantic HTML replacements that provide proper document structure.
                        These are the building blocks for page layout.
                    </p>

                    <div className="showcase-grid">
                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Page Structure</h3>
                            <p className="drams-text--sm drams-text--muted" style={{ marginBottom: 'var(--space-4)' }}>
                                Page, Header, Nav, Footer, Aside, Section, Article
                            </p>
                            <Box bordered style={{ overflow: 'hidden' }}>
                                <Header>
                                    <Nav>
                                        <Text as="span" size="sm" style={{ fontWeight: 600 }}>Logo</Text>
                                        <Flex gap={2}>
                                            <Button variant="ghost" size="sm">Home</Button>
                                            <Button variant="ghost" size="sm">About</Button>
                                            <Button variant="ghost" size="sm">Contact</Button>
                                        </Flex>
                                    </Nav>
                                </Header>
                                <Flex>
                                    <Box style={{ flex: 1, padding: 'var(--space-4)' }}>
                                        <Article>
                                            <Heading level={4}>Article Title</Heading>
                                            <Text size="sm" color="secondary">
                                                This is article content inside a semantic article element.
                                            </Text>
                                        </Article>
                                    </Box>
                                    <Aside style={{ width: 120, borderLeft: '1px solid var(--border-default)' }}>
                                        <Text size="sm" color="muted">Sidebar</Text>
                                    </Aside>
                                </Flex>
                                <Footer style={{ borderTop: '1px solid var(--border-default)', padding: 'var(--space-3)' }}>
                                    <Caption>© 2026 DRAMS3</Caption>
                                </Footer>
                            </Box>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Section with containment</h3>
                            <p className="drams-text--sm drams-text--muted" style={{ marginBottom: 'var(--space-4)' }}>
                                Section can be contained (max-width + centered)
                            </p>
                            <Box bordered style={{ background: 'var(--surface-muted)' }}>
                                <Section contained style={{ padding: 'var(--space-4) var(--space-6)' }}>
                                    <Heading level={4}>Contained Section</Heading>
                                    <Text size="sm">Content is constrained to max-width and centered.</Text>
                                </Section>
                            </Box>
                        </div>
                    </div>
                </section>

                {/* Layout Primitives */}
                <section className="showcase-section">
                    <h2 className="showcase-section-title">Layout Primitives</h2>
                    <p className="showcase-section-description">
                        Flexible containers for organizing content. Box, Flex, Grid, and Stack
                        provide the layout building blocks.
                    </p>

                    <div className="showcase-grid">
                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Box</h3>
                            <p className="drams-text--sm drams-text--muted" style={{ marginBottom: 'var(--space-4)' }}>
                                Generic container with surface and bordered variants.
                            </p>
                            <Stack gap={3}>
                                <Box>
                                    <Text size="sm">Default Box (padding only)</Text>
                                </Box>
                                <Box surface>
                                    <Text size="sm">Surface Box (card-like)</Text>
                                </Box>
                                <Box bordered>
                                    <Text size="sm">Bordered Box</Text>
                                </Box>
                            </Stack>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Flex</h3>
                            <p className="drams-text--sm drams-text--muted" style={{ marginBottom: 'var(--space-4)' }}>
                                One-dimensional layout with direction, justify, align, gap.
                            </p>
                            <Stack gap={3}>
                                <Box bordered style={{ padding: 'var(--space-2)' }}>
                                    <Flex gap={2}>
                                        <Box surface style={{ padding: 'var(--space-2)' }}><Caption>1</Caption></Box>
                                        <Box surface style={{ padding: 'var(--space-2)' }}><Caption>2</Caption></Box>
                                        <Box surface style={{ padding: 'var(--space-2)' }}><Caption>3</Caption></Box>
                                    </Flex>
                                    <Caption>Row (default)</Caption>
                                </Box>
                                <Box bordered style={{ padding: 'var(--space-2)' }}>
                                    <Flex direction="column" gap={2}>
                                        <Box surface style={{ padding: 'var(--space-2)' }}><Caption>1</Caption></Box>
                                        <Box surface style={{ padding: 'var(--space-2)' }}><Caption>2</Caption></Box>
                                    </Flex>
                                    <Caption>Column</Caption>
                                </Box>
                                <Box bordered style={{ padding: 'var(--space-2)' }}>
                                    <Flex justify="between" align="center">
                                        <Text size="sm">Left</Text>
                                        <Text size="sm">Right</Text>
                                    </Flex>
                                    <Caption>justify="between"</Caption>
                                </Box>
                            </Stack>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Grid</h3>
                            <p className="drams-text--sm drams-text--muted" style={{ marginBottom: 'var(--space-4)' }}>
                                Two-dimensional layout with columns and gap.
                            </p>
                            <Stack gap={3}>
                                <Box bordered style={{ padding: 'var(--space-2)' }}>
                                    <Grid cols={3} gap={2}>
                                        <Box surface style={{ padding: 'var(--space-2)', textAlign: 'center' }}><Caption>1</Caption></Box>
                                        <Box surface style={{ padding: 'var(--space-2)', textAlign: 'center' }}><Caption>2</Caption></Box>
                                        <Box surface style={{ padding: 'var(--space-2)', textAlign: 'center' }}><Caption>3</Caption></Box>
                                        <Box surface style={{ padding: 'var(--space-2)', textAlign: 'center' }}><Caption>4</Caption></Box>
                                        <Box surface style={{ padding: 'var(--space-2)', textAlign: 'center' }}><Caption>5</Caption></Box>
                                        <Box surface style={{ padding: 'var(--space-2)', textAlign: 'center' }}><Caption>6</Caption></Box>
                                    </Grid>
                                    <Caption>cols={3}</Caption>
                                </Box>
                            </Stack>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Stack</h3>
                            <p className="drams-text--sm drams-text--muted" style={{ marginBottom: 'var(--space-4)' }}>
                                Vertical or horizontal spacing utility.
                            </p>
                            <Flex gap={4}>
                                <Box bordered style={{ padding: 'var(--space-2)' }}>
                                    <Stack gap={2}>
                                        <Box surface style={{ padding: 'var(--space-2)' }}><Caption>Item 1</Caption></Box>
                                        <Box surface style={{ padding: 'var(--space-2)' }}><Caption>Item 2</Caption></Box>
                                        <Box surface style={{ padding: 'var(--space-2)' }}><Caption>Item 3</Caption></Box>
                                    </Stack>
                                    <Caption>Vertical (default)</Caption>
                                </Box>
                                <Box bordered style={{ padding: 'var(--space-2)' }}>
                                    <Stack direction="horizontal" gap={2}>
                                        <Box surface style={{ padding: 'var(--space-2)' }}><Caption>A</Caption></Box>
                                        <Box surface style={{ padding: 'var(--space-2)' }}><Caption>B</Caption></Box>
                                        <Box surface style={{ padding: 'var(--space-2)' }}><Caption>C</Caption></Box>
                                    </Stack>
                                    <Caption>Horizontal</Caption>
                                </Box>
                            </Flex>
                        </div>
                    </div>
                </section>

                {/* Typography Primitives */}
                <section className="showcase-section">
                    <h2 className="showcase-section-title">Typography Primitives</h2>
                    <p className="showcase-section-description">
                        Text elements with semantic meaning. Typography serves content, not decoration.
                    </p>

                    <div className="showcase-grid">
                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Headings</h3>
                            <Stack gap={3}>
                                <Heading level={1}>Heading 1</Heading>
                                <Heading level={2}>Heading 2</Heading>
                                <Heading level={3}>Heading 3</Heading>
                                <Heading level={4}>Heading 4</Heading>
                            </Stack>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Text</h3>
                            <Stack gap={3}>
                                <Text size="lg">Large text for emphasis</Text>
                                <Text>Default body text for regular content.</Text>
                                <Text size="sm">Small text for compact areas</Text>
                                <Text color="secondary">Secondary color text</Text>
                                <Text color="muted">Muted color text</Text>
                            </Stack>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Caption & Code</h3>
                            <Stack gap={3}>
                                <div>
                                    <Caption>This is a caption for small helper text</Caption>
                                </div>
                                <div>
                                    <Text size="sm">
                                        Use <Code>npm install drams3</Code> to install.
                                    </Text>
                                </div>
                            </Stack>
                        </div>
                    </div>
                </section>

                {/* Select Primitive */}
                <section className="showcase-section">
                    <h2 className="showcase-section-title">Select</h2>
                    <p className="showcase-section-description">
                        Dropdown selection with full Radix UI accessibility. Follows shadcn/ui API exactly.
                        Accent color appears on focus ring and selected item indicator.
                    </p>

                    <div className="showcase-grid">
                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Basic Select</h3>
                            <Stack gap={4}>
                                <Select>
                                    <SelectTrigger style={{ width: '200px' }}>
                                        <SelectValue placeholder="Select a fruit" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="apple">Apple</SelectItem>
                                        <SelectItem value="banana">Banana</SelectItem>
                                        <SelectItem value="cherry">Cherry</SelectItem>
                                        <SelectItem value="grape">Grape</SelectItem>
                                        <SelectItem value="orange">Orange</SelectItem>
                                    </SelectContent>
                                </Select>
                                <Caption>Click to open dropdown</Caption>
                            </Stack>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Grouped Select</h3>
                            <Stack gap={4}>
                                <Select>
                                    <SelectTrigger style={{ width: '220px' }}>
                                        <SelectValue placeholder="Select a timezone" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectGroup>
                                            <SelectLabel>North America</SelectLabel>
                                            <SelectItem value="est">Eastern Time (ET)</SelectItem>
                                            <SelectItem value="cst">Central Time (CT)</SelectItem>
                                            <SelectItem value="pst">Pacific Time (PT)</SelectItem>
                                        </SelectGroup>
                                        <SelectSeparator />
                                        <SelectGroup>
                                            <SelectLabel>Europe</SelectLabel>
                                            <SelectItem value="gmt">GMT</SelectItem>
                                            <SelectItem value="cet">Central European (CET)</SelectItem>
                                            <SelectItem value="eet">Eastern European (EET)</SelectItem>
                                        </SelectGroup>
                                        <SelectSeparator />
                                        <SelectGroup>
                                            <SelectLabel>Asia</SelectLabel>
                                            <SelectItem value="jst">Japan (JST)</SelectItem>
                                            <SelectItem value="cst-asia">China (CST)</SelectItem>
                                            <SelectItem value="ist">India (IST)</SelectItem>
                                        </SelectGroup>
                                    </SelectContent>
                                </Select>
                                <Caption>Groups with labels and separators</Caption>
                            </Stack>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">States</h3>
                            <Stack gap={4}>
                                <Flex gap={4} align="center">
                                    <Select defaultValue="apple">
                                        <SelectTrigger style={{ width: '150px' }}>
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="apple">Apple</SelectItem>
                                            <SelectItem value="banana">Banana</SelectItem>
                                        </SelectContent>
                                    </Select>
                                    <Caption>With value</Caption>
                                </Flex>
                                <Flex gap={4} align="center">
                                    <Select disabled>
                                        <SelectTrigger style={{ width: '150px' }}>
                                            <SelectValue placeholder="Disabled" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="apple">Apple</SelectItem>
                                        </SelectContent>
                                    </Select>
                                    <Caption>Disabled state</Caption>
                                </Flex>
                                <Flex gap={4} align="center">
                                    <Select>
                                        <SelectTrigger style={{ width: '150px' }} aria-invalid="true">
                                            <SelectValue placeholder="Invalid" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="apple">Apple</SelectItem>
                                        </SelectContent>
                                    </Select>
                                    <Caption>Invalid state</Caption>
                                </Flex>
                                <Flex gap={4} align="center">
                                    <Select>
                                        <SelectTrigger accent style={{ width: '150px' }}>
                                            <SelectValue placeholder="Accent" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="apple">Apple</SelectItem>
                                            <SelectItem value="banana">Banana</SelectItem>
                                        </SelectContent>
                                    </Select>
                                    <Caption>Accent focus ring</Caption>
                                </Flex>
                            </Stack>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">In a Form</h3>
                            <Form>
                                <FormField>
                                    <Label htmlFor="role-select">Role</Label>
                                    <Select>
                                        <SelectTrigger id="role-select" style={{ width: '100%' }}>
                                            <SelectValue placeholder="Select a role" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="admin">Administrator</SelectItem>
                                            <SelectItem value="editor">Editor</SelectItem>
                                            <SelectItem value="viewer">Viewer</SelectItem>
                                        </SelectContent>
                                    </Select>
                                    <FormDescription>Choose the user's access level.</FormDescription>
                                </FormField>

                                <FormField invalid>
                                    <Label htmlFor="dept-select">Department</Label>
                                    <Select>
                                        <SelectTrigger id="dept-select" style={{ width: '100%' }} aria-invalid="true">
                                            <SelectValue placeholder="Select department" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="eng">Engineering</SelectItem>
                                            <SelectItem value="design">Design</SelectItem>
                                            <SelectItem value="sales">Sales</SelectItem>
                                        </SelectContent>
                                    </Select>
                                    <FormMessage>Please select a department.</FormMessage>
                                </FormField>
                            </Form>
                        </div>
                    </div>
                </section>

                {/* Form Primitives */}
                <section className="showcase-section">
                    <h2 className="showcase-section-title">Form Primitives</h2>
                    <p className="showcase-section-description">
                        Form structure elements for organizing controls. Proper semantic structure
                        with labels, descriptions, and validation messages.
                    </p>

                    <div className="showcase-grid">
                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Form with Fields</h3>
                            <Form>
                                <FormField>
                                    <Label htmlFor="name">Name</Label>
                                    <Input id="name" placeholder="Enter your name" />
                                    <FormDescription>Your full name as it appears on documents.</FormDescription>
                                </FormField>

                                <FormField>
                                    <Label htmlFor="email">Email</Label>
                                    <Input id="email" type="email" placeholder="you@example.com" />
                                </FormField>

                                <FormField invalid>
                                    <Label htmlFor="password">Password</Label>
                                    <Input id="password" type="password" aria-invalid />
                                    <FormMessage>Password must be at least 8 characters.</FormMessage>
                                </FormField>

                                <Button type="submit">Submit</Button>
                            </Form>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Fieldset & Legend</h3>
                            <Form>
                                <Fieldset>
                                    <Legend>Notification Preferences</Legend>
                                    <Stack gap={3}>
                                        <Flex align="center" gap={2}>
                                            <Checkbox id="email-notif" />
                                            <Label htmlFor="email-notif" style={{ marginBottom: 0 }}>Email notifications</Label>
                                        </Flex>
                                        <Flex align="center" gap={2}>
                                            <Checkbox id="sms-notif" />
                                            <Label htmlFor="sms-notif" style={{ marginBottom: 0 }}>SMS notifications</Label>
                                        </Flex>
                                        <Flex align="center" gap={2}>
                                            <Checkbox id="push-notif" defaultChecked />
                                            <Label htmlFor="push-notif" style={{ marginBottom: 0 }}>Push notifications</Label>
                                        </Flex>
                                    </Stack>
                                </Fieldset>

                                <Fieldset>
                                    <Legend>Frequency</Legend>
                                    <RadioGroup defaultValue="daily">
                                        <Flex align="center" gap={2}>
                                            <RadioGroupItem value="realtime" id="realtime" />
                                            <Label htmlFor="realtime" style={{ marginBottom: 0 }}>Real-time</Label>
                                        </Flex>
                                        <Flex align="center" gap={2}>
                                            <RadioGroupItem value="daily" id="daily" />
                                            <Label htmlFor="daily" style={{ marginBottom: 0 }}>Daily digest</Label>
                                        </Flex>
                                        <Flex align="center" gap={2}>
                                            <RadioGroupItem value="weekly" id="weekly" />
                                            <Label htmlFor="weekly" style={{ marginBottom: 0 }}>Weekly summary</Label>
                                        </Flex>
                                    </RadioGroup>
                                </Fieldset>
                            </Form>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Form Messages</h3>
                            <Stack gap={3}>
                                <FormMessage variant="error">This field is required.</FormMessage>
                                <FormMessage variant="success">Email verified successfully!</FormMessage>
                                <FormDescription>Helper text appears below inputs.</FormDescription>
                            </Stack>
                        </div>
                    </div>
                </section>

                {/* Textarea Primitive */}
                <section className="showcase-section">
                    <h2 className="showcase-section-title">Textarea</h2>
                    <p className="showcase-section-description">
                        Multi-line text input. Supports all Input states including disabled and invalid.
                    </p>

                    <div className="showcase-grid">
                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Basic</h3>
                            <Stack gap={3}>
                                <Textarea placeholder="Type your message here..." />
                                <Textarea placeholder="With custom rows" rows={3} />
                            </Stack>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">With Field</h3>
                            <FormField>
                                <Label htmlFor="bio">Bio</Label>
                                <Textarea id="bio" placeholder="Tell us about yourself..." />
                                <FormDescription>Max 500 characters.</FormDescription>
                            </FormField>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Disabled</h3>
                            <Textarea disabled placeholder="This textarea is disabled" defaultValue="Cannot edit this content" />
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Invalid</h3>
                            <FormField>
                                <Label htmlFor="feedback">Feedback</Label>
                                <Textarea id="feedback" aria-invalid="true" placeholder="Required field" />
                                <FormMessage variant="error">Please provide your feedback.</FormMessage>
                            </FormField>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">With Button</h3>
                            <Stack gap={3}>
                                <Textarea placeholder="What's on your mind?" />
                                <Flex justify="end">
                                    <Button>Post</Button>
                                </Flex>
                            </Stack>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Accent Focus</h3>
                            <Textarea accent placeholder="Click to see Braun Orange focus ring" />
                            <Caption style={{ marginTop: 'var(--space-2)' }}>DRAMS extension: accent focus ring</Caption>
                        </div>
                    </div>
                </section>

                {/* Avatar Primitive */}
                <section className="showcase-section">
                    <h2 className="showcase-section-title">Avatar</h2>
                    <p className="showcase-section-description">
                        User avatars with image, fallback, badges, and grouping support.
                        Follows shadcn/ui API with Radix UI primitives.
                    </p>

                    <div className="showcase-grid">
                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Basic Avatar</h3>
                            <Stack gap={4}>
                                <Flex gap={4} align="center">
                                    <Avatar>
                                        <AvatarImage src="https://github.com/shadcn.png" alt="@shadcn" />
                                        <AvatarFallback>CN</AvatarFallback>
                                    </Avatar>
                                    <Caption>With image</Caption>
                                </Flex>
                                <Flex gap={4} align="center">
                                    <Avatar>
                                        <AvatarFallback>JD</AvatarFallback>
                                    </Avatar>
                                    <Caption>Fallback only</Caption>
                                </Flex>
                                <Flex gap={4} align="center">
                                    <Avatar>
                                        <AvatarImage src="https://invalid-url.com/404.png" alt="Invalid" />
                                        <AvatarFallback>FB</AvatarFallback>
                                    </Avatar>
                                    <Caption>Fallback on error</Caption>
                                </Flex>
                            </Stack>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Sizes</h3>
                            <Flex gap={4} align="center">
                                <Avatar size="sm">
                                    <AvatarFallback>SM</AvatarFallback>
                                </Avatar>
                                <Avatar>
                                    <AvatarFallback>DF</AvatarFallback>
                                </Avatar>
                                <Avatar size="lg">
                                    <AvatarFallback>LG</AvatarFallback>
                                </Avatar>
                                <Avatar size="xl">
                                    <AvatarFallback>XL</AvatarFallback>
                                </Avatar>
                            </Flex>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">With Badge</h3>
                            <Flex gap={4} align="center">
                                <Avatar>
                                    <AvatarImage src="https://github.com/shadcn.png" alt="@shadcn" />
                                    <AvatarFallback>CN</AvatarFallback>
                                    <AvatarBadge />
                                </Avatar>
                                <Avatar>
                                    <AvatarFallback>JD</AvatarFallback>
                                    <AvatarBadge status="success" />
                                </Avatar>
                                <Avatar>
                                    <AvatarFallback>AB</AvatarFallback>
                                    <AvatarBadge status="warning" />
                                </Avatar>
                                <Avatar>
                                    <AvatarFallback>XY</AvatarFallback>
                                    <AvatarBadge status="error" />
                                </Avatar>
                                <Avatar>
                                    <AvatarFallback>AC</AvatarFallback>
                                    <AvatarBadge status="accent" />
                                </Avatar>
                            </Flex>
                            <Caption style={{ marginTop: 'var(--space-2)' }}>Status indicators (last one: accent)</Caption>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Accent Border (Selected)</h3>
                            <Flex gap={4} align="center">
                                <Avatar>
                                    <AvatarFallback>DF</AvatarFallback>
                                </Avatar>
                                <Avatar accent>
                                    <AvatarFallback>AC</AvatarFallback>
                                </Avatar>
                                <Avatar accent>
                                    <AvatarImage src="https://github.com/shadcn.png" alt="@shadcn" />
                                    <AvatarFallback>CN</AvatarFallback>
                                </Avatar>
                            </Flex>
                            <Caption style={{ marginTop: 'var(--space-2)' }}>Default vs selected (accent border)</Caption>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Avatar Group</h3>
                            <Stack gap={4}>
                                <AvatarGroup>
                                    <Avatar>
                                        <AvatarImage src="https://github.com/shadcn.png" alt="User 1" />
                                        <AvatarFallback>U1</AvatarFallback>
                                    </Avatar>
                                    <Avatar>
                                        <AvatarFallback>U2</AvatarFallback>
                                    </Avatar>
                                    <Avatar>
                                        <AvatarFallback>U3</AvatarFallback>
                                    </Avatar>
                                    <AvatarGroupCount>+5</AvatarGroupCount>
                                </AvatarGroup>
                                <Caption>Stacked with overflow count</Caption>
                            </Stack>
                        </div>
                    </div>
                </section>

                {/* Image & AspectRatio Primitive */}
                <section className="showcase-section">
                    <h2 className="showcase-section-title">Image & AspectRatio</h2>
                    <p className="showcase-section-description">
                        Responsive images with aspect ratio containers for consistent layouts.
                    </p>

                    <div className="showcase-grid">
                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Basic Image</h3>
                            <Stack gap={4}>
                                <Image
                                    src="https://images.unsplash.com/photo-1588345921523-c2dcdb7f1dcd?w=400"
                                    alt="Demo image"
                                    style={{ width: 200 }}
                                />
                                <Caption>Default image with rounded corners</Caption>
                            </Stack>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Loading State</h3>
                            <Stack gap={4}>
                                <Box style={{ width: 200 }}>
                                    <Image
                                        src=""
                                        alt="Loading"
                                        isLoading
                                        style={{ width: '100%', height: 150 }}
                                    />
                                </Box>
                                <Caption>Skeleton while loading</Caption>
                            </Stack>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">AspectRatio</h3>
                            <Stack gap={4}>
                                <Flex gap={4}>
                                    <Box style={{ width: 120 }}>
                                        <AspectRatio ratio={1}>
                                            <img
                                                src="https://images.unsplash.com/photo-1588345921523-c2dcdb7f1dcd?w=200"
                                                alt="1:1"
                                                style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: 'var(--radius-md)' }}
                                            />
                                        </AspectRatio>
                                        <Caption>1:1</Caption>
                                    </Box>
                                    <Box style={{ width: 160 }}>
                                        <AspectRatio ratio={16 / 9}>
                                            <img
                                                src="https://images.unsplash.com/photo-1588345921523-c2dcdb7f1dcd?w=200"
                                                alt="16:9"
                                                style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: 'var(--radius-md)' }}
                                            />
                                        </AspectRatio>
                                        <Caption>16:9</Caption>
                                    </Box>
                                    <Box style={{ width: 100 }}>
                                        <AspectRatio ratio={3 / 4}>
                                            <img
                                                src="https://images.unsplash.com/photo-1588345921523-c2dcdb7f1dcd?w=200"
                                                alt="3:4"
                                                style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: 'var(--radius-md)' }}
                                            />
                                        </AspectRatio>
                                        <Caption>3:4</Caption>
                                    </Box>
                                </Flex>
                            </Stack>
                        </div>
                    </div>
                </section>

                {/* Kbd Primitive */}
                <section className="showcase-section">
                    <h2 className="showcase-section-title">Kbd (Keyboard)</h2>
                    <p className="showcase-section-description">
                        Display keyboard shortcuts and key combinations with proper styling.
                    </p>

                    <div className="showcase-grid">
                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Single Keys</h3>
                            <Flex gap={2} align="center">
                                <Kbd>⌘</Kbd>
                                <Kbd>⇧</Kbd>
                                <Kbd>⌥</Kbd>
                                <Kbd>⌃</Kbd>
                                <Kbd>↵</Kbd>
                                <Kbd>⌫</Kbd>
                                <Kbd>Esc</Kbd>
                                <Kbd>Tab</Kbd>
                            </Flex>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Key Combinations</h3>
                            <Stack gap={3}>
                                <Flex gap={2} align="center">
                                    <KbdGroup>
                                        <Kbd>⌘</Kbd>
                                        <Kbd>C</Kbd>
                                    </KbdGroup>
                                    <Text size="sm">Copy</Text>
                                </Flex>
                                <Flex gap={2} align="center">
                                    <KbdGroup>
                                        <Kbd>⌘</Kbd>
                                        <Kbd>⇧</Kbd>
                                        <Kbd>P</Kbd>
                                    </KbdGroup>
                                    <Text size="sm">Command Palette</Text>
                                </Flex>
                                <Flex gap={2} align="center">
                                    <KbdGroup>
                                        <Kbd>Ctrl</Kbd>
                                        <Kbd>Alt</Kbd>
                                        <Kbd>Del</Kbd>
                                    </KbdGroup>
                                    <Text size="sm">Task Manager</Text>
                                </Flex>
                            </Stack>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">In Context</h3>
                            <Stack gap={3}>
                                <Text size="sm">
                                    Press <Kbd>⌘</Kbd> + <Kbd>K</Kbd> to open search
                                </Text>
                                <Text size="sm">
                                    Use <Kbd>↑</Kbd> and <Kbd>↓</Kbd> to navigate
                                </Text>
                                <Text size="sm">
                                    Hit <Kbd>Esc</Kbd> to close
                                </Text>
                            </Stack>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Accent (Active Keys)</h3>
                            <Stack gap={3}>
                                <Flex gap={2} align="center">
                                    <Text size="sm">Currently pressed:</Text>
                                    <Kbd accent>⌘</Kbd>
                                </Flex>
                                <Flex gap={2} align="center">
                                    <KbdGroup>
                                        <Kbd accent>⌘</Kbd>
                                        <Kbd accent>K</Kbd>
                                    </KbdGroup>
                                    <Text size="sm">Active shortcut</Text>
                                </Flex>
                                <Caption>Accent highlights currently pressed keys</Caption>
                            </Stack>
                        </div>
                    </div>
                </section>

                {/* Progress Primitive */}
                <section className="showcase-section">
                    <h2 className="showcase-section-title">Progress</h2>
                    <p className="showcase-section-description">
                        Progress indicators for showing completion status.
                        Supports variants for different contexts.
                    </p>

                    <div className="showcase-grid">
                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Basic Progress</h3>
                            <Stack gap={4}>
                                <div>
                                    <Flex justify="between" style={{ marginBottom: 'var(--space-1)' }}>
                                        <Caption>Upload progress</Caption>
                                        <Caption>{progressValue}%</Caption>
                                    </Flex>
                                    <Progress value={progressValue} />
                                </div>
                                <Flex gap={2}>
                                    <Button size="sm" variant="outline" onClick={() => setProgressValue(Math.max(0, progressValue - 10))}>-10</Button>
                                    <Button size="sm" variant="outline" onClick={() => setProgressValue(Math.min(100, progressValue + 10))}>+10</Button>
                                </Flex>
                            </Stack>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Variants</h3>
                            <Stack gap={4}>
                                <div>
                                    <Caption>Default (neutral)</Caption>
                                    <Progress value={65} />
                                </div>
                                <div>
                                    <Caption>Accent</Caption>
                                    <Progress value={65} variant="accent" />
                                </div>
                                <div>
                                    <Caption>Success</Caption>
                                    <Progress value={100} variant="success" />
                                </div>
                                <div>
                                    <Caption>Warning</Caption>
                                    <Progress value={75} variant="warning" />
                                </div>
                                <div>
                                    <Caption>Error</Caption>
                                    <Progress value={30} variant="error" />
                                </div>
                            </Stack>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Sizes & States</h3>
                            <Stack gap={4}>
                                <div>
                                    <Caption>Small</Caption>
                                    <Progress value={60} size="sm" />
                                </div>
                                <div>
                                    <Caption>Default</Caption>
                                    <Progress value={60} />
                                </div>
                                <div>
                                    <Caption>Large</Caption>
                                    <Progress value={60} size="lg" />
                                </div>
                                <div>
                                    <Caption>Indeterminate</Caption>
                                    <Progress indeterminate />
                                </div>
                            </Stack>
                        </div>
                    </div>
                </section>

                {/* Separator Primitive */}
                <section className="showcase-section">
                    <h2 className="showcase-section-title">Separator</h2>
                    <p className="showcase-section-description">
                        Visual dividers for separating content sections.
                    </p>

                    <div className="showcase-grid">
                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Horizontal</h3>
                            <Stack gap={4}>
                                <Text size="sm">Content above</Text>
                                <Separator />
                                <Text size="sm">Content below</Text>
                            </Stack>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Vertical</h3>
                            <Flex gap={4} align="center" style={{ height: 40 }}>
                                <Text size="sm">Left</Text>
                                <Separator orientation="vertical" />
                                <Text size="sm">Center</Text>
                                <Separator orientation="vertical" />
                                <Text size="sm">Right</Text>
                            </Flex>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Variants</h3>
                            <Stack gap={4}>
                                <div>
                                    <Caption>Default</Caption>
                                    <Separator />
                                </div>
                                <div>
                                    <Caption>Subtle</Caption>
                                    <Separator variant="subtle" />
                                </div>
                                <div>
                                    <Caption>Strong</Caption>
                                    <Separator variant="strong" />
                                </div>
                            </Stack>
                        </div>
                    </div>
                </section>

                {/* Skeleton Primitive */}
                <section className="showcase-section">
                    <h2 className="showcase-section-title">Skeleton</h2>
                    <p className="showcase-section-description">
                        Loading placeholders that indicate content is being loaded.
                    </p>

                    <div className="showcase-grid">
                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Basic Shapes</h3>
                            <Stack gap={4}>
                                <div>
                                    <Caption>Default (rectangle)</Caption>
                                    <Skeleton style={{ width: '100%', height: 20 }} />
                                </div>
                                <div>
                                    <Caption>Circle</Caption>
                                    <Skeleton shape="circle" style={{ width: 48, height: 48 }} />
                                </div>
                            </Stack>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Preset Variants</h3>
                            <Stack gap={4}>
                                <div>
                                    <Caption>Text line</Caption>
                                    <Skeleton variant="text" />
                                </div>
                                <div>
                                    <Caption>Heading</Caption>
                                    <Skeleton variant="heading" />
                                </div>
                                <div>
                                    <Caption>Button</Caption>
                                    <Skeleton variant="button" />
                                </div>
                                <div>
                                    <Caption>Avatar</Caption>
                                    <Skeleton variant="avatar" />
                                </div>
                            </Stack>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Content Card Loading</h3>
                            <Box bordered style={{ padding: 'var(--space-4)' }}>
                                <Flex gap={3}>
                                    <Skeleton variant="avatar" />
                                    <Stack gap={2} style={{ flex: 1 }}>
                                        <Skeleton variant="text" style={{ width: '60%' }} />
                                        <Skeleton variant="text" style={{ width: '40%' }} />
                                    </Stack>
                                </Flex>
                                <Skeleton style={{ width: '100%', height: 120, marginTop: 'var(--space-3)' }} />
                                <Flex gap={2} style={{ marginTop: 'var(--space-3)' }}>
                                    <Skeleton variant="button" style={{ width: 80 }} />
                                    <Skeleton variant="button" style={{ width: 80 }} />
                                </Flex>
                            </Box>
                        </div>
                    </div>
                </section>

                {/* Card Primitive */}
                <section className="showcase-section">
                    <h2 className="showcase-section-title">Card</h2>
                    <p className="showcase-section-description">
                        Content container with physical surface appearance. Raised from background with subtle shadow depth.
                    </p>

                    <div className="showcase-grid">
                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Default Card</h3>
                            <Card>
                                <CardHeader>
                                    <CardTitle>Card Title</CardTitle>
                                    <CardDescription>Card description with additional context.</CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <Text>This is the main content area of the card. It can contain any content you need.</Text>
                                </CardContent>
                                <CardFooter>
                                    <Button variant="outline">Cancel</Button>
                                    <Button>Save</Button>
                                </CardFooter>
                            </Card>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">With Action</h3>
                            <Card>
                                <CardHeader>
                                    <CardTitle>Notifications</CardTitle>
                                    <CardDescription>Manage your notification preferences.</CardDescription>
                                    <CardAction>
                                        <Button size="sm" variant="outline">Settings</Button>
                                    </CardAction>
                                </CardHeader>
                                <CardContent>
                                    <Text>Configure how and when you receive notifications.</Text>
                                </CardContent>
                            </Card>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Interactive Card</h3>
                            <Stack gap={3}>
                                <Card interactive>
                                    <CardHeader>
                                        <CardTitle>Clickable Card</CardTitle>
                                        <CardDescription>Hover to see lift effect.</CardDescription>
                                    </CardHeader>
                                </Card>
                                <Card interactive>
                                    <CardHeader>
                                        <CardTitle>Another Item</CardTitle>
                                        <CardDescription>Interactive cards for navigation.</CardDescription>
                                    </CardHeader>
                                </Card>
                            </Stack>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Card Variants</h3>
                            <Stack gap={3}>
                                <Card variant="outline">
                                    <CardHeader>
                                        <CardTitle>Outline</CardTitle>
                                        <CardDescription>Border only, no shadow.</CardDescription>
                                    </CardHeader>
                                </Card>
                                <Card variant="inset">
                                    <CardHeader>
                                        <CardTitle>Inset</CardTitle>
                                        <CardDescription>Recessed surface.</CardDescription>
                                    </CardHeader>
                                </Card>
                            </Stack>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Card Sizes</h3>
                            <Stack gap={3}>
                                <Card size="sm">
                                    <CardHeader>
                                        <CardTitle>Small</CardTitle>
                                        <CardDescription>Compact padding.</CardDescription>
                                    </CardHeader>
                                </Card>
                                <Card size="lg">
                                    <CardHeader>
                                        <CardTitle>Large</CardTitle>
                                        <CardDescription>Spacious padding.</CardDescription>
                                    </CardHeader>
                                </Card>
                            </Stack>
                        </div>
                    </div>
                </section>

                {/* Dropdown Menu Primitive */}
                <section className="showcase-section">
                    <h2 className="showcase-section-title">Dropdown Menu</h2>
                    <p className="showcase-section-description">
                        Dropdown menu with physical surface appearance. Supports items, checkboxes, radios, and submenus.
                    </p>

                    <div className="showcase-grid">
                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Basic Menu</h3>
                            <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                    <Button variant="outline">Open Menu</Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent>
                                    <DropdownMenuLabel>My Account</DropdownMenuLabel>
                                    <DropdownMenuSeparator />
                                    <DropdownMenuItem>Profile</DropdownMenuItem>
                                    <DropdownMenuItem>Settings</DropdownMenuItem>
                                    <DropdownMenuItem>Billing</DropdownMenuItem>
                                    <DropdownMenuSeparator />
                                    <DropdownMenuItem variant="destructive">Log out</DropdownMenuItem>
                                </DropdownMenuContent>
                            </DropdownMenu>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">With Shortcuts</h3>
                            <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                    <Button variant="outline">Edit Menu</Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent>
                                    <DropdownMenuItem>
                                        Undo
                                        <DropdownMenuShortcut>⌘Z</DropdownMenuShortcut>
                                    </DropdownMenuItem>
                                    <DropdownMenuItem>
                                        Redo
                                        <DropdownMenuShortcut>⌘⇧Z</DropdownMenuShortcut>
                                    </DropdownMenuItem>
                                    <DropdownMenuSeparator />
                                    <DropdownMenuItem>
                                        Cut
                                        <DropdownMenuShortcut>⌘X</DropdownMenuShortcut>
                                    </DropdownMenuItem>
                                    <DropdownMenuItem>
                                        Copy
                                        <DropdownMenuShortcut>⌘C</DropdownMenuShortcut>
                                    </DropdownMenuItem>
                                    <DropdownMenuItem>
                                        Paste
                                        <DropdownMenuShortcut>⌘V</DropdownMenuShortcut>
                                    </DropdownMenuItem>
                                </DropdownMenuContent>
                            </DropdownMenu>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Checkbox Items</h3>
                            <DropdownMenuCheckboxDemo />
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Radio Items</h3>
                            <DropdownMenuRadioDemo />
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Submenu</h3>
                            <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                    <Button variant="outline">More Options</Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent>
                                    <DropdownMenuItem>New File</DropdownMenuItem>
                                    <DropdownMenuSub>
                                        <DropdownMenuSubTrigger>Share</DropdownMenuSubTrigger>
                                        <DropdownMenuSubContent>
                                            <DropdownMenuItem>Email</DropdownMenuItem>
                                            <DropdownMenuItem>Message</DropdownMenuItem>
                                            <DropdownMenuItem>Airdrop</DropdownMenuItem>
                                        </DropdownMenuSubContent>
                                    </DropdownMenuSub>
                                    <DropdownMenuSeparator />
                                    <DropdownMenuItem>Print</DropdownMenuItem>
                                </DropdownMenuContent>
                            </DropdownMenu>
                        </div>
                    </div>
                </section>

                {/* Tooltip Primitive */}
                <section className="showcase-section">
                    <h2 className="showcase-section-title">Tooltip</h2>
                    <p className="showcase-section-description">
                        A popup that displays information when hovering over or focusing an element.
                    </p>

                    <div className="showcase-grid">
                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Basic</h3>
                            <TooltipProvider>
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <Button variant="outline">Hover me</Button>
                                    </TooltipTrigger>
                                    <TooltipContent>
                                        <p>Add to library</p>
                                    </TooltipContent>
                                </Tooltip>
                            </TooltipProvider>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Sides</h3>
                            <TooltipProvider>
                                <Flex gap={2} wrap>
                                    <Tooltip>
                                        <TooltipTrigger asChild>
                                            <Button variant="outline" size="sm">Top</Button>
                                        </TooltipTrigger>
                                        <TooltipContent side="top">
                                            <p>Tooltip on top</p>
                                        </TooltipContent>
                                    </Tooltip>
                                    <Tooltip>
                                        <TooltipTrigger asChild>
                                            <Button variant="outline" size="sm">Right</Button>
                                        </TooltipTrigger>
                                        <TooltipContent side="right">
                                            <p>Tooltip on right</p>
                                        </TooltipContent>
                                    </Tooltip>
                                    <Tooltip>
                                        <TooltipTrigger asChild>
                                            <Button variant="outline" size="sm">Bottom</Button>
                                        </TooltipTrigger>
                                        <TooltipContent side="bottom">
                                            <p>Tooltip on bottom</p>
                                        </TooltipContent>
                                    </Tooltip>
                                    <Tooltip>
                                        <TooltipTrigger asChild>
                                            <Button variant="outline" size="sm">Left</Button>
                                        </TooltipTrigger>
                                        <TooltipContent side="left">
                                            <p>Tooltip on left</p>
                                        </TooltipContent>
                                    </Tooltip>
                                </Flex>
                            </TooltipProvider>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">With Keyboard Shortcut</h3>
                            <TooltipProvider>
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <Button variant="outline">
                                            Save
                                        </Button>
                                    </TooltipTrigger>
                                    <TooltipContent>
                                        <Flex align="center" gap={2}>
                                            <span>Save document</span>
                                            <Kbd>⌘S</Kbd>
                                        </Flex>
                                    </TooltipContent>
                                </Tooltip>
                            </TooltipProvider>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">On Disabled Button</h3>
                            <TooltipProvider>
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <span tabIndex={0}>
                                            <Button variant="outline" disabled style={{ pointerEvents: 'none' }}>
                                                Disabled
                                            </Button>
                                        </span>
                                    </TooltipTrigger>
                                    <TooltipContent>
                                        <p>You don't have permission</p>
                                    </TooltipContent>
                                </Tooltip>
                            </TooltipProvider>
                        </div>
                    </div>
                </section>

                {/* Tabs Primitive */}
                <section className="showcase-section">
                    <h2 className="showcase-section-title">Tabs</h2>
                    <p className="showcase-section-description">
                        A set of layered sections of content—known as tab panels—that are displayed one at a time.
                    </p>

                    <div className="showcase-grid">
                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Default</h3>
                            <Tabs defaultValue="account" style={{ width: '100%' }}>
                                <TabsList>
                                    <TabsTrigger value="account">Account</TabsTrigger>
                                    <TabsTrigger value="password">Password</TabsTrigger>
                                </TabsList>
                                <TabsContent value="account">
                                    <Card>
                                        <CardHeader>
                                            <CardTitle>Account</CardTitle>
                                            <CardDescription>
                                                Make changes to your account here.
                                            </CardDescription>
                                        </CardHeader>
                                        <CardContent>
                                            <Stack gap={4}>
                                                <FormField>
                                                    <Label htmlFor="name">Name</Label>
                                                    <Input id="name" defaultValue="Pedro Duarte" />
                                                </FormField>
                                                <FormField>
                                                    <Label htmlFor="username">Username</Label>
                                                    <Input id="username" defaultValue="@peduarte" />
                                                </FormField>
                                            </Stack>
                                        </CardContent>
                                        <CardFooter>
                                            <Button>Save changes</Button>
                                        </CardFooter>
                                    </Card>
                                </TabsContent>
                                <TabsContent value="password">
                                    <Card>
                                        <CardHeader>
                                            <CardTitle>Password</CardTitle>
                                            <CardDescription>
                                                Change your password here.
                                            </CardDescription>
                                        </CardHeader>
                                        <CardContent>
                                            <Stack gap={4}>
                                                <FormField>
                                                    <Label htmlFor="current">Current password</Label>
                                                    <Input id="current" type="password" />
                                                </FormField>
                                                <FormField>
                                                    <Label htmlFor="new">New password</Label>
                                                    <Input id="new" type="password" />
                                                </FormField>
                                            </Stack>
                                        </CardContent>
                                        <CardFooter>
                                            <Button>Save password</Button>
                                        </CardFooter>
                                    </Card>
                                </TabsContent>
                            </Tabs>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Line Variant</h3>
                            <Tabs defaultValue="overview" style={{ width: '100%' }}>
                                <TabsList variant="line">
                                    <TabsTrigger value="overview">Overview</TabsTrigger>
                                    <TabsTrigger value="analytics">Analytics</TabsTrigger>
                                    <TabsTrigger value="reports">Reports</TabsTrigger>
                                </TabsList>
                                <TabsContent value="overview" style={{ paddingTop: 'var(--space-4)' }}>
                                    <Text>Overview content goes here.</Text>
                                </TabsContent>
                                <TabsContent value="analytics" style={{ paddingTop: 'var(--space-4)' }}>
                                    <Text>Analytics content goes here.</Text>
                                </TabsContent>
                                <TabsContent value="reports" style={{ paddingTop: 'var(--space-4)' }}>
                                    <Text>Reports content goes here.</Text>
                                </TabsContent>
                            </Tabs>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Vertical</h3>
                            <Tabs defaultValue="general" orientation="vertical" style={{ width: '100%' }}>
                                <TabsList variant="line">
                                    <TabsTrigger value="general">General</TabsTrigger>
                                    <TabsTrigger value="security">Security</TabsTrigger>
                                    <TabsTrigger value="notifications">Notifications</TabsTrigger>
                                </TabsList>
                                <TabsContent value="general" style={{ paddingLeft: 'var(--space-4)' }}>
                                    <Text>General settings content.</Text>
                                </TabsContent>
                                <TabsContent value="security" style={{ paddingLeft: 'var(--space-4)' }}>
                                    <Text>Security settings content.</Text>
                                </TabsContent>
                                <TabsContent value="notifications" style={{ paddingLeft: 'var(--space-4)' }}>
                                    <Text>Notification preferences.</Text>
                                </TabsContent>
                            </Tabs>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Disabled Tab</h3>
                            <Tabs defaultValue="active" style={{ width: '100%' }}>
                                <TabsList>
                                    <TabsTrigger value="active">Active</TabsTrigger>
                                    <TabsTrigger value="disabled" disabled>Disabled</TabsTrigger>
                                    <TabsTrigger value="other">Other</TabsTrigger>
                                </TabsList>
                                <TabsContent value="active">
                                    <Text>This tab is active.</Text>
                                </TabsContent>
                                <TabsContent value="disabled">
                                    <Text>This content cannot be accessed.</Text>
                                </TabsContent>
                                <TabsContent value="other">
                                    <Text>Other content here.</Text>
                                </TabsContent>
                            </Tabs>
                        </div>
                    </div>
                </section>

                {/* Dialog Primitive */}
                <section className="showcase-section">
                    <h2 className="showcase-section-title">Dialog</h2>
                    <p className="showcase-section-description">
                        A window overlaid on the primary window, rendering the content underneath inert.
                    </p>

                    <div className="showcase-grid">
                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Basic</h3>
                            <Dialog>
                                <DialogTrigger asChild>
                                    <Button variant="outline">Edit Profile</Button>
                                </DialogTrigger>
                                <DialogContent>
                                    <DialogHeader>
                                        <DialogTitle>Edit profile</DialogTitle>
                                        <DialogDescription>
                                            Make changes to your profile here. Click save when you're done.
                                        </DialogDescription>
                                    </DialogHeader>
                                    <Stack gap={4} style={{ paddingBlock: 'var(--space-4)' }}>
                                        <FormField>
                                            <Label htmlFor="dialog-name">Name</Label>
                                            <Input id="dialog-name" defaultValue="Pedro Duarte" />
                                        </FormField>
                                        <FormField>
                                            <Label htmlFor="dialog-username">Username</Label>
                                            <Input id="dialog-username" defaultValue="@peduarte" />
                                        </FormField>
                                    </Stack>
                                    <DialogFooter>
                                        <DialogClose asChild>
                                            <Button variant="outline">Cancel</Button>
                                        </DialogClose>
                                        <Button>Save changes</Button>
                                    </DialogFooter>
                                </DialogContent>
                            </Dialog>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Sizes</h3>
                            <Flex gap={2} wrap>
                                <Dialog>
                                    <DialogTrigger asChild>
                                        <Button variant="outline" size="sm">Small</Button>
                                    </DialogTrigger>
                                    <DialogContent size="sm">
                                        <DialogHeader>
                                            <DialogTitle>Small Dialog</DialogTitle>
                                            <DialogDescription>This is a small dialog.</DialogDescription>
                                        </DialogHeader>
                                    </DialogContent>
                                </Dialog>
                                <Dialog>
                                    <DialogTrigger asChild>
                                        <Button variant="outline" size="sm">Large</Button>
                                    </DialogTrigger>
                                    <DialogContent size="lg">
                                        <DialogHeader>
                                            <DialogTitle>Large Dialog</DialogTitle>
                                            <DialogDescription>This is a large dialog with more room for content.</DialogDescription>
                                        </DialogHeader>
                                    </DialogContent>
                                </Dialog>
                            </Flex>
                        </div>
                    </div>
                </section>

                {/* Alert Dialog Primitive */}
                <section className="showcase-section">
                    <h2 className="showcase-section-title">Alert Dialog</h2>
                    <p className="showcase-section-description">
                        A modal dialog that interrupts the user and expects a response.
                    </p>

                    <div className="showcase-grid">
                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Confirmation</h3>
                            <AlertDialog>
                                <AlertDialogTrigger asChild>
                                    <Button variant="destructive">Delete Account</Button>
                                </AlertDialogTrigger>
                                <AlertDialogContent>
                                    <AlertDialogHeader>
                                        <AlertDialogTitle>Are you absolutely sure?</AlertDialogTitle>
                                        <AlertDialogDescription>
                                            This action cannot be undone. This will permanently delete your
                                            account and remove your data from our servers.
                                        </AlertDialogDescription>
                                    </AlertDialogHeader>
                                    <AlertDialogFooter>
                                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                                        <AlertDialogAction>Yes, delete account</AlertDialogAction>
                                    </AlertDialogFooter>
                                </AlertDialogContent>
                            </AlertDialog>
                        </div>
                    </div>
                </section>

                {/* Popover Primitive */}
                <section className="showcase-section">
                    <h2 className="showcase-section-title">Popover</h2>
                    <p className="showcase-section-description">
                        Displays rich content in a portal, triggered by a button.
                    </p>

                    <div className="showcase-grid">
                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Basic</h3>
                            <Popover>
                                <PopoverTrigger asChild>
                                    <Button variant="outline">Open Popover</Button>
                                </PopoverTrigger>
                                <PopoverContent>
                                    <Stack gap={4}>
                                        <div>
                                            <Text style={{ fontWeight: 500 }}>Dimensions</Text>
                                            <Text size="sm" color="muted">Set the dimensions for the layer.</Text>
                                        </div>
                                        <Stack gap={2}>
                                            <FormField>
                                                <Label htmlFor="width">Width</Label>
                                                <Input id="width" defaultValue="100%" />
                                            </FormField>
                                            <FormField>
                                                <Label htmlFor="height">Height</Label>
                                                <Input id="height" defaultValue="25px" />
                                            </FormField>
                                        </Stack>
                                    </Stack>
                                </PopoverContent>
                            </Popover>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Sides</h3>
                            <Flex gap={2} wrap>
                                <Popover>
                                    <PopoverTrigger asChild>
                                        <Button variant="outline" size="sm">Top</Button>
                                    </PopoverTrigger>
                                    <PopoverContent side="top">
                                        <Text size="sm">Popover on top</Text>
                                    </PopoverContent>
                                </Popover>
                                <Popover>
                                    <PopoverTrigger asChild>
                                        <Button variant="outline" size="sm">Right</Button>
                                    </PopoverTrigger>
                                    <PopoverContent side="right">
                                        <Text size="sm">Popover on right</Text>
                                    </PopoverContent>
                                </Popover>
                                <Popover>
                                    <PopoverTrigger asChild>
                                        <Button variant="outline" size="sm">Bottom</Button>
                                    </PopoverTrigger>
                                    <PopoverContent side="bottom">
                                        <Text size="sm">Popover on bottom</Text>
                                    </PopoverContent>
                                </Popover>
                                <Popover>
                                    <PopoverTrigger asChild>
                                        <Button variant="outline" size="sm">Left</Button>
                                    </PopoverTrigger>
                                    <PopoverContent side="left">
                                        <Text size="sm">Popover on left</Text>
                                    </PopoverContent>
                                </Popover>
                            </Flex>
                        </div>
                    </div>
                </section>

                {/* Sheet Primitive */}
                <section className="showcase-section">
                    <h2 className="showcase-section-title">Sheet</h2>
                    <p className="showcase-section-description">
                        A slide-out panel that extends from the edge of the screen.
                    </p>

                    <div className="showcase-grid">
                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Sides</h3>
                            <Flex gap={2} wrap>
                                <Sheet>
                                    <SheetTrigger asChild>
                                        <Button variant="outline">Right</Button>
                                    </SheetTrigger>
                                    <SheetContent side="right">
                                        <SheetHeader>
                                            <SheetTitle>Edit profile</SheetTitle>
                                            <SheetDescription>
                                                Make changes to your profile here.
                                            </SheetDescription>
                                        </SheetHeader>
                                        <Stack gap={4} style={{ paddingBlock: 'var(--space-4)' }}>
                                            <FormField>
                                                <Label htmlFor="sheet-name">Name</Label>
                                                <Input id="sheet-name" defaultValue="Pedro Duarte" />
                                            </FormField>
                                        </Stack>
                                        <SheetFooter>
                                            <SheetClose asChild>
                                                <Button variant="outline">Cancel</Button>
                                            </SheetClose>
                                            <Button>Save</Button>
                                        </SheetFooter>
                                    </SheetContent>
                                </Sheet>
                                <Sheet>
                                    <SheetTrigger asChild>
                                        <Button variant="outline">Left</Button>
                                    </SheetTrigger>
                                    <SheetContent side="left">
                                        <SheetHeader>
                                            <SheetTitle>Navigation</SheetTitle>
                                            <SheetDescription>Browse sections.</SheetDescription>
                                        </SheetHeader>
                                    </SheetContent>
                                </Sheet>
                                <Sheet>
                                    <SheetTrigger asChild>
                                        <Button variant="outline">Top</Button>
                                    </SheetTrigger>
                                    <SheetContent side="top">
                                        <SheetHeader>
                                            <SheetTitle>Notifications</SheetTitle>
                                            <SheetDescription>Your recent notifications.</SheetDescription>
                                        </SheetHeader>
                                    </SheetContent>
                                </Sheet>
                                <Sheet>
                                    <SheetTrigger asChild>
                                        <Button variant="outline">Bottom</Button>
                                    </SheetTrigger>
                                    <SheetContent side="bottom">
                                        <SheetHeader>
                                            <SheetTitle>Quick Actions</SheetTitle>
                                            <SheetDescription>Perform quick actions.</SheetDescription>
                                        </SheetHeader>
                                    </SheetContent>
                                </Sheet>
                            </Flex>
                        </div>
                    </div>
                </section>

                {/* Alert Primitive */}
                <section className="showcase-section">
                    <h2 className="showcase-section-title">Alert</h2>
                    <p className="showcase-section-description">
                        Displays a callout for user attention.
                    </p>

                    <div className="showcase-grid">
                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Default</h3>
                            <Alert>
                                <AlertTitle>Heads up!</AlertTitle>
                                <AlertDescription>
                                    You can add components to your app using the cli.
                                </AlertDescription>
                            </Alert>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Destructive</h3>
                            <Alert variant="destructive">
                                <AlertTitle>Error</AlertTitle>
                                <AlertDescription>
                                    Your session has expired. Please log in again.
                                </AlertDescription>
                            </Alert>
                        </div>
                    </div>
                </section>

                {/* Slider Primitive */}
                <section className="showcase-section">
                    <h2 className="showcase-section-title">Slider</h2>
                    <p className="showcase-section-description">
                        Range input for selecting numeric values. Supports single and range selection.
                    </p>

                    <div className="showcase-grid">
                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Single Value</h3>
                            <Stack gap={4}>
                                <div>
                                    <Flex justify="between" style={{ marginBottom: 'var(--space-2)' }}>
                                        <Caption>Volume</Caption>
                                        <Caption>{sliderValue[0]}%</Caption>
                                    </Flex>
                                    <Slider
                                        value={sliderValue}
                                        onValueChange={setSliderValue}
                                        max={100}
                                        step={1}
                                    />
                                </div>
                            </Stack>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Range Selection</h3>
                            <Stack gap={4}>
                                <div>
                                    <Flex justify="between" style={{ marginBottom: 'var(--space-2)' }}>
                                        <Caption>Price Range</Caption>
                                        <Caption>${rangeValue[0]} - ${rangeValue[1]}</Caption>
                                    </Flex>
                                    <Slider
                                        value={rangeValue}
                                        onValueChange={setRangeValue}
                                        max={100}
                                        step={5}
                                    />
                                </div>
                            </Stack>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Accent Variant</h3>
                            <Stack gap={4}>
                                <div>
                                    <Caption>Default</Caption>
                                    <Slider defaultValue={[50]} max={100} />
                                </div>
                                <div>
                                    <Caption>Accent</Caption>
                                    <Slider defaultValue={[50]} max={100} accent />
                                </div>
                                <div>
                                    <Caption>Disabled</Caption>
                                    <Slider defaultValue={[50]} max={100} disabled />
                                </div>
                            </Stack>
                        </div>
                    </div>
                </section>

                {/* Spinner Primitive */}
                <section className="showcase-section">
                    <h2 className="showcase-section-title">Spinner</h2>
                    <p className="showcase-section-description">
                        Loading indicator for asynchronous operations.
                    </p>

                    <div className="showcase-grid">
                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Sizes</h3>
                            <Flex gap={4} align="center">
                                <div style={{ textAlign: 'center' }}>
                                    <Spinner size="xs" />
                                    <Caption style={{ display: 'block', marginTop: 'var(--space-2)' }}>XS</Caption>
                                </div>
                                <div style={{ textAlign: 'center' }}>
                                    <Spinner size="sm" />
                                    <Caption style={{ display: 'block', marginTop: 'var(--space-2)' }}>SM</Caption>
                                </div>
                                <div style={{ textAlign: 'center' }}>
                                    <Spinner />
                                    <Caption style={{ display: 'block', marginTop: 'var(--space-2)' }}>Default</Caption>
                                </div>
                                <div style={{ textAlign: 'center' }}>
                                    <Spinner size="md" />
                                    <Caption style={{ display: 'block', marginTop: 'var(--space-2)' }}>MD</Caption>
                                </div>
                                <div style={{ textAlign: 'center' }}>
                                    <Spinner size="lg" />
                                    <Caption style={{ display: 'block', marginTop: 'var(--space-2)' }}>LG</Caption>
                                </div>
                                <div style={{ textAlign: 'center' }}>
                                    <Spinner size="xl" />
                                    <Caption style={{ display: 'block', marginTop: 'var(--space-2)' }}>XL</Caption>
                                </div>
                            </Flex>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Variants</h3>
                            <Flex gap={4} align="center">
                                <div style={{ textAlign: 'center' }}>
                                    <Spinner />
                                    <Caption style={{ display: 'block', marginTop: 'var(--space-2)' }}>Default</Caption>
                                </div>
                                <div style={{ textAlign: 'center' }}>
                                    <Spinner variant="accent" />
                                    <Caption style={{ display: 'block', marginTop: 'var(--space-2)' }}>Accent</Caption>
                                </div>
                                <div style={{ textAlign: 'center' }}>
                                    <Spinner variant="muted" />
                                    <Caption style={{ display: 'block', marginTop: 'var(--space-2)' }}>Muted</Caption>
                                </div>
                                <div style={{ textAlign: 'center', background: 'var(--surface-inverse)', padding: 'var(--space-3)', borderRadius: 'var(--radius-md)' }}>
                                    <Spinner variant="inverse" />
                                    <Caption style={{ display: 'block', marginTop: 'var(--space-2)', color: 'var(--text-inverse)' }}>Inverse</Caption>
                                </div>
                            </Flex>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Dot Variant</h3>
                            <Flex gap={4} align="center">
                                <div style={{ textAlign: 'center' }}>
                                    <Spinner dot size="xs" />
                                    <Caption style={{ display: 'block', marginTop: 'var(--space-2)' }}>XS</Caption>
                                </div>
                                <div style={{ textAlign: 'center' }}>
                                    <Spinner dot size="sm" />
                                    <Caption style={{ display: 'block', marginTop: 'var(--space-2)' }}>SM</Caption>
                                </div>
                                <div style={{ textAlign: 'center' }}>
                                    <Spinner dot />
                                    <Caption style={{ display: 'block', marginTop: 'var(--space-2)' }}>Default</Caption>
                                </div>
                                <div style={{ textAlign: 'center' }}>
                                    <Spinner dot size="lg" />
                                    <Caption style={{ display: 'block', marginTop: 'var(--space-2)' }}>LG</Caption>
                                </div>
                                <div style={{ textAlign: 'center' }}>
                                    <Spinner dot variant="accent" />
                                    <Caption style={{ display: 'block', marginTop: 'var(--space-2)' }}>Accent</Caption>
                                </div>
                                <div style={{ textAlign: 'center', background: 'var(--surface-inverse)', padding: 'var(--space-3)', borderRadius: 'var(--radius-md)' }}>
                                    <Spinner dot variant="inverse" />
                                    <Caption style={{ display: 'block', marginTop: 'var(--space-2)', color: 'var(--text-inverse)' }}>Inverse</Caption>
                                </div>
                            </Flex>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">In Context</h3>
                            <Stack gap={4}>
                                <Button disabled>
                                    <Spinner size="sm" style={{ marginRight: 'var(--space-2)' }} />
                                    Loading...
                                </Button>
                                <Box bordered style={{ padding: 'var(--space-8)', textAlign: 'center' }}>
                                    <Spinner />
                                    <Text size="sm" color="muted" style={{ marginTop: 'var(--space-3)' }}>
                                        Fetching data...
                                    </Text>
                                </Box>
                            </Stack>
                        </div>
                    </div>
                </section>

                {/* Toggle Primitive */}
                <section className="showcase-section">
                    <h2 className="showcase-section-title">Toggle</h2>
                    <p className="showcase-section-description">
                        A two-state button that can be either on or off.
                        Accent color appears when pressed.
                    </p>

                    <div className="showcase-grid">
                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Basic Toggle</h3>
                            <Stack gap={4}>
                                <Flex gap={4} align="center">
                                    <Toggle pressed={togglePressed} onPressedChange={setTogglePressed}>
                                        B
                                    </Toggle>
                                    <Caption>Pressed: {togglePressed ? 'Yes' : 'No'}</Caption>
                                </Flex>
                                <Flex gap={2}>
                                    <Toggle><span style={{ fontWeight: 'bold' }}>B</span></Toggle>
                                    <Toggle><span style={{ fontStyle: 'italic' }}>I</span></Toggle>
                                    <Toggle><span style={{ textDecoration: 'underline' }}>U</span></Toggle>
                                </Flex>
                                <Caption>Formatting toolbar</Caption>
                            </Stack>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Variants</h3>
                            <Stack gap={4}>
                                <Flex gap={4} align="center">
                                    <Toggle defaultPressed>Default</Toggle>
                                    <Toggle variant="outline" defaultPressed>Outline</Toggle>
                                </Flex>
                                <Flex gap={4} align="center">
                                    <Toggle defaultPressed accent>Accent</Toggle>
                                    <Toggle variant="outline" defaultPressed accent>Outline Accent</Toggle>
                                </Flex>
                            </Stack>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Sizes</h3>
                            <Flex gap={4} align="center">
                                <Toggle size="sm">SM</Toggle>
                                <Toggle>Default</Toggle>
                                <Toggle size="lg">Large</Toggle>
                            </Flex>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">States</h3>
                            <Stack gap={3}>
                                <Flex gap={4} align="center">
                                    <Toggle>Not Pressed</Toggle>
                                    <Caption>Rest state</Caption>
                                </Flex>
                                <Flex gap={4} align="center">
                                    <Toggle defaultPressed>Pressed</Toggle>
                                    <Caption>Active state</Caption>
                                </Flex>
                                <Flex gap={4} align="center">
                                    <Toggle disabled>Disabled</Toggle>
                                    <Caption>Disabled state</Caption>
                                </Flex>
                            </Stack>
                        </div>
                    </div>
                </section>

                {/* ScrollArea Primitive */}
                <section className="showcase-section">
                    <h2 className="showcase-section-title">ScrollArea</h2>
                    <p className="showcase-section-description">
                        Custom scrollbars with consistent cross-browser styling.
                    </p>

                    <div className="showcase-grid">
                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Vertical Scroll</h3>
                            <ScrollArea style={{ height: 200, width: '100%' }}>
                                <Stack gap={2} style={{ padding: 'var(--space-2)' }}>
                                    {Array.from({ length: 20 }).map((_, i) => (
                                        <Box key={i} surface style={{ padding: 'var(--space-2)' }}>
                                            <Text size="sm">Item {i + 1}</Text>
                                        </Box>
                                    ))}
                                </Stack>
                            </ScrollArea>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Horizontal Scroll</h3>
                            <ScrollArea style={{ width: '100%' }}>
                                <Flex gap={2} style={{ padding: 'var(--space-2)', width: 'max-content' }}>
                                    {Array.from({ length: 15 }).map((_, i) => (
                                        <Box key={i} surface style={{ padding: 'var(--space-4)', minWidth: 100, textAlign: 'center' }}>
                                            <Text size="sm">Card {i + 1}</Text>
                                        </Box>
                                    ))}
                                </Flex>
                                <ScrollBar orientation="horizontal" />
                            </ScrollArea>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Thin Scrollbar</h3>
                            <ScrollArea thin style={{ height: 150, width: '100%' }}>
                                <Stack gap={2} style={{ padding: 'var(--space-2)' }}>
                                    {Array.from({ length: 15 }).map((_, i) => (
                                        <Text key={i} size="sm">Line {i + 1}: Lorem ipsum dolor sit amet</Text>
                                    ))}
                                </Stack>
                            </ScrollArea>
                        </div>

                        <div className="showcase-card">
                            <h3 className="showcase-card-title">Accent Scrollbar</h3>
                            <ScrollArea accent style={{ height: 150, width: '100%' }}>
                                <Stack gap={2} style={{ padding: 'var(--space-2)' }}>
                                    {Array.from({ length: 15 }).map((_, i) => (
                                        <Box key={i} surface style={{ padding: 'var(--space-2)' }}>
                                            <Text size="sm">Item {i + 1}</Text>
                                        </Box>
                                    ))}
                                </Stack>
                            </ScrollArea>
                            <Caption style={{ marginTop: 'var(--space-2)' }}>Accent colored scrollbar for active/focused areas</Caption>
                        </div>
                    </div>
                </section>

                {/* Design Principles Recap */}
                <section className="showcase-section">
                    <h2 className="showcase-section-title">Design Principles</h2>

                    <div className="drams-prose" style={{ maxWidth: '100%' }}>
                        <div className="showcase-grid">
                            <div className="showcase-card">
                                <h4>✓ Physical, Not Flat</h4>
                                <p className="drams-text--sm drams-text--secondary">
                                    Controls are raised surfaces with shadows. Pressed states show compression.
                                    Light source is consistent (top-left).
                                </p>
                            </div>

                            <div className="showcase-card">
                                <h4>✓ Accent = Active/Selected</h4>
                                <p className="drams-text--sm drams-text--secondary">
                                    Braun Orange appears only when state changes to active.
                                    Never decorative. Never on rest states.
                                </p>
                            </div>

                            <div className="showcase-card">
                                <h4>✓ Status = Semantic Feedback</h4>
                                <p className="drams-text--sm drams-text--secondary">
                                    Green/red/blue only for success/error/info.
                                    Never for buttons. Never for interaction states.
                                </p>
                            </div>

                            <div className="showcase-card">
                                <h4>✓ Visible State Differences</h4>
                                <p className="drams-text--sm drams-text--secondary">
                                    Every state is visually distinct. If you can't tell states apart
                                    without labels, the design has failed.
                                </p>
                            </div>
                        </div>
                    </div>
                </section>

                {/* Footer */}
                <footer className="drams-footer" style={{ marginTop: 'var(--space-16)', textAlign: 'center' }}>
                    <p className="drams-caption">
                        DRAMS3 — Dieter Rams Design System v3<br />
                        "Less, but better"
                    </p>
                </footer>
            </div>
        </div>
    )
}

/**
 * DropdownMenuCheckboxDemo - Helper component for checkbox items demo
 */
function DropdownMenuCheckboxDemo() {
    const [showStatusBar, setShowStatusBar] = useState(true)
    const [showActivityBar, setShowActivityBar] = useState(false)
    const [showPanel, setShowPanel] = useState(false)

    return (
        <DropdownMenu>
            <DropdownMenuTrigger asChild>
                <Button variant="outline">View Options</Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent>
                <DropdownMenuLabel>Appearance</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuCheckboxItem
                    checked={showStatusBar}
                    onCheckedChange={setShowStatusBar}
                >
                    Status Bar
                </DropdownMenuCheckboxItem>
                <DropdownMenuCheckboxItem
                    checked={showActivityBar}
                    onCheckedChange={setShowActivityBar}
                >
                    Activity Bar
                </DropdownMenuCheckboxItem>
                <DropdownMenuCheckboxItem
                    checked={showPanel}
                    onCheckedChange={setShowPanel}
                >
                    Panel
                </DropdownMenuCheckboxItem>
            </DropdownMenuContent>
        </DropdownMenu>
    )
}

/**
 * DropdownMenuRadioDemo - Helper component for radio items demo
 */
function DropdownMenuRadioDemo() {
    const [position, setPosition] = useState('bottom')

    return (
        <DropdownMenu>
            <DropdownMenuTrigger asChild>
                <Button variant="outline">Panel Position</Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent>
                <DropdownMenuLabel>Position</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuRadioGroup value={position} onValueChange={setPosition}>
                    <DropdownMenuRadioItem value="top">Top</DropdownMenuRadioItem>
                    <DropdownMenuRadioItem value="bottom">Bottom</DropdownMenuRadioItem>
                    <DropdownMenuRadioItem value="right">Right</DropdownMenuRadioItem>
                </DropdownMenuRadioGroup>
            </DropdownMenuContent>
        </DropdownMenu>
    )
}
