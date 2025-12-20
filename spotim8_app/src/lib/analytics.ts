/**
 * Analytics Processing
 * 
 * All processing happens client-side in your browser.
 * No data is ever sent to or stored on any server.
 */

import type { SpotifyTrack, SpotifyPlaylist } from './spotify'

export interface LibraryStats {
  totalTracks: number
  totalArtists: number
  totalPlaylists: number
  totalHours: number
  avgPopularity: number
}

export interface GenreData {
  name: string
  value: number
  color: string
}

export interface ArtistData {
  name: string
  trackCount: number
  avgPopularity: number
  genre: string
}

export interface TrackData {
  id: string
  name: string
  artist: string
  year: number
  popularity: number
  genre: string
  playlistCount: number
  duration_ms: number
}

export interface TimelineData {
  year: number
  [genre: string]: number
}

// Genre color mapping
const GENRE_COLORS: Record<string, string> = {
  'hip hop': '#00ffcc',
  'rap': '#00ffcc',
  'r&b': '#ff00aa',
  'soul': '#ff00aa',
  'electronic': '#ffcc00',
  'edm': '#ffcc00',
  'house': '#ffcc00',
  'rock': '#00aaff',
  'metal': '#00aaff',
  'pop': '#aa66ff',
  'indie': '#ff6600',
  'alternative': '#ff6600',
  'jazz': '#00ff66',
  'classical': '#ff0066',
  'country': '#66ff00',
  'latin': '#ff9900',
}

// Map specific genres to core categories
function getCoreGenre(genres: string[]): string {
  if (!genres || genres.length === 0) return 'Other'
  
  const genreStr = genres.join(' ').toLowerCase()
  
  if (genreStr.includes('hip hop') || genreStr.includes('rap') || genreStr.includes('trap')) return 'Hip-Hop'
  if (genreStr.includes('r&b') || genreStr.includes('soul') || genreStr.includes('neo soul')) return 'R&B/Soul'
  if (genreStr.includes('electronic') || genreStr.includes('edm') || genreStr.includes('house') || genreStr.includes('techno')) return 'Electronic'
  if (genreStr.includes('rock') || genreStr.includes('metal') || genreStr.includes('punk')) return 'Rock'
  if (genreStr.includes('pop')) return 'Pop'
  if (genreStr.includes('indie') || genreStr.includes('alternative')) return 'Indie'
  if (genreStr.includes('jazz')) return 'Jazz'
  if (genreStr.includes('classical')) return 'Classical'
  if (genreStr.includes('country')) return 'Country'
  if (genreStr.includes('latin') || genreStr.includes('reggaeton')) return 'Latin'
  
  return 'Other'
}

function getGenreColor(genre: string): string {
  const lowerGenre = genre.toLowerCase()
  for (const [key, color] of Object.entries(GENRE_COLORS)) {
    if (lowerGenre.includes(key)) return color
  }
  return '#666666'
}

// Process library data into analytics format
export function processLibraryData(
  playlists: SpotifyPlaylist[],
  allTracks: Map<string, { track: SpotifyTrack; playlistIds: Set<string> }>,
  artistGenres: Map<string, string[]>
): {
  stats: LibraryStats
  genreData: GenreData[]
  topArtists: ArtistData[]
  tracks: TrackData[]
  timelineData: TimelineData[]
  decadeData: { decade: string; tracks: number }[]
  popularityDistribution: { range: string; count: number }[]
} {
  const tracks = Array.from(allTracks.values())
  
  // Calculate stats
  const totalDurationMs = tracks.reduce((sum, t) => sum + (t.track.duration_ms || 0), 0)
  const avgPopularity = tracks.reduce((sum, t) => sum + (t.track.popularity || 0), 0) / tracks.length
  
  // Get unique artists
  const artistCounts = new Map<string, { count: number; totalPop: number; genre: string }>()
  tracks.forEach(({ track }) => {
    track.artists.forEach(artist => {
      const genres = artistGenres.get(artist.id) || []
      const coreGenre = getCoreGenre(genres)
      const existing = artistCounts.get(artist.name) || { count: 0, totalPop: 0, genre: coreGenre }
      artistCounts.set(artist.name, {
        count: existing.count + 1,
        totalPop: existing.totalPop + (track.popularity || 0),
        genre: coreGenre,
      })
    })
  })
  
  // Genre counts
  const genreCounts = new Map<string, number>()
  tracks.forEach(({ track }) => {
    const artistId = track.artists[0]?.id
    const genres = artistGenres.get(artistId) || []
    const coreGenre = getCoreGenre(genres)
    genreCounts.set(coreGenre, (genreCounts.get(coreGenre) || 0) + 1)
  })
  
  const genreData: GenreData[] = Array.from(genreCounts.entries())
    .map(([name, value]) => ({
      name,
      value,
      color: getGenreColor(name),
    }))
    .sort((a, b) => b.value - a.value)
  
  // Top artists
  const topArtists: ArtistData[] = Array.from(artistCounts.entries())
    .map(([name, data]) => ({
      name,
      trackCount: data.count,
      avgPopularity: Math.round(data.totalPop / data.count),
      genre: data.genre,
    }))
    .sort((a, b) => b.trackCount - a.trackCount)
    .slice(0, 30)
  
  // Track data with years
  const trackData: TrackData[] = tracks.map(({ track, playlistIds }) => {
    const artistId = track.artists[0]?.id
    const genres = artistGenres.get(artistId) || []
    const year = parseInt(track.album.release_date?.substring(0, 4) || '0')
    
    return {
      id: track.id,
      name: track.name,
      artist: track.artists.map(a => a.name).join(', '),
      year,
      popularity: track.popularity || 0,
      genre: getCoreGenre(genres),
      playlistCount: playlistIds.size,
      duration_ms: track.duration_ms,
    }
  })
  
  // Timeline data
  const yearGenreCounts = new Map<number, Map<string, number>>()
  trackData.forEach(track => {
    if (track.year >= 1970 && track.year <= 2025) {
      if (!yearGenreCounts.has(track.year)) {
        yearGenreCounts.set(track.year, new Map())
      }
      const yearMap = yearGenreCounts.get(track.year)!
      yearMap.set(track.genre, (yearMap.get(track.genre) || 0) + 1)
    }
  })
  
  const allGenres = ['Hip-Hop', 'R&B/Soul', 'Electronic', 'Rock', 'Pop', 'Indie']
  const timelineData: TimelineData[] = []
  for (let year = 1970; year <= 2025; year++) {
    const yearData: TimelineData = { year }
    const yearCounts = yearGenreCounts.get(year) || new Map()
    allGenres.forEach(genre => {
      yearData[genre] = yearCounts.get(genre) || 0
    })
    timelineData.push(yearData)
  }
  
  // Decade breakdown
  const decadeCounts = new Map<string, number>()
  trackData.forEach(track => {
    if (track.year >= 1960 && track.year <= 2029) {
      const decade = `${Math.floor(track.year / 10) * 10}s`
      decadeCounts.set(decade, (decadeCounts.get(decade) || 0) + 1)
    }
  })
  const decadeData = Array.from(decadeCounts.entries())
    .map(([decade, tracks]) => ({ decade, tracks }))
    .sort((a, b) => a.decade.localeCompare(b.decade))
  
  // Popularity distribution
  const popBuckets = new Map<number, number>()
  for (let i = 0; i < 20; i++) {
    popBuckets.set(i, 0)
  }
  trackData.forEach(track => {
    const bucket = Math.min(Math.floor(track.popularity / 5), 19)
    popBuckets.set(bucket, (popBuckets.get(bucket) || 0) + 1)
  })
  const popularityDistribution = Array.from(popBuckets.entries())
    .map(([bucket, count]) => ({
      range: `${bucket * 5}-${bucket * 5 + 4}`,
      count,
    }))
  
  return {
    stats: {
      totalTracks: tracks.length,
      totalArtists: artistCounts.size,
      totalPlaylists: playlists.length,
      totalHours: Math.round(totalDurationMs / 3600000),
      avgPopularity: Math.round(avgPopularity),
    },
    genreData,
    topArtists,
    tracks: trackData,
    timelineData,
    decadeData,
    popularityDistribution,
  }
}

// Find hidden gems (low popularity, in library)
export function findHiddenGems(tracks: TrackData[]): TrackData[] {
  return tracks
    .filter(t => t.popularity > 0 && t.popularity <= 35)
    .sort((a, b) => b.playlistCount - a.playlistCount || a.popularity - b.popularity)
    .slice(0, 20)
}

// Calculate playlist genre profiles
export function getPlaylistGenreProfile(
  tracks: TrackData[]
): Record<string, number> {
  const genreCounts: Record<string, number> = {}
  tracks.forEach(track => {
    genreCounts[track.genre] = (genreCounts[track.genre] || 0) + 1
  })
  
  const total = Object.values(genreCounts).reduce((a, b) => a + b, 0)
  const profile: Record<string, number> = {}
  Object.entries(genreCounts).forEach(([genre, count]) => {
    profile[genre] = Math.round((count / total) * 100)
  })
  
  return profile
}

