import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'

// Import the complete design system
import '../../index.css'

// Import showcase-specific styles
import './styles.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
        <App />
    </React.StrictMode>,
)
