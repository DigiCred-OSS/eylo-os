/**
 * Full Astryx inventory — Data Input, Container, Layout.
 */
import { useState } from 'react'
import { Showcase, Demo } from '../ui'

import { NumberInput } from '@astryxdesign/core/NumberInput'
import { FileInput } from '@astryxdesign/core/FileInput'
import { DateInput } from '@astryxdesign/core/DateInput'
import { TimeInput } from '@astryxdesign/core/TimeInput'
import { DateRangeInput } from '@astryxdesign/core/DateRangeInput'
import { Calendar } from '@astryxdesign/core/Calendar'
import { CheckboxList, CheckboxListItem } from '@astryxdesign/core/CheckboxList'
import { RadioListItem } from '@astryxdesign/core/RadioList'
import { Selector } from '@astryxdesign/core/Selector'
import { MultiSelector } from '@astryxdesign/core/MultiSelector'
import { Typeahead } from '@astryxdesign/core/Typeahead'
import { createStaticSource } from '@astryxdesign/core/Typeahead/utils'
import { InputGroup, InputGroupText } from '@astryxdesign/core/InputGroup'
import { Field } from '@astryxdesign/core/Field'
import { FieldStatus } from '@astryxdesign/core/FieldStatus'
import { FormLayout } from '@astryxdesign/core/FormLayout'

import { Card } from '@astryxdesign/core/Card'
import { ClickableCard } from '@astryxdesign/core/ClickableCard'
import { SelectableCard } from '@astryxdesign/core/SelectableCard'
import { Collapsible } from '@astryxdesign/core/Collapsible'
import { AspectRatio } from '@astryxdesign/core/AspectRatio'
import { Section } from '@astryxdesign/core/Section'

import { Divider } from '@astryxdesign/core/Divider'
import { Grid } from '@astryxdesign/core/Grid'
import { Center } from '@astryxdesign/core/Center'
import { HStack, VStack } from '@astryxdesign/core/Layout'
import { Text } from '@astryxdesign/core/Text'

import {
    TextInput, TextArea, CheckboxInput, Switch, Slider, RadioList, Badge,
} from '../components/accented'

const FRUIT = createStaticSource([
    { id: 'a', label: 'Ada Lovelace' },
    { id: 'b', label: 'Grace Hopper' },
    { id: 'c', label: 'Alan Turing' },
])

export function DataInputSection() {
    const [text, setText] = useState('')
    const [area, setArea] = useState('')
    const [num, setNum] = useState<number | null>(3)
    const [file, setFile] = useState<File | File[] | null>(null)
    const [checked, setChecked] = useState(true)
    const [on, setOn] = useState(true)
    const [radio, setRadio] = useState('a')
    const [slider, setSlider] = useState(40)
    const [sel, setSel] = useState('a')
    const [multi, setMulti] = useState<string[]>(['a'])
    const [person, setPerson] = useState<{ id: string; label: string } | null>(null)
    const [list, setList] = useState<string[]>(['a'])

    return (
        <Showcase id="datainput" title="Data input"
            blurb="Every input is controlled and every one requires a label. Inputs read as recessed — the inverse of a raised control.">
            <Demo title="Text input" column>
                <TextInput label="Project" value={text} onChange={setText} placeholder="Type here" />
                <TextInput label="Disabled" value="" isDisabled />
            </Demo>
            <Demo title="Text area" column>
                <TextArea label="Notes" value={area} onChange={setArea} />
            </Demo>
            <Demo title="Number input" column>
                <NumberInput label="Quantity" value={num} onChange={setNum} />
            </Demo>
            <Demo title="File input" column>
                <FileInput label="Attachment" value={file} onChange={setFile} />
            </Demo>
            <Demo title="Date input" column>
                <DateInput label="Start date" />
            </Demo>
            <Demo title="Time input" column>
                <TimeInput label="Start time" />
            </Demo>
            <Demo title="Date range" column>
                <DateRangeInput label="Period" value={null} onChange={() => {}} />
            </Demo>
            <Demo title="Calendar" column>
                <Calendar />
            </Demo>
            <Demo title="Checkbox" column>
                <CheckboxInput label="Checked" value={checked} onChange={setChecked} />
                <CheckboxInput label="Indeterminate" value="indeterminate" onChange={() => {}} />
            </Demo>
            <Demo title="Checkbox list" column>
                <CheckboxList label="Features" value={list} onChange={setList}>
                    <CheckboxListItem value="a" label="Analytics" />
                    <CheckboxListItem value="b" label="Billing" />
                </CheckboxList>
            </Demo>
            <Demo title="Radio list" column>
                <RadioList label="Plan" value={radio} onChange={setRadio}>
                    <RadioListItem value="a" label="Starter" />
                    <RadioListItem value="b" label="Pro" />
                </RadioList>
            </Demo>
            <Demo title="Switch" column>
                <Switch label="Notifications" value={on} onChange={setOn} />
            </Demo>
            <Demo title="Slider" column>
                <Slider label="Contrast" value={slider} min={0} max={100}
                    onChange={(v: number) => setSlider(v)} />
            </Demo>
            <Demo title="Selector" column>
                <Selector label="Owner" value={sel} onChange={setSel}
                    options={[{ value: 'a', label: 'Ada' }, { value: 'b', label: 'Grace' }]} />
            </Demo>
            <Demo title="Multi selector" column>
                <MultiSelector label="Tags" value={multi} onChange={setMulti}
                    options={[{ value: 'a', label: 'Design' }, { value: 'b', label: 'Code' }]} />
            </Demo>
            <Demo title="Typeahead" column>
                <Typeahead label="Assignee" searchSource={FRUIT} value={person} onChange={setPerson} />
            </Demo>
            <Demo title="Input group" column>
                <InputGroup label="Amount">
                    <InputGroupText>$</InputGroupText>
                    <TextInput label="Amount" isLabelHidden value={text} onChange={setText} />
                </InputGroup>
            </Demo>
            <Demo title="Field + status" column>
                <Field label="Email" inputID="email-demo" description="We never share it.">
                    <TextInput label="Email" isLabelHidden value="" />
                </Field>
                <FieldStatus type="error" message="That email is invalid" />
            </Demo>
            <Demo title="Form layout" column>
                <FormLayout>
                    <TextInput label="First name" value="" />
                    <TextInput label="Last name" value="" />
                </FormLayout>
            </Demo>
        </Showcase>
    )
}

export function ContainerSection() {
    const [picked, setPicked] = useState(false)
    return (
        <Showcase id="container" title="Container"
            blurb="Surfaces that hold other things. Surfaces stack: body → surface → card → popover.">
            <Demo title="Card" column>
                <Card>
                    <VStack gap={2}>
                        <Text>Card</Text>
                        <Text size="sm" color="secondary">Sits on a raised surface.</Text>
                    </VStack>
                </Card>
            </Demo>
            <Demo title="Clickable card" column>
                <ClickableCard label="Open project" onClick={() => {}}>
                    <Text size="sm">A whole card as one control.</Text>
                </ClickableCard>
            </Demo>
            <Demo title="Selectable card" column>
                <SelectableCard label="Starter plan" isSelected={picked} onChange={setPicked}>
                    <Text size="sm">Selectable, like a large radio.</Text>
                </SelectableCard>
            </Demo>
            <Demo title="Collapsible" column>
                <Collapsible trigger="Show details">
                    <Text size="sm" color="secondary">Disclosed content.</Text>
                </Collapsible>
            </Demo>
            <Demo title="Aspect ratio" column>
                <AspectRatio ratio={16 / 9}>
                    <Center><Text size="sm" color="secondary">16 : 9</Text></Center>
                </AspectRatio>
            </Demo>
            <Demo title="Section" column>
                <Section>
                    <Text size="sm">A semantic content grouping.</Text>
                </Section>
            </Demo>
        </Showcase>
    )
}

export function LayoutSection() {
    return (
        <Showcase id="layout2" title="Layout"
            blurb="Whitespace is structure. Everything sits on one spacing scale.">
            <Demo title="HStack">
                <HStack gap={3}>
                    <Badge variant="neutral" label="One" />
                    <Badge variant="neutral" label="Two" />
                    <Badge variant="neutral" label="Three" />
                </HStack>
            </Demo>
            <Demo title="VStack" column>
                <VStack gap={2}>
                    <Text size="sm">Vertical A</Text>
                    <Text size="sm">Vertical B</Text>
                </VStack>
            </Demo>
            <Demo title="Grid" column>
                <Grid columns={3} gap={2}>
                    <Badge variant="neutral" label="1" />
                    <Badge variant="neutral" label="2" />
                    <Badge variant="neutral" label="3" />
                </Grid>
            </Demo>
            <Demo title="Center" column>
                <Center><Text size="sm">Centred</Text></Center>
            </Demo>
            <Demo title="Divider" column>
                <Text size="sm">Above</Text>
                <Divider />
                <Text size="sm">Below</Text>
            </Demo>
        </Showcase>
    )
}
