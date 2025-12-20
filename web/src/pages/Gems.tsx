import { motion } from 'framer-motion'
import {
  ScatterChart, Scatter, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Cell,
} from 'recharts'
import PageHeader from '../components/PageHeader'
import Card from '../components/Card'
import { useSpotify } from '../context/SpotifyContext'
import { Play, ExternalLink } from 'lucide-react'

const genreColors: Record<string, string> = {
  'Hip-Hop': '#00ffcc',
  'R&B/Soul': '#ff00aa',
  'Electronic': '#ffcc00',
  'Rock': '#00aaff',
  'Pop': '#aa66ff',
  'Indie': '#ff6600',
  'Jazz': '#00ff66',
  'Classical': '#ff0066',
  'Other': '#666666',
}

export default function Gems() {
  const { hiddenGems } = useSpotify()

  const CustomTooltip = ({ active, payload }: any) => {
    if (!active || !payload?.length) return null
    const data = payload[0].payload
    return (
      <div className="bg-void-200 border border-border-subtle rounded-lg px-4 py-3 shadow-lg max-w-xs">
        <p className="text-text-primary font-medium">{data.name}</p>
        <p className="text-sm text-text-muted">{data.artist}</p>
        <div className="flex gap-4 mt-2 text-xs">
          <span className="text-neon-cyan">Popularity: {data.popularity}</span>
          <span className="text-text-muted">{data.year}</span>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen">
      <PageHeader title="Hidden Gems" subtitle="Underrated tracks in your library" />
      
      <div className="p-8 space-y-8">
        {/* Info Box */}
        <motion.div 
          className="p-5 bg-neon-cyan/5 rounded-2xl border border-neon-cyan/20"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <p className="text-text-secondary text-sm">
            💎 <strong className="text-neon-cyan">Hidden Gems</strong> are tracks with low Spotify popularity 
            (under 35) that appear in your library. These deserve more love!
          </p>
        </motion.div>

        {/* Scatter Plot */}
        {hiddenGems.length > 0 && (
          <Card title="Hidden Gems Explorer" icon="💎" hint="Low-popularity tracks that deserve more attention." delay={0.1}>
            <ResponsiveContainer width="100%" height={350}>
              <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                <XAxis 
                  type="number" 
                  dataKey="year" 
                  name="Year"
                  stroke="#606070"
                  tick={{ fill: '#a0a0b0', fontSize: 12 }}
                  domain={['auto', 'auto']}
                  label={{ 
                    value: 'Release Year', 
                    position: 'bottom', 
                    fill: '#606070',
                    offset: 0,
                  }}
                />
                <YAxis 
                  type="number" 
                  dataKey="popularity" 
                  name="Popularity"
                  stroke="#606070"
                  tick={{ fill: '#a0a0b0', fontSize: 12 }}
                  domain={[0, 40]}
                  label={{ 
                    value: 'Popularity', 
                    angle: -90, 
                    position: 'insideLeft',
                    fill: '#606070',
                  }}
                />
                <Tooltip content={<CustomTooltip />} cursor={{ strokeDasharray: '3 3' }} />
                <Scatter data={hiddenGems} shape="circle">
                  {hiddenGems.map((entry, index) => (
                    <Cell 
                      key={index} 
                      fill={genreColors[entry.genre] || '#666666'}
                      fillOpacity={0.9}
                      r={8 + entry.playlistCount * 2}
                    />
                  ))}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
            
            {/* Genre Legend */}
            <div className="flex flex-wrap gap-4 mt-4 justify-center">
              {Object.entries(genreColors).filter(([k]) => k !== 'Other').slice(0, 6).map(([genre, color]) => (
                <div key={genre} className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
                  <span className="text-xs text-text-muted">{genre}</span>
                </div>
              ))}
            </div>
          </Card>
        )}

        {/* Gems Table */}
        <Card title="Gem Collection" icon="📋" delay={0.2}>
          {hiddenGems.length === 0 ? (
            <p className="text-text-muted text-center py-8">
              No hidden gems found in your library yet.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border-subtle">
                    <th className="text-left text-xs font-semibold text-text-muted uppercase tracking-wider p-4">Track</th>
                    <th className="text-left text-xs font-semibold text-text-muted uppercase tracking-wider p-4">Artist</th>
                    <th className="text-center text-xs font-semibold text-text-muted uppercase tracking-wider p-4">Popularity</th>
                    <th className="text-left text-xs font-semibold text-text-muted uppercase tracking-wider p-4">Genre</th>
                    <th className="text-center text-xs font-semibold text-text-muted uppercase tracking-wider p-4">Year</th>
                  </tr>
                </thead>
                <tbody>
                  {hiddenGems.map((gem, i) => (
                    <motion.tr 
                      key={gem.id}
                      className="border-b border-border-subtle hover:bg-void-400/30 transition-colors group"
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.03 }}
                    >
                      <td className="p-4">
                        <span className="text-sm font-medium text-text-primary">
                          {gem.name.length > 40 ? gem.name.substring(0, 40) + '...' : gem.name}
                        </span>
                      </td>
                      <td className="p-4 text-sm text-text-secondary">
                        {gem.artist.length > 30 ? gem.artist.substring(0, 30) + '...' : gem.artist}
                      </td>
                      <td className="p-4 text-center">
                        <span className="inline-flex items-center justify-center w-10 h-6 rounded-full bg-neon-cyan/10 text-neon-cyan text-xs font-mono font-bold">
                          {gem.popularity}
                        </span>
                      </td>
                      <td className="p-4">
                        <span 
                          className="inline-flex px-2.5 py-1 rounded-full text-xs font-medium"
                          style={{ 
                            backgroundColor: `${genreColors[gem.genre] || '#666666'}20`,
                            color: genreColors[gem.genre] || '#666666',
                          }}
                        >
                          {gem.genre}
                        </span>
                      </td>
                      <td className="p-4 text-center text-sm text-text-muted font-mono">
                        {gem.year || '-'}
                      </td>
                    </motion.tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
