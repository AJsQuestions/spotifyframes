import { ReactNode } from 'react'
import { motion } from 'framer-motion'

interface CardProps {
  title: string
  icon?: ReactNode
  children: ReactNode
  hint?: string
  className?: string
  delay?: number
}

export default function Card({ title, icon, children, hint, className = '', delay = 0 }: CardProps) {
  return (
    <motion.div 
      className={`bg-void-200 rounded-2xl border border-border-subtle overflow-hidden card-hover ${className}`}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay }}
    >
      <div className="px-6 py-4 border-b border-border-subtle bg-white/[0.01]">
        <div className="flex items-center gap-2.5">
          {icon && <span className="text-lg">{icon}</span>}
          <h3 className="text-[15px] font-semibold text-text-primary">{title}</h3>
        </div>
      </div>
      <div className="p-6">
        {hint && (
          <p className="text-xs text-text-muted mb-4 px-3 py-2 bg-void-300 rounded-md border-l-2 border-neon-cyan">
            {hint}
          </p>
        )}
        {children}
      </div>
    </motion.div>
  )
}

