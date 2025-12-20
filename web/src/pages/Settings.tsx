import { motion } from 'framer-motion'
import PageHeader from '../components/PageHeader'
import Card from '../components/Card'
import { useSpotify } from '../context/SpotifyContext'
import { 
  CheckCircle, Shield, Lock, Eye, Github, ExternalLink, 
  RefreshCw, LogOut, Database, Trash2 
} from 'lucide-react'

export default function Settings() {
  const { libraryData, user, logout, loadData, isDataLoading } = useSpotify()

  return (
    <div className="min-h-screen">
      <PageHeader title="Settings" subtitle="Configure the dashboard" />
      
      <div className="p-8 space-y-6">
        {/* Privacy & Data */}
        <Card title="Privacy & Data" icon="🔒" delay={0.1}>
          <div className="space-y-6">
            {/* Privacy Status */}
            <div className="p-5 bg-neon-cyan/5 rounded-xl border border-neon-cyan/20">
              <div className="flex items-center gap-2 text-neon-cyan font-semibold mb-4">
                <Shield className="w-5 h-5" />
                <span>Your Privacy is Protected</span>
              </div>
              
              <div className="space-y-4 text-sm">
                <div className="flex items-start gap-3">
                  <Lock className="w-4 h-4 mt-0.5 text-neon-cyan flex-shrink-0" />
                  <div>
                    <p className="text-text-primary font-medium">No server-side storage</p>
                    <p className="text-text-muted">
                      All data is processed entirely in your browser. Nothing is ever sent to or stored on any server.
                    </p>
                  </div>
                </div>
                
                <div className="flex items-start gap-3">
                  <Eye className="w-4 h-4 mt-0.5 text-neon-cyan flex-shrink-0" />
                  <div>
                    <p className="text-text-primary font-medium">Session-only data</p>
                    <p className="text-text-muted">
                      Your data exists only while this browser tab is open. Close it and everything is immediately cleared.
                    </p>
                  </div>
                </div>
                
                <div className="flex items-start gap-3">
                  <Database className="w-4 h-4 mt-0.5 text-neon-cyan flex-shrink-0" />
                  <div>
                    <p className="text-text-primary font-medium">No cookies or tracking</p>
                    <p className="text-text-muted">
                      We don't use cookies, analytics, or any form of tracking. Your usage is completely private.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="flex gap-4">
              <motion.button
                onClick={() => loadData()}
                disabled={isDataLoading}
                className="flex items-center gap-2 px-5 py-3 bg-void-300 border border-border rounded-xl text-text-primary hover:border-neon-cyan transition-colors disabled:opacity-50"
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
              >
                <RefreshCw className={`w-4 h-4 ${isDataLoading ? 'animate-spin' : ''}`} />
                Reload Data
              </motion.button>
              
              <motion.button
                onClick={logout}
                className="flex items-center gap-2 px-5 py-3 bg-void-300 border border-border rounded-xl text-red-400 hover:border-red-400/50 transition-colors"
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
              >
                <LogOut className="w-4 h-4" />
                Sign Out & Clear Data
              </motion.button>
            </div>
          </div>
        </Card>

        {/* Account Info */}
        {user && (
          <Card title="Connected Account" icon="👤" delay={0.2}>
            <div className="flex items-center gap-4 p-4 bg-void-300/50 rounded-xl">
              {user.images?.[0]?.url ? (
                <img 
                  src={user.images[0].url} 
                  alt={user.display_name}
                  className="w-14 h-14 rounded-full"
                />
              ) : (
                <div className="w-14 h-14 rounded-full bg-gradient-to-br from-neon-cyan to-neon-violet flex items-center justify-center text-void font-bold text-xl">
                  {user.display_name?.charAt(0).toUpperCase()}
                </div>
              )}
              <div>
                <p className="text-lg font-semibold text-text-primary">{user.display_name}</p>
                <p className="text-sm text-text-muted">{user.email}</p>
                <p className="text-xs text-neon-cyan mt-1">
                  {user.product === 'premium' ? '✨ Spotify Premium' : 'Spotify Free'}
                </p>
              </div>
            </div>
          </Card>
        )}

        {/* Library Statistics */}
        {libraryData && (
          <Card title="Library Statistics" icon="📊" delay={0.3}>
            <div className="divide-y divide-border-subtle">
              {[
                { label: 'Total Tracks Analyzed', value: libraryData.totalTracks.toLocaleString() },
                { label: 'Unique Artists', value: libraryData.totalArtists.toLocaleString() },
                { label: 'Playlists Loaded', value: libraryData.totalPlaylists },
                { label: 'Total Duration', value: `${libraryData.totalHours} hours` },
                { label: 'Average Popularity', value: libraryData.avgPopularity },
              ].map((stat, i) => (
                <motion.div 
                  key={stat.label}
                  className="flex justify-between items-center py-4"
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.05 }}
                >
                  <span className="text-text-secondary">{stat.label}</span>
                  <span className="text-text-primary font-mono font-medium">{stat.value}</span>
                </motion.div>
              ))}
            </div>
          </Card>
        )}

        {/* About */}
        <Card title="About Spotim8" icon="ℹ️" delay={0.4}>
          <div className="space-y-4">
            <p className="text-text-secondary text-sm leading-relaxed">
              Spotim8 is an <strong className="text-neon-cyan">open-source academic project</strong> that 
              visualizes your Spotify library with interactive charts and insights. It's built purely for 
              educational purposes and personal use.
            </p>
            
            <div className="p-4 bg-void-300/50 rounded-xl border border-border-subtle">
              <p className="text-xs text-text-muted mb-2">Key principles:</p>
              <ul className="text-sm text-text-secondary space-y-1">
                <li>✓ No data collection or storage</li>
                <li>✓ No commercial purpose</li>
                <li>✓ Fully transparent, auditable code</li>
                <li>✓ Client-side only processing</li>
              </ul>
            </div>

            <p className="text-xs text-text-muted mt-4">
              Built with React, TypeScript, Tailwind CSS, Recharts, and Framer Motion.
            </p>
          </div>
        </Card>
      </div>
    </div>
  )
}
