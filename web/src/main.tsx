import React from 'react'
import ReactDOM from 'react-dom/client'
import { HashRouter } from 'react-router-dom'
import { SpotifyProvider } from './context/SpotifyContext'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <HashRouter>
      <SpotifyProvider>
        <App />
      </SpotifyProvider>
    </HashRouter>
  </React.StrictMode>,
)
