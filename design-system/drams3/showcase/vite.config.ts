import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
    plugins: [react()],
    // Pinned so it never collides with the astryx showcase on 5174.
    server: { port: 5175 },
})
