/**
 * Full Astryx inventory — Action, Content, Feedback.
 *
 * Every component's props were read from its `.d.ts`, not guessed. Astryx makes
 * `label` required on most controls, so each demo supplies a real one.
 */
import { useState } from 'react'
import { Showcase, Demo, icons } from '../ui'

// Inline so the showcase never reaches the network. An empty `src` makes the
// browser re-request the page, which is what a bare placeholder would do.
const PLACEHOLDER_IMG =
    'data:image/svg+xml;utf8,' + encodeURIComponent(
        '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120">' +
        '<rect width="120" height="120" fill="%23E7E5E4"/></svg>')

import { ButtonGroup } from '@astryxdesign/core/ButtonGroup'
import { ToggleButton, ToggleButtonGroup } from '@astryxdesign/core/ToggleButton'
import { SegmentedControl, SegmentedControlItem } from '@astryxdesign/core/SegmentedControl'
import { MoreMenu } from '@astryxdesign/core/MoreMenu'
import { Toolbar } from '@astryxdesign/core/Toolbar'

import { Heading, Text } from '@astryxdesign/core/Text'
import { Blockquote } from '@astryxdesign/core/Blockquote'
import { Code } from '@astryxdesign/core/Code'
import { CodeBlock } from '@astryxdesign/core/CodeBlock'
import { Markdown } from '@astryxdesign/core/Markdown'
import { AvatarGroup } from '@astryxdesign/core/AvatarGroup'
import { Thumbnail } from '@astryxdesign/core/Thumbnail'
import { Timestamp } from '@astryxdesign/core/Timestamp'
import { Token } from '@astryxdesign/core/Token'
import { Kbd } from '@astryxdesign/core/Kbd'
import { StatusDot } from '@astryxdesign/core/StatusDot'
import { VisuallyHidden } from '@astryxdesign/core/VisuallyHidden'

import { Toast } from '@astryxdesign/core/Toast'
import { EmptyState } from '@astryxdesign/core/EmptyState'
import { AlertDialog } from '@astryxdesign/core/AlertDialog'
import { Skeleton } from '@astryxdesign/core/Skeleton'

import { Button, IconButton, Link, Badge, Avatar, Spinner } from '../components/accented'

export function ActionSection() {
    const [toggled, setToggled] = useState(false)
    const [group, setGroup] = useState<string | null>('bold')
    const [seg, setSeg] = useState('list')

    return (
        <Showcase id="action" title="Action"
            blurb="Controls that do something. Every one takes a required `label` — Astryx enforces accessible naming at the type level.">
            <Demo title="Button — variants">
                <Button label="Primary" variant="primary" />
                <Button label="Secondary" variant="secondary" />
                <Button label="Ghost" variant="ghost" />
                <Button label="Destructive" variant="destructive" />
            </Demo>
            <Demo title="Button — sizes">
                <Button label="Small" size="sm" />
                <Button label="Medium" size="md" />
                <Button label="Large" size="lg" />
            </Demo>
            <Demo title="Button — states">
                <Button label="Rest" />
                <Button label="Disabled" isDisabled />
                <Button label="Loading" isLoading />
            </Demo>
            <Demo title="Icon button">
                <IconButton icon={icons.plus} label="Add" />
                <IconButton icon={icons.search} label="Search" />
                <IconButton icon={icons.trash} label="Delete" />
            </Demo>
            <Demo title="Button group">
                <ButtonGroup label="Date range">
                    <Button label="Day" variant="secondary" />
                    <Button label="Week" variant="secondary" />
                    <Button label="Month" variant="secondary" />
                </ButtonGroup>
            </Demo>
            <Demo title="Toggle button">
                <ToggleButton label="Bold" isPressed={toggled} onPressedChange={v => setToggled(v)} />
            </Demo>
            <Demo title="Toggle button group">
                <ToggleButtonGroup label="Text style" value={group} onChange={setGroup}>
                    <ToggleButton label="Bold" value="bold" />
                    <ToggleButton label="Italic" value="italic" />
                </ToggleButtonGroup>
            </Demo>
            <Demo title="Segmented control">
                <SegmentedControl label="View" value={seg} onChange={setSeg}>
                    <SegmentedControlItem value="list" label="List" />
                    <SegmentedControlItem value="grid" label="Grid" />
                </SegmentedControl>
            </Demo>
            <Demo title="More menu">
                <MoreMenu items={[
                    { label: 'Edit' },
                    { label: 'Duplicate' },
                    { label: 'Delete' },
                ]} />
            </Demo>
            <Demo title="Toolbar">
                <Toolbar label="Formatting"
                    startContent={<IconButton icon={icons.plus} label="Add" />}
                    endContent={<IconButton icon={icons.search} label="Find" />} />
            </Demo>
            <Demo title="Link">
                <Link href="#action">A text link</Link>
            </Demo>
        </Showcase>
    )
}

export function ContentSection() {
    return (
        <Showcase id="content2" title="Content"
            blurb="Everything that presents information rather than accepting it.">
            <Demo title="Headings" column>
                <Heading level={1}>Heading 1</Heading>
                <Heading level={2}>Heading 2</Heading>
                <Heading level={3}>Heading 3</Heading>
            </Demo>
            <Demo title="Text" column>
                <Text>Primary body text</Text>
                <Text color="secondary">Secondary</Text>
                <Text color="disabled">Disabled</Text>
            </Demo>
            <Demo title="Blockquote" column>
                <Blockquote>Weniger, aber besser.</Blockquote>
            </Demo>
            <Demo title="Code">
                <Code>--color-accent</Code>
            </Demo>
            <Demo title="Code block" column>
                <CodeBlock code={'const theme = defineTheme({\n  name: "drams",\n})'} language="ts" />
            </Demo>
            <Demo title="Markdown" column>
                <Markdown>{'**Bold**, _italic_, and `code`.'}</Markdown>
            </Demo>
            <Demo title="Avatar">
                <Avatar name="Ada Lovelace" />
                <Avatar name="Grace Hopper" />
            </Demo>
            <Demo title="Avatar group">
                <AvatarGroup>
                    <Avatar name="Ada Lovelace" />
                    <Avatar name="Grace Hopper" />
                    <Avatar name="Alan Turing" />
                </AvatarGroup>
            </Demo>
            <Demo title="Thumbnail">
                <Thumbnail src={PLACEHOLDER_IMG} alt="A neutral placeholder" />
            </Demo>
            <Demo title="Timestamp">
                <Timestamp value="2026-07-27T10:00:00Z" />
            </Demo>
            <Demo title="Token">
                <Token label="filter: active" />
            </Demo>
            <Demo title="Kbd">
                <Kbd keys="cmd+k" />
            </Demo>
            <Demo title="Status dot">
                <StatusDot variant="success" label="Online" />
                <StatusDot variant="warning" label="Degraded" />
                <StatusDot variant="error" label="Offline" />
            </Demo>
            <Demo title="Badge">
                <Badge variant="neutral" label="Neutral" />
                <Badge variant="success" label="Success" />
                <Badge variant="warning" label="Warning" />
                <Badge variant="error" label="Error" />
            </Demo>
            <Demo title="Visually hidden"
                note="Renders nothing visible — present for screen readers only.">
                <VisuallyHidden>Hidden from sight, read aloud.</VisuallyHidden>
                <Text size="sm" color="secondary">(a hidden label sits here)</Text>
            </Demo>
        </Showcase>
    )
}

export function FeedbackSection() {
    const [alertOpen, setAlertOpen] = useState(false)
    return (
        <Showcase id="feedback2" title="Feedback"
            blurb="Status reports an outcome. These never carry brand — that would confuse an outcome with an interaction.">
            <Demo title="Spinner"><Spinner /></Demo>
            <Demo title="Skeleton" column>
                <Skeleton width={220} height={12} />
                <Skeleton width={160} height={12} />
            </Demo>
            <Demo title="Empty state" column>
                <EmptyState title="No integrations yet"
                    description="Connect your first integration to start syncing." />
            </Demo>
            <Demo title="Toast" column>
                <Toast type="info" body="Saved successfully" isAutoHide={false}
                    autoHideDuration={0} onDismiss={() => {}} />
            </Demo>
            <Demo title="Alert dialog" column>
                <Button label="Delete…" variant="destructive" onClick={() => setAlertOpen(true)} />
                <AlertDialog
                    isOpen={alertOpen}
                    onOpenChange={setAlertOpen}
                    title="Delete this project?"
                    description="This cannot be undone."
                    actionLabel="Delete"
                    onAction={() => setAlertOpen(false)}
                />
            </Demo>
        </Showcase>
    )
}
