import * as React from 'react';
import {
    CircleCheckIcon,
    InfoIcon,
    Loader2Icon,
    OctagonXIcon,
    TriangleAlertIcon
} from 'lucide-react';
import { Toaster as Sonner, toast, type ToasterProps } from 'sonner';

function getResolvedMode(): 'light' | 'dark' {
    if (typeof window === 'undefined') {
        return 'light';
    }

    const root = document.documentElement;
    const explicitMode = root.getAttribute('data-mode');

    if (explicitMode === 'light' || explicitMode === 'dark') {
        return explicitMode;
    }

    if (root.classList.contains('dark')) {
        return 'dark';
    }

    if (root.classList.contains('light')) {
        return 'light';
    }

    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function useResolvedToasterTheme(): 'light' | 'dark' {
    const [theme, setTheme] = React.useState<'light' | 'dark'>(() => getResolvedMode());

    React.useEffect(() => {
        const updateTheme = () => setTheme(getResolvedMode());

        updateTheme();

        const root = document.documentElement;
        const observer = new MutationObserver(updateTheme);
        observer.observe(root, {
            attributes: true,
            attributeFilter: ['class', 'data-mode']
        });

        const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
        mediaQuery.addEventListener('change', updateTheme);

        return () => {
            observer.disconnect();
            mediaQuery.removeEventListener('change', updateTheme);
        };
    }, []);

    return theme;
}

const DEFAULT_CLASS_NAMES = {
    actionButton: 'drams-sonner-action',
    cancelButton: 'drams-sonner-cancel',
    closeButton: 'drams-sonner-close',
    description: 'drams-sonner-description',
    toast: 'drams-sonner-toast',
    title: 'drams-sonner-title'
} satisfies NonNullable<ToasterProps['toastOptions']>['classNames'];

export function Toaster({ theme = 'system', toastOptions, ...props }: ToasterProps) {
    const resolvedTheme = useResolvedToasterTheme();

    return (
        <Sonner
            theme={theme === 'system' ? resolvedTheme : theme}
            icons={{
                error: <OctagonXIcon className="size-4" />,
                info: <InfoIcon className="size-4" />,
                loading: <Loader2Icon className="size-4 animate-spin" />,
                success: <CircleCheckIcon className="size-4" />,
                warning: <TriangleAlertIcon className="size-4" />
            }}
            style={{
                '--border-radius': 'var(--radius-lg)',
                '--normal-bg': 'var(--surface-overlay)',
                '--normal-border': 'var(--border-default)',
                '--normal-text': 'var(--text-primary)'
            } as React.CSSProperties}
            toastOptions={{
                ...toastOptions,
                classNames: {
                    ...DEFAULT_CLASS_NAMES,
                    ...toastOptions?.classNames
                }
            }}
            {...props}
        />
    );
}

export { toast };
export type { ToasterProps };
