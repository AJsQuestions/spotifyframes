import { NavLink } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useSpotify } from '../context/SpotifyContext'
import {
  LayoutDashboard,
  Compass,
  ListMusic,
  Network,
  Gem,
  Settings,
  Disc3,
  LogOut,
  Shield,
} from 'lucide-react'

const navItems = [
  { 
    section: 'EXPLORE',
    items: [
      { path: '/', label: 'Dashboard', icon: LayoutDashboard },
      { path: '/explore', label: 'Deep Dive', icon: Compass },
      { path: '/playlists', label: 'Playlists', icon: ListMusic },
      { path: '/clusters', label: 'Clusters', icon: Network },
    ]
  },
  {
    section: 'DISCOVER',
    items: [
      { path: '/gems', label: 'Hidden Gems', icon: Gem },
    ]
  },
  {
    section: 'SETTINGS',
    items: [
      { path: '/settings', label: 'Settings', icon: Settings },
    ]
  }
]

export default function Sidebar() {
  const { user, logout } = useSpotify()

  return (
    <aside className="w-[260px] h-screen bg-void-100 border-r border-border-subtle fixed left-0 top-0 flex flex-col z-50">
      {/* Gradient border effect */}
      <div className="absolute top-0 right-0 w-[1px] h-full bg-gradient-to-b from-transparent via-neon-cyan/30 to-transparent" />
      
      {/* Logo */}
      <div className="p-7 border-b border-border-subtle">
        <NavLink to="/" className="flex items-center gap-3.5 group">
          <motion.div 
            className="w-11 h-11 rounded-xl bg-gradient-to-br from-neon-cyan via-neon-blue to-neon-violet flex items-center justify-center shadow-glow-cyan"
            whileHover={{ scale: 1.05, rotate: -5 }}
            transition={{ type: "spring", stiffness: 400, damping: 10 }}
          >
            <Disc3 className="w-6 h-6 text-void" />
          </motion.div>
          <span className="text-[17px] font-semibold tracking-tight gradient-text">
            Spotim8
          </span>
        </NavLink>
      </div>

      {/* User Info */}
      {user && (
        <div className="px-4 py-4 border-b border-border-subtle">
          <div className="flex items-center gap-3 p-3 bg-void-300/50 rounded-xl">
            {user.images?.[0]?.url ? (
              <img 
                src={user.images[0].url} 
                alt={user.display_name}
                className="w-9 h-9 rounded-full"
              />
            ) : (
              <div className="w-9 h-9 rounded-full bg-gradient-to-br from-neon-cyan to-neon-violet flex items-center justify-center text-void font-bold text-sm">
                {user.display_name?.charAt(0).toUpperCase()}
              </div>
            )}
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-text-primary truncate">
                {user.display_name}
              </p>
              <p className="text-xs text-text-muted truncate">
                {user.product === 'premium' ? '✨ Premium' : 'Free'}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Navigation */}
      <nav className="flex-1 px-4 py-5 overflow-y-auto">
        {navItems.map((section) => (
          <div key={section.section} className="mb-7">
            <p className="text-[10px] font-bold uppercase tracking-[2px] text-text-muted px-3 mb-3">
              {section.section}
            </p>
            <div className="space-y-1">
              {section.items.map((item) => {
                const Icon = item.icon
                return (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    end={item.path === '/'}
                    className={({ isActive }) => `
                      relative flex items-center gap-3.5 px-3.5 py-3 rounded-lg
                      text-sm font-medium transition-all duration-200
                      ${isActive 
                        ? 'text-neon-cyan bg-neon-cyan/8 border border-neon-cyan/30 shadow-glow-cyan' 
                        : 'text-text-secondary hover:text-text-primary hover:bg-void-400 border border-transparent'
                      }
                    `}
                  >
                    {({ isActive }) => (
                      <>
                        {isActive && (
                          <motion.div
                            layoutId="activeIndicator"
                            className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-[60%] bg-gradient-to-b from-neon-cyan to-neon-blue rounded-r"
                            initial={false}
                            transition={{ type: "spring", stiffness: 500, damping: 30 }}
                          />
                        )}
                        <Icon className="w-[18px] h-[18px]" />
                        <span>{item.label}</span>
                      </>
                    )}
                  </NavLink>
                )
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-border-subtle space-y-3">
        {/* Privacy indicator */}
        <div className="flex items-center gap-2 px-3 py-2 bg-neon-cyan/5 rounded-lg border border-neon-cyan/20">
          <Shield className="w-4 h-4 text-neon-cyan" />
          <span className="text-[11px] text-neon-cyan">No data stored</span>
        </div>
        
        {/* Logout button */}
        <motion.button
          onClick={logout}
          className="w-full flex items-center gap-3 px-3.5 py-3 rounded-lg text-sm font-medium text-text-secondary hover:text-text-primary hover:bg-void-400 transition-colors"
          whileHover={{ x: 2 }}
        >
          <LogOut className="w-[18px] h-[18px]" />
          <span>Sign Out</span>
        </motion.button>
        
        <p className="text-[10px] text-text-muted text-center">
          Open Source • Academic Project
        </p>
      </div>
    </aside>
  )
}
