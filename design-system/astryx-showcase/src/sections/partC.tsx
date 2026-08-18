/**
 * Full Astryx inventory — Navigation, Overlay, Data.
 */
import { useState } from 'react'
import { Showcase, Demo, icons } from '../ui'

import { Tab } from '@astryxdesign/core/TabList'
import { BreadcrumbItem } from '@astryxdesign/core/Breadcrumbs'
import { SideNav, SideNavItem, SideNavSection } from '@astryxdesign/core/SideNav'
import { TopNav, TopNavItem } from '@astryxdesign/core/TopNav'
import { Pagination } from '@astryxdesign/core/Pagination'
import { Outline } from '@astryxdesign/core/Outline'
import { NavIcon } from '@astryxdesign/core/NavIcon'

import { Dialog, DialogHeader } from '@astryxdesign/core/Dialog'
import { Popover } from '@astryxdesign/core/Popover'
import { Tooltip } from '@astryxdesign/core/Tooltip'
import { HoverCard } from '@astryxdesign/core/HoverCard'
import { DropdownMenu } from '@astryxdesign/core/DropdownMenu'
import { ContextMenu } from '@astryxdesign/core/ContextMenu'

import {
    Table, TableHeader, TableHeaderCell, TableBody, TableRow, TableCell,
} from '@astryxdesign/core/Table'
import { List, ListItem } from '@astryxdesign/core/List'
import { MetadataList, MetadataListItem } from '@astryxdesign/core/MetadataList'
import { TreeList } from '@astryxdesign/core/TreeList'
import { OverflowList } from '@astryxdesign/core/OverflowList'
import { Item } from '@astryxdesign/core/Item'
import { Text } from '@astryxdesign/core/Text'
import { VStack } from '@astryxdesign/core/Layout'

import { Button, TabList, Breadcrumbs, Badge } from '../components/accented'

export function NavigationSection() {
    const [tab, setTab] = useState('a')
    const [page, setPage] = useState(1)

    return (
        <Showcase id="navigation2" title="Navigation"
            blurb="Getting between places. The selected item is an active control, so it is where accent belongs.">
            <Demo title="Tabs" column>
                <TabList value={tab} onChange={setTab}>
                    <Tab value="a" label="Overview" />
                    <Tab value="b" label="Activity" />
                    <Tab value="c" label="Settings" />
                </TabList>
            </Demo>
            <Demo title="Breadcrumbs" column>
                <Breadcrumbs>
                    <BreadcrumbItem href="#navigation2">Design system</BreadcrumbItem>
                    <BreadcrumbItem href="#navigation2">Astryx</BreadcrumbItem>
                    <BreadcrumbItem isCurrent>DRAMS</BreadcrumbItem>
                </Breadcrumbs>
            </Demo>
            <Demo title="Side nav" column>
                <SideNav>
                    <SideNavSection title="Workspace">
                        <SideNavItem label="Overview" />
                        <SideNavItem label="Projects" />
                        <SideNavItem label="Members" />
                    </SideNavSection>
                </SideNav>
            </Demo>
            <Demo title="Top nav" column>
                <TopNav>
                    <TopNavItem label="Product" />
                    <TopNavItem label="Docs" />
                    <TopNavItem label="Pricing" />
                </TopNav>
            </Demo>
            <Demo title="Nav icon">
                <NavIcon icon={icons.search} />
            </Demo>
            <Demo title="Pagination" column>
                <Pagination page={page} onChange={setPage} totalPages={5} />
            </Demo>
            <Demo title="Outline" column>
                <Outline items={[
                    { id: '1', label: 'Introduction', level: 1 },
                    { id: '2', label: 'Principles', level: 1 },
                    { id: '3', label: 'Tokens', level: 2 },
                ]} />
            </Demo>
        </Showcase>
    )
}

export function OverlaySection() {
    const [dialog, setDialog] = useState(false)

    return (
        <Showcase id="overlay" title="Overlay"
            blurb="Surfaces that float above the page. All share one elevation and backdrop language.">
            <Demo title="Dialog" column>
                <Button label="Open dialog" onClick={() => setDialog(true)} />
                <Dialog isOpen={dialog} onOpenChange={setDialog}>
                    <DialogHeader title="Dialog title" />
                    <Text size="sm" color="secondary">Modal content sits on the overlay surface.</Text>
                </Dialog>
            </Demo>
            <Demo title="Popover">
                <Popover content={<Text size="sm">Popover content</Text>}>
                    <Button label="Open popover" variant="secondary" />
                </Popover>
            </Demo>
            <Demo title="Tooltip">
                <Tooltip content="Brand only on interaction">
                    <Button label="Hover me" variant="secondary" />
                </Tooltip>
            </Demo>
            <Demo title="Hover card">
                <HoverCard content={<Text size="sm">Richer hover surface</Text>}>
                    <Button label="Hover me" variant="ghost" />
                </HoverCard>
            </Demo>
            <Demo title="Dropdown menu">
                <DropdownMenu
                    button={{ label: 'Actions' }}
                    items={[
                        { label: 'Edit' },
                        { label: 'Duplicate' },
                        { type: 'divider' },
                        { label: 'Delete' },
                    ]}
                />
            </Demo>
            <Demo title="Context menu" column>
                <ContextMenu items={[{ label: 'Cut' }, { label: 'Copy' }, { label: 'Paste' }]}>
                    <Text size="sm" color="secondary">Right-click this area</Text>
                </ContextMenu>
            </Demo>
        </Showcase>
    )
}

export function DataSection() {
    return (
        <Showcase id="data2" title="Data"
            blurb="Dense information stays calm: no zebra stripes, no decorative rules.">
            <Demo title="Table" column>
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHeaderCell>Token</TableHeaderCell>
                            <TableHeaderCell>Role</TableHeaderCell>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        <TableRow>
                            <TableCell>--color-accent</TableCell>
                            <TableCell>brand, opt-in</TableCell>
                        </TableRow>
                        <TableRow>
                            <TableCell>--color-warning</TableCell>
                            <TableCell>non-blocking caution</TableCell>
                        </TableRow>
                    </TableBody>
                </Table>
            </Demo>
            <Demo title="List" column>
                <List>
                    <ListItem label="Unobtrusive" />
                    <ListItem label="Honest" />
                    <ListItem label="Long-lasting" />
                </List>
            </Demo>
            <Demo title="Metadata list" column>
                <MetadataList>
                    <MetadataListItem label="Owner">Ada Lovelace</MetadataListItem>
                    <MetadataListItem label="Updated">Today</MetadataListItem>
                </MetadataList>
            </Demo>
            <Demo title="Item" column>
                <Item label="A single row item" />
            </Demo>
            <Demo title="Tree list" column>
                <TreeList items={[
                    { id: '1', label: 'src', children: [
                        { id: '2', label: 'components' },
                        { id: '3', label: 'theme' },
                    ] },
                ]} />
            </Demo>
            <Demo title="Overflow list" column>
                <OverflowList>
                    <Badge variant="neutral" label="One" />
                    <Badge variant="neutral" label="Two" />
                    <Badge variant="neutral" label="Three" />
                </OverflowList>
            </Demo>
            <Demo title="Empty" column>
                <VStack gap={2}>
                    <Text size="sm" color="secondary">See Feedback → Empty state.</Text>
                </VStack>
            </Demo>
        </Showcase>
    )
}
