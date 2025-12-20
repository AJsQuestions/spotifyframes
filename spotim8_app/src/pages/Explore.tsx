import { useState, useMemo } from 'react'
import {
  Treemap, ResponsiveContainer, Tooltip, RadarChart,
  PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, Legend,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from 'recharts'
import PageHeader from '../components/PageHeader'
import Card from '../components/Card'
import { useSpotify } from '../context/SpotifyContext'

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
  const { topArtists, genreData, tracks } = useSpotify()
  const [selectedGenre, setSelectedGenre] = useState<string>('')

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

  // Radar data for library profile
  const radarData = useMemo(() => {
    const total = genreData.reduce((sum, g) => sum + g.value, 0)
    return genreData.slice(0, 7).map(g => ({
      genre: g.name,
      library: Math.round((g.value / total) * 100),
    }))
  }, [genreData])

  // Genre breakdown for bar chart
  const genreBarData = useMemo(() => {
    return genreData.slice(0, 8).map(g => ({
      name: g.name,
      tracks: g.value,
      fill: genreColorMap[g.name] || '#666666',
    }))
  }, [genreData])

  // Top artists by genre
  const artistsByGenre = useMemo(() => {
    if (!selectedGenre) return topArtists.slice(0, 10)
    return topArtists.filter(a => a.genre === selectedGenre).slice(0, 10)
  }, [topArtists, selectedGenre])

  // Popularity by genre
  const popularityByGenre = useMemo(() => {
    const genreStats: Record<string, { total: number; count: number }> = {}
    tracks.forEach(track => {
      if (!genreStats[track.genre]) {
        genreStats[track.genre] = { total: 0, count: 0 }
      }
      genreStats[track.genre].total += track.popularity
      genreStats[track.genre].count++
    })
    return Object.entries(genreStats)
      .map(([genre, stats]) => ({
        genre,
        avgPopularity: Math.round(stats.total / stats.count),
        fill: genreColorMap[genre] || '#666666',
      }))
      .sort((a, b) => b.avgPopularity - a.avgPopularity)
  }, [tracks])

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

  const BarTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload?.length) return null
    return (
      <div className="bg-void-200 border border-border-subtle rounded-lg px-4 py-3 shadow-lg">
        <p className="text-text-primary font-medium">{label}</p>
        <p className="text-sm text-neon-cyan">{payload[0].value} tracks</p>
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
              isAnimationActive={true}
            >
              <Tooltip content={<CustomTooltip />} />
            </Treemap>
          </ResponsiveContainer>
        </Card>

        <div className="grid grid-cols-2 gap-6">
          {/* Genre Breakdown */}
          <Card title="Genre Distribution" icon="🎸" hint="Track count by genre" delay={0.2}>
            <ResponsiveContainer width="100%" height={350}>
              <BarChart data={genreBarData} layout="vertical" margin={{ left: 10, right: 30 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1a1a25" horizontal={false} />
                <XAxis type="number" stroke="#606070" tick={{ fill: '#a0a0b0', fontSize: 12 }} />
                <YAxis 
                  dataKey="name" 
                  type="category" 
                  width={90} 
                  stroke="#606070" 
                  tick={{ fill: '#f0f0f5', fontSize: 12 }}
                />
                <Tooltip content={<BarTooltip />} />
                <Bar dataKey="tracks" radius={[0, 4, 4, 0]}>
                  {genreBarData.map((entry, index) => (
                    <rect key={index} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </Card>

          {/* Taste Profile Radar */}
          <Card title="Your Taste Profile" icon="🎯" delay={0.3}>
            <ResponsiveContainer width="100%" height={350}>
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
                <Legend 
                  wrapperStyle={{ paddingTop: 10 }}
                  formatter={(value) => <span className="text-text-secondary text-sm">{value}</span>}
                />
              </RadarChart>
            </ResponsiveContainer>
          </Card>
        </div>

        <div className="grid grid-cols-2 gap-6">
          {/* Top Artists by Genre */}
          <Card title="Top Artists" icon="🎤" delay={0.4}>
            <div className="mb-4">
              <label className="text-xs font-semibold text-text-muted uppercase tracking-wider block mb-2">
                Filter by genre:
              </label>
              <select
                value={selectedGenre}
                onChange={(e) => setSelectedGenre(e.target.value)}
                className="w-full bg-void-500 border border-border rounded-lg px-4 py-2.5 text-sm text-text-primary focus:outline-none focus:border-neon-cyan"
              >
                <option value="">All Genres</option>
                {genreData.map(g => (
                  <option key={g.name} value={g.name}>{g.name}</option>
                ))}
              </select>
            </div>
            <div className="space-y-2 max-h-[280px] overflow-y-auto">
              {artistsByGenre.map((artist, i) => (
                <div 
                  key={artist.name}
                  className="flex items-center justify-between p-3 rounded-lg bg-void-500/50 hover:bg-void-400 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-text-muted font-mono text-sm w-6">{i + 1}</span>
                    <div>
                      <p className="text-text-primary font-medium">{artist.name}</p>
                      <p className="text-xs text-text-muted">{artist.genre}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-neon-cyan font-mono">{artist.trackCount}</p>
                    <p className="text-xs text-text-muted">tracks</p>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* Average Popularity by Genre */}
          <Card title="Popularity by Genre" icon="📊" hint="Average track popularity" delay={0.5}>
            <ResponsiveContainer width="100%" height={350}>
              <BarChart data={popularityByGenre} margin={{ top: 10, right: 30, left: 10, bottom: 40 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1a1a25" vertical={false} />
                <XAxis 
                  dataKey="genre" 
                  stroke="#606070" 
                  tick={{ fill: '#a0a0b0', fontSize: 10 }}
                  angle={-45}
                  textAnchor="end"
                  height={60}
                />
                <YAxis 
                  domain={[0, 100]}
                  stroke="#606070" 
                  tick={{ fill: '#a0a0b0', fontSize: 12 }} 
                />
                <Tooltip 
                  content={({ active, payload, label }) => {
                    if (!active || !payload?.length) return null
                    return (
                      <div className="bg-void-200 border border-border-subtle rounded-lg px-4 py-3 shadow-lg">
                        <p className="text-text-primary font-medium">{label}</p>
                        <p className="text-sm text-neon-cyan">Avg: {payload[0].value}</p>
                      </div>
                    )
                  }}
                />
                <Bar dataKey="avgPopularity" radius={[4, 4, 0, 0]}>
                  {popularityByGenre.map((entry, index) => (
                    <rect key={index} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </div>
      </div>
    </div>
  )
}
