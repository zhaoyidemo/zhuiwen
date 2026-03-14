import { useState } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import PasswordGuard from './components/PasswordGuard'
import VideoAnalyzer from './pages/VideoAnalyzer'
import CompetitorRadar from './pages/CompetitorRadar'
import Dashboard from './pages/Dashboard'
import AIAnalysis from './pages/AIAnalysis'

export default function App() {
  const [authed, setAuthed] = useState(() => !!localStorage.getItem('site_password'))

  if (!authed) {
    return <PasswordGuard onAuth={() => setAuthed(true)} />
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<VideoAnalyzer />} />
          <Route path="/competitor" element={<CompetitorRadar />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/analysis" element={<AIAnalysis />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
