import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Astryx ships pre-compiled CSS, so no StyleX build plugin is required here.
// A StyleX toolchain only becomes necessary if a component is `astryx swizzle`d
// into this repo, which this showcase deliberately avoids.
export default defineConfig({
    plugins: [react()],
    server: { port: 5174 },

    // Astryx takes react/react-dom as peer deps. Under pnpm's symlinked layout
    // Vite can pre-bundle a second React instance for the dependency and hand
    // the app a different one, which shows up as "Invalid hook call". Not
    // currently happening here — this is preventative, and cheap.
    resolve: {
        dedupe: ['react', 'react-dom'],
    },
    optimizeDeps: {
        include: ['react', 'react-dom', 'react/jsx-runtime'],
    },
})
