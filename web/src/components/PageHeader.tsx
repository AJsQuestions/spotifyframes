import { motion } from 'framer-motion'

interface PageHeaderProps {
  title: string
  subtitle: string
}

export default function PageHeader({ title, subtitle }: PageHeaderProps) {
  return (
    <motion.div 
      className="px-10 pt-8 pb-6 bg-gradient-to-b from-void-100 to-void border-b border-border-subtle sticky top-0 z-40 backdrop-blur-sm"
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <h1 className="text-[32px] font-bold tracking-tight mb-1.5 gradient-text">
        {title}
      </h1>
      <p className="text-sm text-text-secondary">
        {subtitle}
      </p>
    </motion.div>
  )
}

