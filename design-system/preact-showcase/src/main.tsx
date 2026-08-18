import { render } from 'preact'
import App from './App'

// The design system, imported straight from the sibling directory.
// This is the identical file the React showcase and a plain HTML page use —
// no Preact-specific build, no fork, no wrapper package.
import '../../drams3/index.css'
import './styles.css'

render(<App />, document.getElementById('root')!)
