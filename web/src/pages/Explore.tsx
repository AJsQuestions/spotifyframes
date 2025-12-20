import { useState, useMemo } from 'react'
import { motion } from 'framer-motion'
import {
  Treemap, ResponsiveContainer, Tooltip, RadarChart,
  PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, Legend,
} from 'recharts'
import PageHeader from '../components/PageHeader'
import Card from '../components/Card'
import { useSpotify } from '../context/SpotifyContext'
import { getPlaylistGenreProfile } from '../lib/analytics'

const chartColors = ['#00ffcc', '#ff00aa', '#ffcc00', '#00aaff', '#aa66ff', '#ff6600', '#00ff66', '#ff0066']

const genreColorMap: Record<string, string> = {
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

export default function Explore() {
  const { topArtists, playlists, genreData, tracks } = useSpotify()
  const [selectedPlaylist, setSelectedPlaylist] = useState<string>('')

  // Build treemap data from artists
  const treemapData = useMemo(() => {
    return topArtists.slice(0, 25).map((artist, i) => ({
      name: artist.name,
      size: artist.trackCount,
      genre: artist.genre,
      popularity: artist.avgPopularity,
      fill: genreColorMap[artist.genre] || chartColors[i % chartColors.length],
    }))
  }, [topArtists])

  // Playlist genre heatmap data
  const heatmapData = useMemo(() => {
    return playlists.slice(0, 10).map(p => {
      // Calculate genre distribution for this playlist
      const playlistTracks = tracks.filter(t => 
        // This is a simplification - we'd need proper playlist-track mapping
        true
      )
      const profile = getPlaylistGenreProfile(playlistTracks.slice(0, 50))
      return {
        name: p.name.length > 25 ? p.name.substring(0, 25) + '...' : p.name,
        ...profile,
      }
    })
  }, [playlists, tracks])

  // Radar data for library profile
  const radarData = useMemo(() => {
    const total = genreData.reduce((sum, g) => sum + g.value, 0)
    return genreData.slice(0, 7).map(g => ({
      genre: g.name,
      library: Math.round((g.value / total) * 100),
      playlist: selectedPlaylist ? Math.floor(Math.random() * 50) : 0, // Placeholder
    }))
  }, [genreData, selectedPlaylist])

  const genreList = ['Hip-Hop', 'R&B/Soul', 'Electronic', 'Rock', 'Pop', 'Indie']

  const CustomTooltip = ({ active, payload }: any) => {
    if (!active || !payload?.length) return null
    const data = payload[0].payload
    return (
      <div className="bg-void-200 border border-border-subtle rounded-lg px-4 py-3 shadow-lg">
        <p className="text-text-primary font-medium">{data.name}</p>
        <p className="text-sm text-neon-cyan">{data.size} tracks</p>
        {data.popularity && (
          <p className="text-xs text-text-muted">Avg Popularity: {data.popularity}</p>
        )}
      </div>
    )
  }

  return (
    <div className="min-h-screen">
      <PageHeader title="Deep Dive" subtitle="Explore your music landscape" />
      
      <div className="p-8 space-y-8">
        {/* Artist Landscape Treemap */}
        <Card title="Artist Landscape" icon="🌳" hint="Your top artists sized by track count" delay={0.1}>
          <ResponsiveContainer width="100%" height={450}>
            <Treemap
              data={treemapData}
              dataKey="size"
              aspectRatio={4 / 3}
              stroke="#050508"
              fill="#00ffcc"
              content={({ x, y, width, height, name, fill }: any) => {
                if (width < 40 || height < 30) return null
                return (
                  <g>
                    <rect
                      x={x}
                      y={y}
                      width={width}
                      height={height}
                      fill={fill}
                      stroke="#050508"
                      strokeWidth={2}
                      rx={4}
                      style={{ transition: 'all 0.2s' }}
                    />
                    <text
                      x={x + width / 2}
                      y={y + height / 2}
                      textAnchor="middle"
                      dominantBaseline="middle"
                      fill="#050508"
                      fontSize={Math.min(width / 8, 14)}
                      fontWeight={600}
                    >
                      {width > 60 ? name : name?.substring(0, 8)}
                    </text>
                  </g>
                )
              }}
            >
              <Tooltip content={<CustomTooltip />} />
            </Treemap>
          </ResponsiveContainer>
        </Card>

        <div className="grid grid-cols-2 gap-6">
          {/* Playlist DNA Heatmap */}
          <Card title="Playlist DNA" icon="🧬" hint="Genre composition across playlists" delay={0.2}>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr>
                    <th className="text-left text-xs font-semibold text-text-muted uppercase tracking-wider p-3"></th>
                    {genreList.slice(0, 5).map(genre => (
                      <th key={genre} className="text-center text-xs font-semibold text-text-muted uppercase tracking-wider p-2">
                        {genre.split('/')[0].substring(0, 6)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {playlists.slice(0, 8).map((playlist, i) => (
                    <tr key={playlist.id} className="border-t border-border-subtle">
                      <td className="text-sm text-text-primary p-3 max-w-[150px] truncate">
                        {playlist.name.length > 20 ? playlist.name.substring(0, 20) + '...' : playlist.name}
                      </td>
                      {genreList.slice(0, 5).map((genre, gi) => {
                        const value = Math.floor(Math.random() * 50 + (gi === 0 ? 20 : 0)) // Placeholder
                        const intensity = value / 60
                        return (
                          <td key={genre} className="p-1">
                            <div 
                              className="w-full h-8 rounded flex items-center justify-center text-xs font-mono"
                              style={{
                                backgroundColor: `rgba(0, 255, 204, ${intensity})`,
                                color: intensity > 0.5 ? '#050508' : '#a0a0b0',
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

          {/* Taste Profile Radar */}
          <Card title="Your Taste Profile" icon="🎯" delay={0.3}>
            <div className="mb-4">
              <label className="text-xs font-semibold text-text-muted uppercase tracking-wider block mb-2">
                Compare with playlist:
              </label>
              <select
                value={selectedPlaylist}
                onChange={(e) => setSelectedPlaylist(e.target.value)}
                className="w-full bg-void-500 border border-border rounded-lg px-4 py-2.5 text-sm text-text-primary focus:outline-none focus:border-neon-cyan"
              >
                <option value="">Select a playlist...</option>
                {playlists.map(p => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </div>
            <ResponsiveContainer width="100%" height={320}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="#1a1a25" />
                <PolarAngleAxis 
                  dataKey="genre" 
                  tick={{ fill: '#a0a0b0', fontSize: 11 }} 
                />
                <PolarRadiusAxis 
                  angle={30} 
                  domain={[0, 50]} 
                  tick={{ fill: '#606070', fontSize: 10 }}
                />
                <Radar
                  name="Your Library"
                  dataKey="library"
                  stroke="#00ffcc"
                  fill="#00ffcc"
                  fillOpacity={0.3}
                />
                {selectedPlaylist && (
                  <Radar
                    name="Selected Playlist"
                    dataKey="playlist"
                    stroke="#ff00aa"
                    fill="#ff00aa"
                    fillOpacity={0.3}
                  />
                )}
                <Legend 
                  wrapperStyle={{ paddingTop: 10 }}
                  formatter={(value) => <span className="text-text-secondary text-sm">{value}</span>}
                />
              </RadarChart>
            </ResponsiveContainer>
          </Card>
        </div>
      </div>
    </div>
  )
}
