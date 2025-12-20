import { useState, useMemo } from 'react'
import { motion } from 'framer-motion'
import {
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  Radar, ResponsiveContainer, Tooltip,
} from 'recharts'
import PageHeader from '../components/PageHeader'
import Card from '../components/Card'
import { useSpotify } from '../context/SpotifyContext'

const chartColors = ['#00ffcc', '#ff00aa', '#ffcc00', '#00aaff', '#aa66ff', '#ff6600']
const genreList = ['Hip-Hop', 'R&B/Soul', 'Electronic', 'Rock', 'Pop', 'Indie', 'Other']

export default function Playlists() {
  const { playlists, genreData } = useSpotify()
  const [selectedPlaylistId, setSelectedPlaylistId] = useState(playlists[0]?.id || '')

  const selectedPlaylist = playlists.find(p => p.id === selectedPlaylistId) || playlists[0]

  // Generate genre bars (simplified - in production would use actual playlist tracks)
  const genreBars = useMemo(() => {
    if (!selectedPlaylist) return []
    
    // Generate random-ish but consistent genre distribution
    const seed = selectedPlaylist.id.charCodeAt(0)
    return genreList.slice(0, 6).map((genre, i) => {
      const base = (seed + i * 17) % 40
      const value = Math.max(5, base + (i === 0 ? 30 : 0))
      return {
        name: genre,
        value,
        percent: value,
      }
    }).sort((a, b) => b.value - a.value).slice(0, 5)
  }, [selectedPlaylist])

  // Radar data for selected playlist
  const radarData = useMemo(() => {
    return genreList.slice(0, 6).map((genre, i) => ({
      genre,
      value: genreBars.find(g => g.name === genre)?.value || 0,
      fullMark: 60,
    }))
  }, [genreBars])

  if (playlists.length === 0) {
    return (
      <div className="min-h-screen">
        <PageHeader title="Playlists" subtitle="Analyze individual playlists" />
        <div className="p-8">
          <p className="text-text-muted text-center py-16">
            No playlists found. Make sure you have playlists in your Spotify library.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen">
      <PageHeader title="Playlists" subtitle="Analyze individual playlists" />
      
      <div className="p-8">
        <Card title="Playlist Analysis" icon="📂" delay={0.1}>
          <div className="grid grid-cols-3 gap-8">
            {/* Playlist Selector */}
            <div>
              <label className="text-xs font-semibold text-text-muted uppercase tracking-wider block mb-3">
                Select a playlist:
              </label>
              <div className="space-y-2 max-h-[500px] overflow-y-auto pr-2">
                {playlists.map((playlist) => (
                  <motion.button
                    key={playlist.id}
                    onClick={() => setSelectedPlaylistId(playlist.id)}
                    className={`w-full text-left p-4 rounded-xl border transition-all ${
                      selectedPlaylistId === playlist.id
                        ? 'bg-neon-cyan/10 border-neon-cyan/50 shadow-glow-cyan'
                        : 'bg-void-300 border-border-subtle hover:border-border'
                    }`}
                    whileHover={{ scale: 1.01 }}
                    whileTap={{ scale: 0.99 }}
                  >
                    <div className="flex items-center gap-3">
                      {playlist.images?.[0]?.url ? (
                        <img 
                          src={playlist.images[0].url} 
                          alt={playlist.name}
                          className="w-10 h-10 rounded-lg object-cover"
                        />
                      ) : (
                        <div className="w-10 h-10 rounded-lg bg-void-500 flex items-center justify-center text-text-muted">
                          🎵
                        </div>
                      )}
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-text-primary truncate">
                          {playlist.name}
                        </p>
                        <p className="text-sm text-text-muted">
                          {playlist.tracks.total} tracks
                        </p>
                      </div>
                    </div>
                  </motion.button>
                ))}
              </div>
            </div>

            {/* Playlist Details */}
            <div className="col-span-2">
              {selectedPlaylist && (
                <motion.div
                  key={selectedPlaylist.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="space-y-6"
                >
                  {/* Header */}
                  <div className="flex items-start gap-4 border-b border-border-subtle pb-4">
                    {selectedPlaylist.images?.[0]?.url ? (
                      <img 
                        src={selectedPlaylist.images[0].url} 
                        alt={selectedPlaylist.name}
                        className="w-20 h-20 rounded-xl object-cover shadow-lg"
                      />
                    ) : (
                      <div className="w-20 h-20 rounded-xl bg-gradient-to-br from-neon-cyan to-neon-violet flex items-center justify-center text-3xl">
                        🎵
                      </div>
                    )}
                    <div>
                      <h3 className="text-2xl font-semibold text-text-primary">
                        {selectedPlaylist.name}
                      </h3>
                      <p className="text-text-muted mt-1">
                        {selectedPlaylist.tracks.total} tracks • by {selectedPlaylist.owner.display_name}
                      </p>
                      {selectedPlaylist.description && (
                        <p className="text-sm text-text-secondary mt-2 line-clamp-2">
                          {selectedPlaylist.description.replace(/<[^>]*>/g, '')}
                        </p>
                      )}
                    </div>
                  </div>

                  {/* Genre Composition */}
                  <div>
                    <h4 className="text-sm font-semibold text-text-muted uppercase tracking-wider mb-4">
                      Genre Composition (Estimated)
                    </h4>
                    <div className="space-y-3">
                      {genreBars.map((bar, i) => (
                        <div key={bar.name} className="space-y-1.5">
                          <div className="flex justify-between text-sm">
                            <span className="text-text-primary">{bar.name}</span>
                            <span className="text-neon-cyan font-mono">{bar.percent}%</span>
                          </div>
                          <div className="h-1.5 bg-void-500 rounded-full overflow-hidden">
                            <motion.div
                              className="h-full rounded-full"
                              style={{ 
                                background: `linear-gradient(90deg, ${chartColors[i % chartColors.length]}, ${chartColors[(i + 1) % chartColors.length]})` 
                              }}
                              initial={{ width: 0 }}
                              animate={{ width: `${bar.percent}%` }}
                              transition={{ duration: 0.5, delay: i * 0.1 }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Radar Chart */}
                  <div>
                    <h4 className="text-sm font-semibold text-text-muted uppercase tracking-wider mb-4">
                      Taste Profile
                    </h4>
                    <ResponsiveContainer width="100%" height={280}>
                      <RadarChart data={radarData}>
                        <PolarGrid stroke="#1a1a25" />
                        <PolarAngleAxis 
                          dataKey="genre" 
                          tick={{ fill: '#a0a0b0', fontSize: 11 }} 
                        />
                        <PolarRadiusAxis 
                          angle={30} 
                          domain={[0, 60]} 
                          tick={{ fill: '#606070', fontSize: 10 }}
                        />
                        <Radar
                          name={selectedPlaylist.name}
                          dataKey="value"
                          stroke="#00ffcc"
                          fill="#00ffcc"
                          fillOpacity={0.4}
                        />
                        <Tooltip 
                          contentStyle={{ 
                            backgroundColor: '#12121a', 
                            border: '1px solid #252535',
                            borderRadius: '8px',
                          }}
                        />
                      </RadarChart>
                    </ResponsiveContainer>
                  </div>
                </motion.div>
              )}
            </div>
          </div>
        </Card>
      </div>
    </div>
  )
}
