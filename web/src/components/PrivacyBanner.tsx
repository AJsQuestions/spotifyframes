import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Shield, X } from 'lucide-react'

export default function PrivacyBanner() {
  const [isVisible, setIsVisible] = useState(true)

  if (!isVisible) return null

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -10 }}
        className="bg-neon-cyan/5 border-b border-neon-cyan/20 px-4 py-2"
      >
        <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-sm">
            <Shield className="w-4 h-4 text-neon-cyan flex-shrink-0" />
            <span className="text-text-secondary">
              <strong className="text-neon-cyan">Privacy First:</strong> All data is processed locally in your browser. 
              Nothing is stored or sent to any server. This is an open-source academic project.
            </span>
          </div>
          <button
            onClick={() => setIsVisible(false)}
            className="p-1 hover:bg-void-400 rounded transition-colors"
          >
            <X className="w-4 h-4 text-text-muted" />
          </button>
        </div>
      </motion.div>
    </AnimatePresence>
  )
}

