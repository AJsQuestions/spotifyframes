import { useState } from 'react'
import { motion } from 'framer-motion'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  AreaChart, Area, PieChart, Pie, Cell,
  Legend, CartesianGrid,
} from 'recharts'
import PageHeader from '../components/PageHeader'
import Card from '../components/Card'
import StatCard from '../components/StatCard'
import { useSpotify } from '../context/SpotifyContext'

const chartColors = ['#00ffcc', '#ff00aa', '#ffcc00', '#00aaff', '#aa66ff', '#ff6600', '#00ff66', '#ff0066']

export default function Dashboard() {
  const { 
    libraryData, 
    genreData, 
    topArtists, 
    timelineData,
    popularityDistribution,
    decadeData,
  } = useSpotify()
  
  const [selectedGenre, setSelectedGenre] = useState<string>('All')
  const genres = ['All', ...genreData.map(g => g.name)]

  // Custom tooltip styles
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload?.length) return null
    return (
      <div className="bg-void-200 border border-border-subtle rounded-lg px-4 py-3 shadow-lg">
        <p className="text-text-primary font-medium mb-1">{label}</p>
        {payload.map((entry: any, i: number) => (
          <p key={i} className="text-sm" style={{ color: entry.color }}>
            {entry.name}: {typeof entry.value === 'number' ? entry.value.toLocaleString() : entry.value}
          </p>
        ))}
      </div>
    )
  }

  if (!libraryData) {
    return <div className="p-8 text-text-muted">Loading...</div>
  }

  return (
    <div className="min-h-screen">
      <PageHeader title="Dashboard" subtitle="Your library at a glance" />
      
      <div className="p-8 space-y-8">
        {/* Filter Row */}
        <motion.div 
          className="flex items-center gap-5 p-5 bg-void-200 rounded-2xl border border-border-subtle"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <span className="text-xs font-semibold uppercase tracking-wider text-text-muted">
            Filter by Genre:
          </span>
          <select
            value={selectedGenre}
            onChange={(e) => setSelectedGenre(e.target.value)}
            className="bg-void-500 border border-border rounded-lg px-4 py-2.5 text-sm text-text-primary focus:outline-none focus:border-neon-cyan focus:ring-2 focus:ring-neon-cyan/20 min-w-[200px]"
          >
            {genres.map(genre => (
              <option key={genre} value={genre}>{genre}</option>
            ))}
          </select>
          <div className="ml-auto text-sm font-mono text-neon-cyan">
            {libraryData.totalTracks.toLocaleString()} tracks
          </div>
        </motion.div>

        {/* Stats Grid */}
        <div className="grid grid-cols-5 gap-4">
          <StatCard icon="🎵" value={libraryData.totalTracks.toLocaleString()} label="Tracks" delay={0} />
          <StatCard icon="🎤" value={libraryData.totalArtists.toLocaleString()} label="Artists" delay={0.05} />
          <StatCard icon="📂" value={libraryData.totalPlaylists} label="Playlists" delay={0.1} />
          <StatCard icon="⏱️" value={`${libraryData.totalHours}h`} label="Duration" delay={0.15} />
          <StatCard icon="📈" value={libraryData.avgPopularity} label="Avg Popularity" accent delay={0.2} />
        </div>

        {/* Charts Row 1 */}
        <div className="grid grid-cols-2 gap-6">
          {/* Top Artists */}
          <Card title="Top Artists" icon="🎤" hint="Your most-featured artists" delay={0.25}>
            <ResponsiveContainer width="100%" height={400}>
              <BarChart
                data={topArtists.slice(0, 12)}
                layout="vertical"
                margin={{ left: 10, right: 40 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#1a1a25" horizontal={false} />
                <XAxis type="number" stroke="#606070" tick={{ fill: '#a0a0b0', fontSize: 12 }} />
                <YAxis 
                  dataKey="name" 
                  type="category" 
                  width={100} 
                  stroke="#606070" 
                  tick={{ fill: '#f0f0f5', fontSize: 12 }}
                />
                <Tooltip content={<CustomTooltip />} />
                <Bar 
                  dataKey="trackCount" 
                  fill="url(#barGradient)" 
                  radius={[0, 4, 4, 0]}
                  label={{ position: 'right', fill: '#a0a0b0', fontSize: 11 }}
                />
                <defs>
                  <linearGradient id="barGradient" x1="0" y1="0" x2="1" y2="0">
                    <stop offset="0%" stopColor="#00ffcc" />
                    <stop offset="100%" stopColor="#ff00aa" />
                  </linearGradient>
                </defs>
              </BarChart>
            </ResponsiveContainer>
          </Card>

          {/* Genre Breakdown */}
          <Card title="Genre Breakdown" icon="🎸" hint="Distribution of genres in your library" delay={0.3}>
            <ResponsiveContainer width="100%" height={400}>
              <PieChart>
                <Pie
                  data={genreData.slice(0, 8)}
                  cx="50%"
                  cy="50%"
                  innerRadius={80}
                  outerRadius={140}
                  paddingAngle={2}
                  dataKey="value"
                  label={({ name, percent }) => `${name} (${(percent * 100).toFixed(0)}%)`}
                  labelLine={{ stroke: '#606070' }}
                >
                  {genreData.slice(0, 8).map((entry, index) => (
                    <Cell key={index} fill={entry.color || chartColors[index % chartColors.length]} stroke="#050508" strokeWidth={2} />
                  ))}
                </Pie>
                <Tooltip content={<CustomTooltip />} />
              </PieChart>
            </ResponsiveContainer>
          </Card>
        </div>

        {/* Timeline Chart */}
        {timelineData.length > 0 && (
          <Card title="Timeline by Genre" icon="📈" hint="When your music was released" delay={0.35}>
            <ResponsiveContainer width="100%" height={400}>
              <AreaChart data={timelineData.filter(d => d.year >= 1990)} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1a1a25" />
                <XAxis dataKey="year" stroke="#606070" tick={{ fill: '#a0a0b0', fontSize: 12 }} />
                <YAxis stroke="#606070" tick={{ fill: '#a0a0b0', fontSize: 12 }} />
                <Tooltip content={<CustomTooltip />} />
                <Legend 
                  wrapperStyle={{ paddingTop: '20px' }}
                  formatter={(value) => <span style={{ color: '#a0a0b0', fontSize: 12 }}>{value}</span>}
                />
                {['Hip-Hop', 'R&B/Soul', 'Electronic', 'Rock', 'Pop', 'Indie'].map((genre, i) => (
                  <Area
                    key={genre}
                    type="monotone"
                    dataKey={genre}
                    stackId="1"
                    stroke={chartColors[i]}
                    fill={chartColors[i]}
                    fillOpacity={0.6}
                  />
                ))}
              </AreaChart>
            </ResponsiveContainer>
          </Card>
        )}

        {/* Charts Row 2 */}
        <div className="grid grid-cols-2 gap-6">
          {/* Popularity Distribution */}
          {popularityDistribution.length > 0 && (
            <Card title="Popularity Distribution" icon="📊" delay={0.4}>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={popularityDistribution}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1a1a25" vertical={false} />
                  <XAxis dataKey="range" stroke="#606070" tick={{ fill: '#a0a0b0', fontSize: 10 }} />
                  <YAxis stroke="#606070" tick={{ fill: '#a0a0b0', fontSize: 12 }} />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="count" fill="#00ffcc" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          )}

          {/* Decades Breakdown */}
          {decadeData.length > 0 && (
            <Card title="Decades Breakdown" icon="📅" delay={0.45}>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={decadeData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1a1a25" vertical={false} />
                  <XAxis dataKey="decade" stroke="#606070" tick={{ fill: '#a0a0b0', fontSize: 12 }} />
                  <YAxis stroke="#606070" tick={{ fill: '#a0a0b0', fontSize: 12 }} />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="tracks" fill="url(#decadeGradient)" radius={[4, 4, 0, 0]}>
                    {decadeData.map((_, index) => (
                      <Cell key={index} fill={chartColors[index % chartColors.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
