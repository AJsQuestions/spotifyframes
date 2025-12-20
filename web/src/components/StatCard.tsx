import { motion } from 'framer-motion'
import { ReactNode } from 'react'

interface StatCardProps {
  icon: ReactNode
  value: string | number
  label: string
  accent?: boolean
  delay?: number
}

export default function StatCard({ icon, value, label, accent = false, delay = 0 }: StatCardProps) {
  return (
    <motion.div 
      className={`
        relative bg-void-200 rounded-2xl border overflow-hidden p-6 card-hover
        ${accent 
          ? 'border-neon-cyan/50 bg-gradient-to-br from-neon-cyan/5 to-void-200' 
          : 'border-border-subtle'
        }
      `}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay }}
    >
      {/* Top gradient bar */}
      <div 
        className={`absolute top-0 left-0 right-0 h-[2px] bg-gradient-primary ${
          accent ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
        } transition-opacity`}
      />
      
      <div className="text-2xl mb-3 grayscale-[20%]">{icon}</div>
      <p className={`
        text-[36px] font-bold font-mono tracking-tight leading-none mb-1
        ${accent ? 'gradient-text' : 'text-text-primary'}
      `}>
        {value}
      </p>
      <p className="text-xs uppercase tracking-wider text-text-muted mt-1.5">
        {label}
      </p>
    </motion.div>
  )
}

