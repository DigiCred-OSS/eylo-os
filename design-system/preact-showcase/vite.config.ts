import preact from '@preact/preset-vite'
import { defineConfig } from 'vite'

// DRAMS is plain CSS, so there is nothing framework-specific to configure.
// The showcase imports drams3/index.css directly from the sibling directory —
// the same file the React and plain-HTML consumers use.
export default defineConfig({
    plugins: [preact()],
    server: { port: 5176 },
})
