import { motion } from 'framer-motion'
import { useSpotify } from '../context/SpotifyContext'
import { Disc3, Shield } from 'lucide-react'

export default function LoadingScreen() {
  const { loadingProgress, user } = useSpotify()

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden">
      {/* Background effects */}
      <div className="absolute inset-0 bg-void" />
      <div className="absolute top-1/3 left-1/3 w-96 h-96 rounded-full bg-neon-cyan/5 blur-3xl animate-pulse" />
      
      <motion.div 
        className="relative z-10 max-w-md w-full mx-4 text-center"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        {/* Spinning Logo */}
        <motion.div 
          className="w-20 h-20 mx-auto mb-8 rounded-2xl bg-gradient-to-br from-neon-cyan via-neon-blue to-neon-violet flex items-center justify-center shadow-glow-cyan"
          animate={{ rotate: 360 }}
          transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
        >
          <Disc3 className="w-10 h-10 text-void" />
        </motion.div>
        
        {/* User greeting */}
        {user && (
          <p className="text-text-secondary mb-4">
            Welcome, <span className="text-neon-cyan font-medium">{user.display_name}</span>
          </p>
        )}
        
        {/* Loading stage */}
        <h2 className="text-xl font-semibold text-text-primary mb-2">
          {loadingProgress.stage || 'Loading...'}
        </h2>
        
        {/* Progress bar */}
        <div className="h-2 bg-void-400 rounded-full overflow-hidden mb-4">
          <motion.div
            className="h-full bg-gradient-to-r from-neon-cyan to-neon-magenta rounded-full"
            initial={{ width: 0 }}
            animate={{ width: `${loadingProgress.progress}%` }}
            transition={{ duration: 0.3 }}
          />
        </div>
        
        <p className="text-sm text-text-muted">
          {loadingProgress.progress}% complete
        </p>
        
        {/* Privacy reminder */}
        <div className="mt-8 flex items-center justify-center gap-2 text-xs text-text-muted">
          <Shield className="w-4 h-4 text-neon-cyan" />
          <span>All processing happens in your browser. No data is stored.</span>
        </div>
      </motion.div>
    </div>
  )
}
