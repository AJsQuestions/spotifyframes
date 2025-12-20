import { motion } from 'framer-motion'
import { useSpotify } from '../context/SpotifyContext'
import { Disc3, Shield, Lock, Eye, Github, ExternalLink } from 'lucide-react'

export default function LoginPage() {
  const { login, isLoading } = useSpotify()

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden">
      {/* Background effects */}
      <div className="absolute inset-0 bg-void" />
      <div className="absolute top-1/4 left-1/4 w-96 h-96 rounded-full bg-neon-cyan/5 blur-3xl" />
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 rounded-full bg-neon-magenta/5 blur-3xl" />
      
      <motion.div 
        className="relative z-10 max-w-lg w-full mx-4"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        {/* Logo Card */}
        <div className="bg-void-200 rounded-3xl border border-border-subtle p-10 text-center shadow-2xl">
          {/* Logo */}
          <motion.div 
            className="w-24 h-24 mx-auto mb-8 rounded-2xl bg-gradient-to-br from-neon-cyan via-neon-blue to-neon-violet flex items-center justify-center shadow-glow-cyan"
            animate={{ y: [0, -10, 0] }}
            transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
          >
            <Disc3 className="w-12 h-12 text-void" />
          </motion.div>
          
          {/* Title */}
          <h1 className="text-4xl font-bold mb-2 gradient-text">
            Spotim8
          </h1>
          <p className="text-text-secondary mb-8">
            Your Personal Spotify Analytics Dashboard
          </p>
          
          {/* Login Button */}
          <motion.button
            onClick={login}
            disabled={isLoading}
            className="w-full flex items-center justify-center gap-3 px-8 py-4 bg-gradient-to-r from-[#1DB954] to-[#1ed760] text-black font-bold rounded-xl transition-all hover:shadow-lg hover:shadow-[#1DB954]/30 disabled:opacity-50"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <svg className="w-6 h-6" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/>
            </svg>
            Continue with Spotify
          </motion.button>
          
          <p className="text-xs text-text-muted mt-4">
            Requires a Spotify account (Free or Premium)
          </p>
        </div>
        
        {/* Privacy Notice */}
        <motion.div 
          className="mt-6 p-6 bg-void-200/50 backdrop-blur-sm rounded-2xl border border-neon-cyan/20"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
        >
          <div className="flex items-center gap-2 text-neon-cyan font-semibold mb-4">
            <Shield className="w-5 h-5" />
            <span>Your Privacy is Protected</span>
          </div>
          
          <div className="space-y-3 text-sm text-text-secondary">
            <div className="flex items-start gap-3">
              <Lock className="w-4 h-4 mt-0.5 text-neon-cyan flex-shrink-0" />
              <p>
                <strong className="text-text-primary">No data storage.</strong> All processing happens 
                entirely in your browser. Nothing is ever sent to or stored on any server.
              </p>
            </div>
            
            <div className="flex items-start gap-3">
              <Eye className="w-4 h-4 mt-0.5 text-neon-cyan flex-shrink-0" />
              <p>
                <strong className="text-text-primary">Session only.</strong> Your data exists only 
                while this tab is open. Close it and everything is gone.
              </p>
            </div>
            
            <div className="flex items-start gap-3">
              <Github className="w-4 h-4 mt-0.5 text-neon-cyan flex-shrink-0" />
              <p>
                <strong className="text-text-primary">Open source.</strong> This is an academic 
                project. The code is fully transparent and auditable.
              </p>
            </div>
          </div>
        </motion.div>
        
        {/* Academic Notice */}
        <motion.div 
          className="mt-4 p-4 bg-void-300/30 rounded-xl border border-border-subtle text-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4 }}
        >
          <p className="text-xs text-text-muted">
            🎓 <strong>Academic Open Source Project</strong><br />
            Built for learning and personal use. No commercial purpose. No data collection.
          </p>
        </motion.div>
      </motion.div>
    </div>
  )
}
