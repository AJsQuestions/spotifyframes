import { useEffect } from 'react'
import { Routes, Route } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import { useSpotify } from './context/SpotifyContext'
import Sidebar from './components/Sidebar'
import LoginPage from './components/LoginPage'
import LoadingScreen from './components/LoadingScreen'
import PrivacyBanner from './components/PrivacyBanner'
import Dashboard from './pages/Dashboard'
import Explore from './pages/Explore'
import Playlists from './pages/Playlists'
import Clusters from './pages/Clusters'
import Gems from './pages/Gems'
import Settings from './pages/Settings'
import { Disc3 } from 'lucide-react'

function App() {
  const { 
    isAuthenticated, 
    isLoading, 
    isDataLoading, 
    libraryData,
    loadData 
  } = useSpotify()

  // Load data when authenticated
  useEffect(() => {
    if (isAuthenticated && !libraryData && !isDataLoading) {
      loadData()
    }
  }, [isAuthenticated, libraryData, isDataLoading, loadData])

  // Show loading spinner while checking auth
  if (isLoading) {
    return (
      <div className="min-h-screen bg-void flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-neon-cyan to-neon-violet flex items-center justify-center animate-pulse shadow-glow-cyan">
            <Disc3 className="w-8 h-8 text-void" />
          </div>
          <p className="text-text-muted">Loading...</p>
        </div>
      </div>
    )
  }

  // Show login page if not authenticated
  if (!isAuthenticated) {
    return <LoginPage />
  }

  // Show loading screen while fetching data
  if (isDataLoading || !libraryData) {
    return <LoadingScreen />
  }

  // Main app
  return (
    <div className="flex min-h-screen bg-void">
      <Sidebar />
      <main className="flex-1 ml-[260px] min-h-screen flex flex-col">
        <PrivacyBanner />
        <div className="flex-1">
          <AnimatePresence mode="wait">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/explore" element={<Explore />} />
              <Route path="/playlists" element={<Playlists />} />
              <Route path="/clusters" element={<Clusters />} />
              <Route path="/gems" element={<Gems />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </AnimatePresence>
        </div>
      </main>
    </div>
  )
}

export default App
