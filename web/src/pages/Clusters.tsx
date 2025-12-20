import { useMemo } from 'react'
import { motion } from 'framer-motion'
import {
  ScatterChart, Scatter, XAxis, YAxis, ZAxis, Tooltip,
  ResponsiveContainer, Cell,
} from 'recharts'
import PageHeader from '../components/PageHeader'
import Card from '../components/Card'
import { useSpotify } from '../context/SpotifyContext'

const clusterColors = ['#00ffcc', '#ff00aa', '#ffcc00', '#00aaff', '#aa66ff']
const genreList = ['Hip-Hop', 'R&B/Soul', 'Electronic', 'Rock', 'Pop', 'Indie']

export default function Clusters() {
  const { playlists, genreData } = useSpotify()

  // Generate pseudo-PCA cluster data based on playlist characteristics
  const clusterData = useMemo(() => {
    return playlists.slice(0, 12).map((playlist, i) => {
      // Generate pseudo-coordinates based on playlist ID hash
      const hash = playlist.id.split('').reduce((a, b) => a + b.charCodeAt(0), 0)
      return {
        id: playlist.id,
        name: playlist.name.length > 20 ? playlist.name.substring(0, 20) + '...' : playlist.name,
        x: ((hash % 100) - 50) + Math.sin(i) * 20,
        y: ((hash * 7 % 100) - 50) + Math.cos(i) * 20,
        trackCount: playlist.tracks.total,
        cluster: Math.floor(i / 4), // Simple clustering
      }
    })
  }, [playlists])

  // Heatmap data
  const heatmapData = useMemo(() => {
    return playlists.slice(0, 8).map((p, pi) => {
      const profile: Record<string, number> = {}
      genreList.forEach((genre, gi) => {
        // Generate pseudo-random but consistent values
        const seed = p.id.charCodeAt(0) + gi
        profile[genre] = Math.max(0, (seed * 17 % 50) + (gi === 0 ? 20 : 0))
      })
      return {
        name: p.name.length > 20 ? p.name.substring(0, 20) + '...' : p.name,
        ...profile,
      }
    })
  }, [playlists])

  // Library taste profile from actual genre data
  const tasteProfile = useMemo(() => {
    const total = genreData.reduce((sum, g) => sum + g.value, 0)
    return genreData.slice(0, 6).map(g => ({
      genre: g.name,
      percent: Math.round((g.value / total) * 100),
    }))
  }, [genreData])

  const CustomTooltip = ({ active, payload }: any) => {
    if (!active || !payload?.length) return null
    const data = payload[0].payload
    return (
      <div className="bg-void-200 border border-border-subtle rounded-lg px-4 py-3 shadow-lg">
        <p className="text-text-primary font-medium">{data.name}</p>
        <p className="text-sm text-text-muted">{data.trackCount} tracks</p>
        <p className="text-xs text-neon-cyan mt-1">Cluster {data.cluster + 1}</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen">
      <PageHeader title="Clusters" subtitle="Playlist similarity visualization" />
      
      <div className="p-8 space-y-8">
        {/* PCA Scatter Plot */}
        <Card title="Playlist Clusters (Simulated PCA)" icon="🗺️" hint="Playlists positioned by genre similarity. Size = track count." delay={0.1}>
          <ResponsiveContainer width="100%" height={500}>
            <ScatterChart margin={{ top: 20, right: 80, bottom: 60, left: 20 }}>
              <XAxis 
                type="number" 
                dataKey="x" 
                name="PC1"
                stroke="#606070"
                tick={{ fill: '#a0a0b0', fontSize: 12 }}
                label={{ 
                  value: 'PC1 (Genre Mix)', 
                  position: 'bottom', 
                  fill: '#606070',
                  offset: 40,
                }}
                domain={['auto', 'auto']}
              />
              <YAxis 
                type="number" 
                dataKey="y" 
                name="PC2"
                stroke="#606070"
                tick={{ fill: '#a0a0b0', fontSize: 12 }}
                label={{ 
                  value: 'PC2 (Energy)', 
                  angle: -90, 
                  position: 'insideLeft',
                  fill: '#606070',
                }}
                domain={['auto', 'auto']}
              />
              <ZAxis 
                type="number" 
                dataKey="trackCount" 
                range={[100, 800]} 
                name="Tracks"
              />
              <Tooltip content={<CustomTooltip />} />
              <Scatter data={clusterData} shape="circle">
                {clusterData.map((entry, index) => (
                  <Cell 
                    key={index} 
                    fill={clusterColors[entry.cluster % clusterColors.length]}
                    fillOpacity={0.8}
                    stroke={clusterColors[entry.cluster % clusterColors.length]}
                    strokeWidth={2}
                  />
                ))}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
          
          {/* Playlist labels */}
          <div className="flex flex-wrap gap-3 mt-4 justify-center">
            {clusterData.map((playlist) => (
              <span 
                key={playlist.id}
                className="px-3 py-1.5 rounded-full text-xs font-medium border"
                style={{ 
                  borderColor: clusterColors[playlist.cluster % clusterColors.length],
                  color: clusterColors[playlist.cluster % clusterColors.length],
                  backgroundColor: `${clusterColors[playlist.cluster % clusterColors.length]}10`,
                }}
              >
                {playlist.name}
              </span>
            ))}
          </div>
        </Card>

        <div className="grid grid-cols-2 gap-6">
          {/* Heatmap */}
          <Card title="Playlist DNA Heatmap" icon="🧬" hint="Genre distribution across your top playlists." delay={0.2}>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr>
                    <th className="text-left text-xs font-semibold text-text-muted uppercase tracking-wider p-2"></th>
                    {genreList.map(genre => (
                      <th key={genre} className="text-center text-[10px] font-semibold text-text-muted uppercase tracking-wider p-1.5">
                        {genre.split('/')[0].substring(0, 6)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {heatmapData.map((row, i) => (
                    <tr key={i} className="border-t border-border-subtle">
                      <td className="text-xs text-text-primary p-2 max-w-[120px] truncate">
                        {row.name}
                      </td>
                      {genreList.map(genre => {
                        const value = (row as any)[genre] || 0
                        const intensity = Math.min(value / 50, 1)
                        const color = value > 25 
                          ? `rgba(0, 255, 204, ${intensity})`
                          : value > 0 
                            ? `rgba(0, 170, 255, ${intensity * 0.8})`
                            : 'transparent'
                        return (
                          <td key={genre} className="p-1">
                            <div 
                              className="w-full h-7 rounded flex items-center justify-center text-[10px] font-mono"
                              style={{
                                backgroundColor: color,
                                color: intensity > 0.5 ? '#050508' : '#606070',
                              }}
                            >
                              {value > 0 ? `${value}%` : '-'}
                            </div>
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {/* Library Taste Profile */}
          <Card title="Library Taste Profile" icon="🎯" delay={0.3}>
            <p className="text-sm text-text-muted mb-4">
              Your overall library genre distribution
            </p>
            <div className="space-y-3">
              {tasteProfile.map((item, i) => (
                <div key={item.genre} className="space-y-1.5">
                  <div className="flex justify-between text-sm">
                    <span className="text-text-primary">{item.genre}</span>
                    <span className="text-neon-cyan font-mono">{item.percent}%</span>
                  </div>
                  <div className="h-2 bg-void-500 rounded-full overflow-hidden">
                    <motion.div
                      className="h-full rounded-full bg-gradient-to-r from-neon-cyan to-neon-blue"
                      initial={{ width: 0 }}
                      animate={{ width: `${(item.percent / 40) * 100}%` }}
                      transition={{ duration: 0.5, delay: i * 0.08 }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
