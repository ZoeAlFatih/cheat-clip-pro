import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { LanguageProvider } from './locales'
import './index.css'
import App from './App.tsx'
import AccessKeyGate from './components/AccessKeyGate.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <LanguageProvider>
      <AccessKeyGate>
        <App />
      </AccessKeyGate>
    </LanguageProvider>
  </StrictMode>,
)
