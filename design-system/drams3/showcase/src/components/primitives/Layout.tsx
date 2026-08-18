import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'

/* ═══════════════════════════════════════════════════════════════
   SHARED TYPES
   ═══════════════════════════════════════════════════════════════ */

type AsChildProp = {
    asChild?: boolean
}

/* ═══════════════════════════════════════════════════════════════
   PAGE
   The root container — sets background surface.
   Replaces <main>
   ═══════════════════════════════════════════════════════════════ */

export interface PageProps extends React.HTMLAttributes<HTMLElement>, AsChildProp { }

export const Page = React.forwardRef<HTMLElement, PageProps>(
    ({ asChild, className, ...props }, ref) => {
        const Comp = asChild ? Slot : 'main'
        return (
            <Comp
                ref={ref}
                className={`drams-page ${className || ''}`.trim()}
                {...props}
            />
        )
    }
)
Page.displayName = 'Page'

/* ═══════════════════════════════════════════════════════════════
   SECTION
   Semantic grouping of content.
   Replaces <section>
   ═══════════════════════════════════════════════════════════════ */

export interface SectionProps extends React.HTMLAttributes<HTMLElement>, AsChildProp {
    /** Constrain width and center content */
    contained?: boolean
}

export const Section = React.forwardRef<HTMLElement, SectionProps>(
    ({ asChild, contained, className, ...props }, ref) => {
        const Comp = asChild ? Slot : 'section'
        return (
            <Comp
                ref={ref}
                className={`drams-section ${contained ? 'drams-section--contained' : ''} ${className || ''}`.trim()}
                {...props}
            />
        )
    }
)
Section.displayName = 'Section'

/* ═══════════════════════════════════════════════════════════════
   ARTICLE
   Self-contained content block.
   Replaces <article>
   ═══════════════════════════════════════════════════════════════ */

export interface ArticleProps extends React.HTMLAttributes<HTMLElement>, AsChildProp { }

export const Article = React.forwardRef<HTMLElement, ArticleProps>(
    ({ asChild, className, ...props }, ref) => {
        const Comp = asChild ? Slot : 'article'
        return (
            <Comp
                ref={ref}
                className={`drams-article ${className || ''}`.trim()}
                {...props}
            />
        )
    }
)
Article.displayName = 'Article'

/* ═══════════════════════════════════════════════════════════════
   HEADER
   Page or section header.
   Replaces <header>
   ═══════════════════════════════════════════════════════════════ */

export interface HeaderProps extends React.HTMLAttributes<HTMLElement>, AsChildProp { }

export const Header = React.forwardRef<HTMLElement, HeaderProps>(
    ({ asChild, className, ...props }, ref) => {
        const Comp = asChild ? Slot : 'header'
        return (
            <Comp
                ref={ref}
                className={`drams-header ${className || ''}`.trim()}
                {...props}
            />
        )
    }
)
Header.displayName = 'Header'

/* ═══════════════════════════════════════════════════════════════
   FOOTER
   Page or section footer.
   Replaces <footer>
   ═══════════════════════════════════════════════════════════════ */

export interface FooterProps extends React.HTMLAttributes<HTMLElement>, AsChildProp { }

export const Footer = React.forwardRef<HTMLElement, FooterProps>(
    ({ asChild, className, ...props }, ref) => {
        const Comp = asChild ? Slot : 'footer'
        return (
            <Comp
                ref={ref}
                className={`drams-footer ${className || ''}`.trim()}
                {...props}
            />
        )
    }
)
Footer.displayName = 'Footer'

/* ═══════════════════════════════════════════════════════════════
   NAV
   Navigation container.
   Replaces <nav>
   ═══════════════════════════════════════════════════════════════ */

export interface NavProps extends React.HTMLAttributes<HTMLElement>, AsChildProp { }

export const Nav = React.forwardRef<HTMLElement, NavProps>(
    ({ asChild, className, ...props }, ref) => {
        const Comp = asChild ? Slot : 'nav'
        return (
            <Comp
                ref={ref}
                className={`drams-nav ${className || ''}`.trim()}
                {...props}
            />
        )
    }
)
Nav.displayName = 'Nav'

/* ═══════════════════════════════════════════════════════════════
   ASIDE
   Sidebar or tangential content.
   Replaces <aside>
   ═══════════════════════════════════════════════════════════════ */

export interface AsideProps extends React.HTMLAttributes<HTMLElement>, AsChildProp { }

export const Aside = React.forwardRef<HTMLElement, AsideProps>(
    ({ asChild, className, ...props }, ref) => {
        const Comp = asChild ? Slot : 'aside'
        return (
            <Comp
                ref={ref}
                className={`drams-aside ${className || ''}`.trim()}
                {...props}
            />
        )
    }
)
Aside.displayName = 'Aside'

/* ═══════════════════════════════════════════════════════════════
   BOX
   Generic container with optional surface elevation.
   Defaults to <div>
   ═══════════════════════════════════════════════════════════════ */

export interface BoxProps extends React.HTMLAttributes<HTMLDivElement>, AsChildProp {
    /** Add card-like surface with shadow */
    surface?: boolean
    /** Add border instead of shadow */
    bordered?: boolean
}

export const Box = React.forwardRef<HTMLDivElement, BoxProps>(
    ({ asChild, surface, bordered, className, ...props }, ref) => {
        const Comp = asChild ? Slot : 'div'
        const modifiers = [
            surface && 'drams-box--surface',
            bordered && 'drams-box--bordered',
        ].filter(Boolean).join(' ')

        return (
            <Comp
                ref={ref}
                className={`drams-box ${modifiers} ${className || ''}`.trim()}
                {...props}
            />
        )
    }
)
Box.displayName = 'Box'

/* ═══════════════════════════════════════════════════════════════
   FLEX
   Flexbox layout utility.
   ═══════════════════════════════════════════════════════════════ */

export interface FlexProps extends React.HTMLAttributes<HTMLDivElement>, AsChildProp {
    /** Display as inline-flex */
    inline?: boolean
    /** Flex direction */
    direction?: 'row' | 'column' | 'row-reverse' | 'column-reverse'
    /** Justify content (main axis) */
    justify?: 'start' | 'center' | 'end' | 'between' | 'around'
    /** Align items (cross axis) */
    align?: 'start' | 'center' | 'end' | 'stretch'
    /** Flex wrap */
    wrap?: boolean | 'nowrap'
    /** Gap between items */
    gap?: 1 | 2 | 3 | 4 | 6 | 8
}

export const Flex = React.forwardRef<HTMLDivElement, FlexProps>(
    ({ asChild, inline, direction, justify, align, wrap, gap, className, ...props }, ref) => {
        const Comp = asChild ? Slot : 'div'
        const modifiers = [
            inline && 'drams-flex--inline',
            direction === 'column' && 'drams-flex--col',
            direction === 'row-reverse' && 'drams-flex--row-reverse',
            direction === 'column-reverse' && 'drams-flex--col-reverse',
            justify && `drams-flex--${justify}`,
            align && `drams-flex--items-${align}`,
            wrap === true && 'drams-flex--wrap',
            wrap === 'nowrap' && 'drams-flex--nowrap',
            gap && `drams-flex--gap-${gap}`,
        ].filter(Boolean).join(' ')

        return (
            <Comp
                ref={ref}
                className={`drams-flex ${modifiers} ${className || ''}`.trim()}
                {...props}
            />
        )
    }
)
Flex.displayName = 'Flex'

/* ═══════════════════════════════════════════════════════════════
   GRID
   CSS Grid layout utility.
   ═══════════════════════════════════════════════════════════════ */

export interface GridProps extends React.HTMLAttributes<HTMLDivElement>, AsChildProp {
    /** Number of columns */
    cols?: 1 | 2 | 3 | 4 | 6 | 12
    /** Auto-fit columns (responsive) */
    autoFit?: boolean
    /** Auto-fill columns (responsive) */
    autoFill?: boolean
    /** Gap between items */
    gap?: 2 | 4 | 6 | 8
}

export const Grid = React.forwardRef<HTMLDivElement, GridProps>(
    ({ asChild, cols, autoFit, autoFill, gap, className, ...props }, ref) => {
        const Comp = asChild ? Slot : 'div'
        const modifiers = [
            cols && `drams-grid--cols-${cols}`,
            autoFit && 'drams-grid--auto-fit',
            autoFill && 'drams-grid--auto-fill',
            gap && `drams-grid--gap-${gap}`,
        ].filter(Boolean).join(' ')

        return (
            <Comp
                ref={ref}
                className={`drams-grid ${modifiers} ${className || ''}`.trim()}
                {...props}
            />
        )
    }
)
Grid.displayName = 'Grid'

/* ═══════════════════════════════════════════════════════════════
   STACK
   Vertical or horizontal spacing utility.
   ═══════════════════════════════════════════════════════════════ */

export interface StackProps extends React.HTMLAttributes<HTMLDivElement>, AsChildProp {
    /** Stack direction */
    direction?: 'vertical' | 'horizontal'
    /** Gap between items */
    gap?: 2 | 3 | 4 | 6 | 8
}

export const Stack = React.forwardRef<HTMLDivElement, StackProps>(
    ({ asChild, direction = 'vertical', gap = 4, className, ...props }, ref) => {
        const Comp = asChild ? Slot : 'div'
        const baseClass = direction === 'horizontal' ? 'drams-cluster' : 'drams-stack'

        return (
            <Comp
                ref={ref}
                className={`${baseClass} ${baseClass}--${gap} ${className || ''}`.trim()}
                {...props}
            />
        )
    }
)
Stack.displayName = 'Stack'
