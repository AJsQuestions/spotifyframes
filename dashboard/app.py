"""
🎵 Spotim8 - Your Personal Spotify Analytics
A full-featured web application with crossfiltering charts.
"""

import os
import sys
from pathlib import Path
from functools import lru_cache
from collections import Counter

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / 'notebooks'))

import dash
from dash import dcc, html, Input, Output, State, callback, ctx, ALL, no_update
from dash.exceptions import PreventUpdate
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

# Import shared library
from lib import (
    LibraryAnalyzer, 
    get_genres_list, 
    build_playlist_genre_profiles,
    canonical_core_genre,
    PlaylistSimilarityEngine
)

# ============================================================================
# APP CONFIGURATION
# ============================================================================

DATA_DIR = PROJECT_ROOT / 'data'

app = dash.Dash(
    __name__,
    suppress_callback_exceptions=True,
    title="Spotim8",
    update_title=None,
    external_stylesheets=[
        "https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Space+Mono:wght@400;700&display=swap"
    ]
)

# Custom color palette - Neon cyberpunk theme
COLORS = {
    'primary': '#00ffcc',      # Cyan accent
    'secondary': '#ff00aa',    # Magenta
    'tertiary': '#ffcc00',     # Gold
    'bg': '#0d0d0d',
    'card': '#151515',
    'surface': '#1a1a1a',
    'text': '#e6e6e6',
    'muted': '#666666',
    'gradient_start': '#00ffcc',
    'gradient_end': '#ff00aa',
}

CHART_COLORS = ['#00ffcc', '#ff00aa', '#ffcc00', '#00aaff', '#ff6600', 
                '#aa00ff', '#00ff66', '#ff0066', '#66ff00', '#0066ff']

# ============================================================================
# DATA MANAGER
# ============================================================================

class DataManager:
    """Singleton data manager with enhanced caching and filtering."""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def initialize(self):
        if self._initialized:
            return self
        
        try:
            self.analyzer = LibraryAnalyzer(DATA_DIR)
            self.analyzer.load()
            
            # Store filter state
            self.exclude_liked = False
            self.exclude_monthly = False
            self.selected_playlist_ids = None
            
            self.analyzer.filter()  # Default: owned playlists
            
            # Build similarity engine
            self.similarity_engine = PlaylistSimilarityEngine(self.analyzer)
            self.similarity_engine.build(include_followed=True)
            
            # Pre-compute genre profiles
            self._update_profiles()
            
            # Pre-compute enriched dataframes for interactive charts
            self._build_enriched_data()
            
            self._initialized = True
            print("✅ Data loaded successfully")
        except Exception as e:
            print(f"❌ Error loading data: {e}")
            import traceback
            traceback.print_exc()
            self._initialized = False
        
        return self
    
    def apply_filters(self, exclude_liked=False, exclude_monthly=False, selected_ids=None):
        """Apply playlist filters and rebuild data."""
        self.exclude_liked = exclude_liked
        self.exclude_monthly = exclude_monthly
        self.selected_playlist_ids = selected_ids
        
        # Re-filter with new settings
        self.analyzer.filter(
            exclude_liked=exclude_liked,
            exclude_monthly=exclude_monthly,
        )
        
        # Apply playlist selection
        if selected_ids:
            self.analyzer.playlists = self.analyzer.playlists[
                self.analyzer.playlists['playlist_id'].isin(selected_ids)
            ]
            # Re-filter tracks
            playlist_ids = set(self.analyzer.playlists['playlist_id'])
            self.analyzer.playlist_tracks = self.analyzer.playlist_tracks[
                self.analyzer.playlist_tracks['playlist_id'].isin(playlist_ids)
            ]
            track_ids = set(self.analyzer.playlist_tracks['track_id'])
            self.analyzer.tracks = self.analyzer.tracks[
                self.analyzer.tracks['track_id'].isin(track_ids)
            ]
        
        self._update_profiles()
        self._build_enriched_data()
    
    def _update_profiles(self):
        """Update genre profiles for current filtered playlists."""
        self.genre_profiles = build_playlist_genre_profiles(
            self.analyzer.playlists,
            self.analyzer.playlist_tracks,
            self.analyzer.track_artists,
            self.analyzer.artists
        )
        
        # Aggregate genre counts
        self.total_genres = Counter()
        for genres in self.genre_profiles.values():
            self.total_genres.update(genres)
    
    def _build_enriched_data(self):
        """Build enriched dataframes for interactive analysis."""
        tracks = self.analyzer.tracks.copy()
        track_artists = self.analyzer.track_artists
        artists = self.analyzer.artists
        playlist_tracks = self.analyzer.playlist_tracks
        playlists = self.analyzer.playlists
        
        # Enrich tracks with primary artist info
        primary = track_artists[track_artists['position'] == 0].merge(
            artists[['artist_id', 'name', 'genres', 'popularity', 'followers']], 
            on='artist_id'
        ).rename(columns={
            'name': 'artist_name',
            'popularity': 'artist_popularity',
            'followers': 'artist_followers'
        })
        
        self.tracks_enriched = tracks.merge(
            primary[['track_id', 'artist_name', 'artist_id', 'genres', 'artist_popularity']], 
            on='track_id', 
            how='left'
        )
        
        # Parse release year
        self.tracks_enriched['year'] = pd.to_datetime(
            self.tracks_enriched['release_date'], errors='coerce'
        ).dt.year
        
        # Get core genre
        self.tracks_enriched['genre_list'] = self.tracks_enriched['genres'].apply(get_genres_list)
        self.tracks_enriched['core_genre'] = self.tracks_enriched['genre_list'].apply(canonical_core_genre)
        self.tracks_enriched['core_genre'] = self.tracks_enriched['core_genre'].fillna('Other')
        
        # Build track-to-playlist mapping
        track_playlists = playlist_tracks.merge(
            playlists[['playlist_id', 'name']], on='playlist_id'
        ).rename(columns={'name': 'playlist_name'})
        
        # Count playlists per track
        track_playlist_counts = track_playlists.groupby('track_id').agg({
            'playlist_id': 'count',
            'playlist_name': lambda x: list(x)[:5]  # First 5 playlists
        }).reset_index().rename(columns={'playlist_id': 'playlist_count'})
        
        self.tracks_enriched = self.tracks_enriched.merge(
            track_playlist_counts, on='track_id', how='left'
        )
        self.tracks_enriched['playlist_count'] = self.tracks_enriched['playlist_count'].fillna(1).astype(int)
    
    @property
    def is_loaded(self):
        return self._initialized

# Global data manager
dm = DataManager()

# ============================================================================
# CHART GENERATORS - Interactive & Crossfiltering
# ============================================================================

def create_genre_sunburst():
    """Create interactive sunburst chart for genre hierarchy."""
    if not dm.is_loaded:
        return go.Figure()
    
    df = dm.tracks_enriched.copy()
    
    # Build hierarchy: Core Genre -> Specific Genre
    data = []
    for _, row in df.iterrows():
        core = row['core_genre']
        for genre in row['genre_list'][:2]:  # Top 2 specific genres
            data.append({'core': core, 'genre': genre, 'track_id': row['track_id']})
    
    if not data:
        return go.Figure()
    
    genre_df = pd.DataFrame(data)
    counts = genre_df.groupby(['core', 'genre']).size().reset_index(name='count')
    
    # Only keep top genres per core
    top_genres = counts.groupby('core', group_keys=False).apply(
        lambda x: x.nlargest(8, 'count')
    ).reset_index(drop=True)
    
    fig = px.sunburst(
        top_genres,
        path=['core', 'genre'],
        values='count',
        color='core',
        color_discrete_sequence=CHART_COLORS,
    )
    
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Outfit', color=COLORS['text']),
        margin=dict(l=10, r=10, t=10, b=10),
        height=450,
    )
    fig.update_traces(
        textinfo='label+percent entry',
        hovertemplate='<b>%{label}</b><br>Tracks: %{value}<br>%{percentParent:.1%} of parent<extra></extra>'
    )
    
    return fig


def create_popularity_scatter(selected_genre=None, selected_artist=None, year_range=None):
    """Create interactive scatter plot of tracks by popularity vs year."""
    if not dm.is_loaded:
        return go.Figure()
    
    df = dm.tracks_enriched.copy()
    df = df.dropna(subset=['year', 'popularity'])
    
    # Apply filters
    if selected_genre and selected_genre != 'All':
        df = df[df['core_genre'] == selected_genre]
    
    if selected_artist:
        df = df[df['artist_name'] == selected_artist]
    
    if year_range:
        df = df[(df['year'] >= year_range[0]) & (df['year'] <= year_range[1])]
    
    # Sample for performance
    if len(df) > 500:
        df = df.sample(500, random_state=42)
    
    fig = px.scatter(
        df,
        x='year',
        y='popularity',
        size='playlist_count',
        color='core_genre',
        hover_name='name',
        hover_data={
            'artist_name': True,
            'year': True,
            'popularity': True,
            'playlist_count': True,
            'core_genre': False
        },
        color_discrete_sequence=CHART_COLORS,
        size_max=20,
    )
    
    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Outfit', color=COLORS['text']),
        margin=dict(l=40, r=20, t=20, b=40),
        xaxis=dict(
            title='Release Year',
            gridcolor='#222',
            showgrid=True,
            zeroline=False,
        ),
        yaxis=dict(
            title='Popularity',
            gridcolor='#222',
            showgrid=True,
            zeroline=False,
        ),
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1,
            bgcolor='rgba(0,0,0,0)'
        ),
        height=400,
        dragmode='select',  # Enable box/lasso selection
    )
    
    return fig


def create_artist_treemap(top_n=25):
    """Create interactive treemap of top artists by track count."""
    if not dm.is_loaded:
        return go.Figure()
    
    df = dm.tracks_enriched.copy()
    
    artist_stats = df.groupby(['artist_name', 'artist_id', 'core_genre']).agg({
        'track_id': 'count',
        'popularity': 'mean',
        'playlist_count': 'sum'
    }).reset_index().rename(columns={'track_id': 'track_count'})
    
    top = artist_stats.nlargest(top_n, 'track_count')
    
    fig = px.treemap(
        top,
        path=['core_genre', 'artist_name'],
        values='track_count',
        color='popularity',
        color_continuous_scale=['#1a1a2e', '#00ffcc', '#ff00aa'],
        hover_data={'track_count': True, 'popularity': ':.0f'},
    )
    
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Outfit', color=COLORS['text']),
        margin=dict(l=10, r=10, t=10, b=10),
        height=450,
        coloraxis_colorbar=dict(
            title='Popularity',
            tickfont=dict(color=COLORS['text']),
            titlefont=dict(color=COLORS['text']),
        )
    )
    
    fig.update_traces(
        hovertemplate='<b>%{label}</b><br>Tracks: %{value}<br>Avg Popularity: %{color:.0f}<extra></extra>',
        textinfo='label+value',
    )
    
    return fig


def create_timeline_area(selected_genre=None):
    """Create stacked area chart of tracks over time by genre."""
    if not dm.is_loaded:
        return go.Figure()
    
    df = dm.tracks_enriched.copy()
    df = df.dropna(subset=['year'])
    df = df[(df['year'] >= 1970) & (df['year'] <= 2025)]
    
    # Group by year and genre
    year_genre = df.groupby(['year', 'core_genre']).size().reset_index(name='count')
    
    # Pivot for stacked area
    pivot = year_genre.pivot(index='year', columns='core_genre', values='count').fillna(0)
    
    fig = go.Figure()
    
    genres = pivot.columns.tolist()
    for i, genre in enumerate(genres):
        opacity = 1.0 if (selected_genre is None or genre == selected_genre) else 0.2
        fig.add_trace(go.Scatter(
            x=pivot.index,
            y=pivot[genre],
            name=genre,
            mode='lines',
            stackgroup='one',
            line=dict(width=0.5, color=CHART_COLORS[i % len(CHART_COLORS)]),
            fillcolor=CHART_COLORS[i % len(CHART_COLORS)] if opacity == 1.0 else f'rgba(100,100,100,0.1)',
            opacity=opacity,
            hovertemplate=f'<b>{genre}</b><br>Year: %{{x}}<br>Tracks: %{{y}}<extra></extra>'
        ))
    
    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Outfit', color=COLORS['text']),
        margin=dict(l=40, r=20, t=20, b=40),
        xaxis=dict(
            title='Year',
            gridcolor='#222',
            showgrid=True,
            rangeslider=dict(visible=True, bgcolor='#1a1a1a'),
        ),
        yaxis=dict(
            title='Tracks',
            gridcolor='#222',
            showgrid=True,
        ),
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='center',
            x=0.5,
            bgcolor='rgba(0,0,0,0)'
        ),
        height=450,
        hovermode='x unified',
    )
    
    return fig


def create_genre_radar(playlist_id=None):
    """Create radar chart for genre profile comparison."""
    if not dm.is_loaded:
        return go.Figure()
    
    # Get overall library profile
    total = sum(dm.total_genres.values())
    top_genres = dm.total_genres.most_common(10)
    
    if not top_genres:
        return go.Figure()
    
    categories = [g[0] for g in top_genres]
    library_values = [g[1] / total * 100 for g in top_genres]
    
    fig = go.Figure()
    
    # Library profile
    fig.add_trace(go.Scatterpolar(
        r=library_values + [library_values[0]],  # Close the shape
        theta=categories + [categories[0]],
        fill='toself',
        fillcolor='rgba(0,255,204,0.2)',
        line=dict(color=COLORS['primary'], width=2),
        name='Your Library',
    ))
    
    # Add playlist profile if selected
    if playlist_id and playlist_id in dm.genre_profiles:
        playlist_genres = dm.genre_profiles[playlist_id]
        playlist_total = sum(playlist_genres.values()) or 1
        playlist_values = [playlist_genres.get(g, 0) / playlist_total * 100 for g in categories]
        
        fig.add_trace(go.Scatterpolar(
            r=playlist_values + [playlist_values[0]],
            theta=categories + [categories[0]],
            fill='toself',
            fillcolor='rgba(255,0,170,0.2)',
            line=dict(color=COLORS['secondary'], width=2),
            name='Selected Playlist',
        ))
    
    fig.update_layout(
        polar=dict(
            bgcolor='rgba(0,0,0,0)',
            radialaxis=dict(
                visible=True,
                range=[0, max(library_values) * 1.2],
                gridcolor='#333',
                tickfont=dict(color=COLORS['muted']),
            ),
            angularaxis=dict(
                gridcolor='#333',
                tickfont=dict(color=COLORS['text'], size=11),
            ),
        ),
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Outfit', color=COLORS['text']),
        margin=dict(l=60, r=60, t=40, b=40),
        height=400,
        showlegend=True,
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=-0.2,
            xanchor='center',
            x=0.5,
        ),
    )
    
    return fig


def create_popularity_distribution(selected_genre=None):
    """Create interactive histogram of popularity."""
    if not dm.is_loaded:
        return go.Figure()
    
    df = dm.tracks_enriched.copy()
    
    if selected_genre and selected_genre != 'All':
        df = df[df['core_genre'] == selected_genre]
    
    fig = go.Figure()
    
    # Histogram
    fig.add_trace(go.Histogram(
        x=df['popularity'],
        nbinsx=40,
        marker=dict(
            color=COLORS['primary'],
            line=dict(width=0),
        ),
        opacity=0.8,
        name='Distribution',
        hovertemplate='Popularity: %{x}<br>Tracks: %{y}<extra></extra>'
    ))
    
    # Add percentile lines
    p25 = df['popularity'].quantile(0.25)
    p50 = df['popularity'].quantile(0.50)
    p75 = df['popularity'].quantile(0.75)
    
    for p, label, color in [(p25, '25th', '#666'), (p50, 'Median', COLORS['secondary']), (p75, '75th', '#666')]:
        fig.add_vline(
            x=p, 
            line_dash='dash', 
            line_color=color,
            annotation_text=f'{label}: {p:.0f}',
            annotation_position='top',
            annotation_font_color=color,
        )
    
    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Outfit', color=COLORS['text']),
        margin=dict(l=40, r=20, t=30, b=40),
        xaxis=dict(
            title='Popularity Score',
            gridcolor='#222',
            range=[0, 100],
        ),
        yaxis=dict(
            title='Track Count',
            gridcolor='#222',
        ),
        height=300,
        bargap=0.1,
    )
    
    return fig


def create_top_artists_bar(selected_genre=None, top_n=15):
    """Create horizontal bar chart of top artists."""
    if not dm.is_loaded:
        return go.Figure()
    
    df = dm.tracks_enriched.copy()
    
    if selected_genre and selected_genre != 'All':
        df = df[df['core_genre'] == selected_genre]
    
    artist_counts = df.groupby('artist_name').agg({
        'track_id': 'count',
        'popularity': 'mean',
        'core_genre': 'first'
    }).reset_index().rename(columns={'track_id': 'count'})
    
    top = artist_counts.nlargest(top_n, 'count')
    
    # Reverse for horizontal bar
    top = top.iloc[::-1]
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=top['count'],
        y=top['artist_name'],
        orientation='h',
        marker=dict(
            color=top['popularity'],
            colorscale=[[0, '#1a1a2e'], [0.5, COLORS['primary']], [1, COLORS['secondary']]],
            line=dict(width=0),
        ),
        text=top['count'],
        textposition='outside',
        textfont=dict(color=COLORS['text'], size=11),
        hovertemplate='<b>%{y}</b><br>Tracks: %{x}<br>Avg Popularity: %{marker.color:.0f}<extra></extra>',
        customdata=top['artist_name'],  # For click events
    ))
    
    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Outfit', color=COLORS['text']),
        margin=dict(l=10, r=60, t=20, b=20),
        xaxis=dict(
            title='Tracks',
            gridcolor='#222',
            showgrid=True,
        ),
        yaxis=dict(
            title='',
            tickfont=dict(size=12),
        ),
        height=450,
    )
    
    return fig


def create_playlist_heatmap():
    """Create heatmap of playlist genre distributions."""
    if not dm.is_loaded:
        return go.Figure()
    
    playlists = dm.analyzer.playlists.nlargest(15, 'track_count')
    
    # Get core genre distribution for each playlist
    core_genres = ['Hip-Hop', 'R&B/Soul', 'Electronic', 'Rock', 'Pop', 'Indie', 'Other']
    
    data = []
    for _, row in playlists.iterrows():
        pid = row['playlist_id']
        genres = dm.genre_profiles.get(pid, Counter())
        total = sum(genres.values()) or 1
        
        # Map to core genres
        core_counts = Counter()
        for genre, count in genres.items():
            core = canonical_core_genre([genre]) or 'Other'
            core_counts[core] += count
        
        row_data = {
            'playlist': row['name'][:25],
            **{g: core_counts.get(g, 0) / total * 100 for g in core_genres}
        }
        data.append(row_data)
    
    df = pd.DataFrame(data)
    
    fig = go.Figure(go.Heatmap(
        z=df[core_genres].values,
        x=core_genres,
        y=df['playlist'],
        colorscale=[[0, '#0d0d0d'], [0.5, '#00ffcc'], [1, '#ff00aa']],
        hovertemplate='<b>%{y}</b><br>%{x}: %{z:.1f}%<extra></extra>',
    ))
    
    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Outfit', color=COLORS['text']),
        margin=dict(l=10, r=20, t=20, b=40),
        xaxis=dict(
            title='',
            tickangle=45,
        ),
        yaxis=dict(
            title='',
        ),
        height=450,
    )
    
    return fig


def create_duration_distribution():
    """Create track duration distribution chart."""
    if not dm.is_loaded:
        return go.Figure()
    
    df = dm.tracks_enriched.copy()
    df['duration_min'] = df['duration_ms'] / 60000
    
    fig = go.Figure()
    
    fig.add_trace(go.Histogram(
        x=df['duration_min'],
        nbinsx=50,
        marker=dict(color=COLORS['tertiary'], line=dict(width=0)),
        opacity=0.8,
        hovertemplate='Duration: %{x:.1f} min<br>Tracks: %{y}<extra></extra>'
    ))
    
    median = df['duration_min'].median()
    fig.add_vline(x=median, line_dash='dash', line_color=COLORS['secondary'],
                  annotation_text=f'Median: {median:.1f} min')
    
    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Outfit', color=COLORS['text']),
        margin=dict(l=40, r=20, t=30, b=40),
        xaxis=dict(title='Duration (minutes)', gridcolor='#222', range=[0, 10]),
        yaxis=dict(title='Track Count', gridcolor='#222'),
        height=300,
    )
    
    return fig


def create_decade_breakdown():
    """Create decade breakdown bar chart."""
    if not dm.is_loaded:
        return go.Figure()
    
    df = dm.tracks_enriched.copy()
    df['decade'] = (df['year'] // 10 * 10).astype('Int64')
    decade_counts = df['decade'].dropna().value_counts().sort_index()
    decade_counts = decade_counts[(decade_counts.index >= 1960) & (decade_counts.index <= 2020)]
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=[f"{int(d)}s" for d in decade_counts.index],
        y=decade_counts.values,
        marker=dict(
            color=decade_counts.values,
            colorscale=[[0, '#1a1a2e'], [0.5, COLORS['primary']], [1, COLORS['secondary']]],
            line=dict(width=0),
        ),
        text=[f"{v:,}" for v in decade_counts.values],
        textposition='outside',
        textfont=dict(color=COLORS['text']),
        hovertemplate='<b>%{x}</b><br>Tracks: %{y:,}<extra></extra>'
    ))
    
    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Outfit', color=COLORS['text']),
        margin=dict(l=40, r=20, t=20, b=40),
        xaxis=dict(title='Decade', gridcolor='#222'),
        yaxis=dict(title='Tracks', gridcolor='#222'),
        height=300,
    )
    
    return fig


def create_playlist_pca():
    """Create PCA visualization of playlist clusters."""
    if not dm.is_loaded or len(dm.genre_profiles) < 3:
        return go.Figure()
    
    from sklearn.decomposition import PCA
    from sklearn.cluster import AgglomerativeClustering
    
    # Build feature matrix
    playlists = dm.analyzer.playlists
    all_genres = sorted(list(set(g for genres in dm.genre_profiles.values() for g in genres.keys())))
    
    if len(all_genres) < 2:
        return go.Figure()
    
    playlist_ids = []
    vectors = []
    
    for pid in dm.genre_profiles:
        genres = dm.genre_profiles[pid]
        total = sum(genres.values()) or 1
        vec = [genres.get(g, 0) / total for g in all_genres]
        if sum(vec) > 0:
            playlist_ids.append(pid)
            vectors.append(vec)
    
    if len(vectors) < 3:
        return go.Figure()
    
    X = np.array(vectors)
    
    # Cluster
    n_clusters = min(5, len(X))
    clustering = AgglomerativeClustering(n_clusters=n_clusters, metric='cosine', linkage='average')
    labels = clustering.fit_predict(X)
    
    # PCA
    n_components = min(2, X.shape[1])
    pca = PCA(n_components=n_components)
    X_2d = pca.fit_transform(X)
    
    # Build dataframe
    playlist_names = playlists.set_index('playlist_id')['name'].to_dict()
    track_counts = playlists.set_index('playlist_id')['track_count'].to_dict()
    
    df = pd.DataFrame({
        'x': X_2d[:, 0],
        'y': X_2d[:, 1] if n_components > 1 else 0,
        'name': [playlist_names.get(pid, 'Unknown')[:20] for pid in playlist_ids],
        'cluster': labels,
        'tracks': [track_counts.get(pid, 0) for pid in playlist_ids],
    })
    
    fig = px.scatter(
        df, x='x', y='y',
        color='cluster',
        size='tracks',
        hover_name='name',
        color_discrete_sequence=CHART_COLORS,
        size_max=30,
    )
    
    # Add labels
    for _, row in df.iterrows():
        fig.add_annotation(
            x=row['x'], y=row['y'],
            text=row['name'],
            showarrow=False,
            font=dict(size=9, color=COLORS['text']),
            yshift=15,
        )
    
    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Outfit', color=COLORS['text']),
        margin=dict(l=40, r=40, t=40, b=40),
        xaxis=dict(
            title=f'PC1 ({pca.explained_variance_ratio_[0]*100:.1f}%)',
            gridcolor='#222',
            zeroline=False,
        ),
        yaxis=dict(
            title=f'PC2 ({pca.explained_variance_ratio_[1]*100:.1f}%)' if n_components > 1 else '',
            gridcolor='#222',
            zeroline=False,
        ),
        height=500,
        showlegend=False,
    )
    
    return fig


# ============================================================================
# LAYOUT COMPONENTS
# ============================================================================

def create_sidebar():
    """Create the sidebar navigation."""
    return html.Div([
        # Logo
        html.Div([
            html.A([
                html.Div("🎵", className="sidebar-logo-icon"),
                html.Span("Spotim8", className="sidebar-logo-text"),
            ], className="sidebar-logo", href="/"),
        ], className="sidebar-header"),
        
        # Navigation
        html.Nav([
            html.Div([
                html.Div("EXPLORE", className="nav-section-title"),
                dcc.Link([
                    html.Span("⚡", className="nav-item-icon"),
                    "Dashboard"
                ], href="/", className="nav-item"),
                dcc.Link([
                    html.Span("🎯", className="nav-item-icon"),
                    "Deep Dive"
                ], href="/explore", className="nav-item"),
                dcc.Link([
                    html.Span("📂", className="nav-item-icon"),
                    "Playlists"
                ], href="/playlists", className="nav-item"),
                dcc.Link([
                    html.Span("🗺️", className="nav-item-icon"),
                    "Clusters"
                ], href="/clusters", className="nav-item"),
            ], className="nav-section"),
            
            html.Div([
                html.Div("DISCOVER", className="nav-section-title"),
                dcc.Link([
                    html.Span("🔗", className="nav-item-icon"),
                    "Similar Playlists"
                ], href="/discover", className="nav-item"),
                dcc.Link([
                    html.Span("💎", className="nav-item-icon"),
                    "Hidden Gems"
                ], href="/gems", className="nav-item"),
            ], className="nav-section"),
            
            html.Div([
                html.Div("SETTINGS", className="nav-section-title"),
                dcc.Link([
                    html.Span("⚙️", className="nav-item-icon"),
                    "Settings"
                ], href="/settings", className="nav-item"),
            ], className="nav-section"),
        ], className="sidebar-nav"),
        
        # Footer
        html.Div([
            html.Div("Spotim8 • Made with 🎵", className="sidebar-footer-text"),
        ], className="sidebar-footer"),
    ], className="sidebar")


def create_filter_bar():
    """Create the global filter bar for playlist selection."""
    if not dm.is_loaded:
        return html.Div()
    
    playlists = dm.analyzer.playlists_all[dm.analyzer.playlists_all['is_owned'] == True]
    options = [{'label': row['name'], 'value': row['playlist_id']} 
               for _, row in playlists.iterrows()]
    
    return html.Div([
        html.Div([
            dcc.Dropdown(
                id='global-playlist-filter',
                options=options,
                multi=True,
                placeholder="Select playlists to analyze (leave empty for all)...",
                className="filter-dropdown",
            ),
        ], className="filter-dropdown-container"),
        
        html.Div([
            html.Button([
                html.Span("❤️"),
                html.Span("Exclude Liked", className="btn-text"),
            ], id='btn-exclude-liked', className="filter-btn"),
            html.Button([
                html.Span("📅"),
                html.Span("Exclude Monthly", className="btn-text"),
            ], id='btn-exclude-monthly', className="filter-btn"),
        ], className="filter-toggles"),
        
        html.Div(id='global-filter-stats', className="filter-stats"),
    ], className="filter-bar")


def create_stat_card(icon, value, label, accent=False):
    """Create a statistics card with proper structure."""
    class_name = "stat-card accent" if accent else "stat-card"
    return html.Div([
        html.Span(icon, className="stat-icon"),
        html.Span(str(value), className="stat-value"),
        html.Span(str(label), className="stat-label"),
    ], className=class_name)


def create_card(title, content, icon="", className=""):
    """Create a content card with proper icon and title handling."""
    title_content = []
    if icon:
        title_content.append(html.Span(icon, className="card-icon"))
    title_content.append(html.Span(title, className="card-title-text"))
    
    return html.Div([
        html.Div([
            html.Div(title_content, className="card-title"),
        ], className="card-header"),
        html.Div(content, className="card-body"),
    ], className=f"card {className}")


# ============================================================================
# PAGE LAYOUTS
# ============================================================================

def page_dashboard():
    """Main interactive dashboard."""
    if not dm.is_loaded:
        return html.Div("Loading...", className="loading")
    
    stats = dm.analyzer.stats()
    genres = list(set(dm.tracks_enriched['core_genre'].dropna()))
    genres = ['All'] + sorted(genres)
    
    return html.Div([
        # Genre Filter
        html.Div([
            html.Span("Filter by Genre:", className="filter-label"),
            dcc.Dropdown(
                id='genre-filter',
                options=[{'label': g, 'value': g} for g in genres],
                value='All',
                clearable=False,
                className="genre-dropdown",
            ),
            html.Div(id='filter-stats', className="filter-stats"),
        ], className="filter-row"),
        
        # Stats Grid
        html.Div([
            create_stat_card("🎵", f"{stats.get('total_tracks', 0):,}", "Tracks"),
            create_stat_card("🎤", f"{stats.get('total_artists', 0):,}", "Artists"),
            create_stat_card("📂", f"{stats.get('total_playlists', 0):,}", "Playlists"),
            create_stat_card("⏱️", f"{stats.get('total_hours', 0):.0f}h", "Duration"),
            create_stat_card("📈", f"{stats.get('avg_popularity', 0):.0f}", "Avg Popularity", accent=True),
        ], className="stats-grid"),
        
        # Row 1: Scatter + Artists
        html.Div([
            create_card("Track Explorer", html.Div([
                html.P("🔍 Drag to select tracks • Click legend to toggle genres", className="chart-hint"),
                dcc.Graph(
                    id='scatter-chart',
                    figure=create_popularity_scatter(),
                    config={'displayModeBar': True, 'modeBarButtonsToRemove': ['pan2d', 'lasso2d', 'autoScale2d']},
                ),
            ]), "📊"),
            create_card("Top Artists", html.Div([
                html.P("🎯 Click bar to filter by artist", className="chart-hint"),
                dcc.Graph(
                    id='artists-chart',
                    figure=create_top_artists_bar(),
                    config={'displayModeBar': False},
                ),
            ]), "🎤"),
        ], className="charts-row"),
        
        # Row 2: Timeline + Popularity
        html.Div([
            create_card("Timeline by Genre", html.Div([
                html.P("📅 Use range slider to zoom • Click legend to isolate genre", className="chart-hint"),
                dcc.Graph(
                    id='timeline-chart',
                    figure=create_timeline_area(),
                    config={'displayModeBar': False},
                ),
            ]), "📈", className="wide"),
        ], className="charts-row single"),
        
        # Row 3: Popularity + Sunburst
        html.Div([
            create_card("Popularity Distribution", html.Div([
                dcc.Graph(
                    id='popularity-chart',
                    figure=create_popularity_distribution(),
                    config={'displayModeBar': False},
                ),
            ]), "📊"),
            create_card("Genre Breakdown", html.Div([
                html.P("🎯 Click to drill down into genres", className="chart-hint"),
                dcc.Graph(
                    id='sunburst-chart',
                    figure=create_genre_sunburst(),
                    config={'displayModeBar': False},
                ),
            ]), "🎸"),
        ], className="charts-row"),
        
        # Row 4: Duration + Decades
        html.Div([
            create_card("Track Duration", html.Div([
                dcc.Graph(
                    id='duration-chart',
                    figure=create_duration_distribution(),
                    config={'displayModeBar': False},
                ),
            ]), "⏱️"),
            create_card("Decades Breakdown", html.Div([
                dcc.Graph(
                    id='decade-chart',
                    figure=create_decade_breakdown(),
                    config={'displayModeBar': False},
                ),
            ]), "📅"),
        ], className="charts-row"),
        
        # Selected tracks display
        html.Div(id='selected-tracks-panel', className="selection-panel"),
    ])


def page_explore():
    """Deep dive exploration page."""
    if not dm.is_loaded:
        return html.Div("Loading...", className="loading")
    
    return html.Div([
        html.Div([
            create_card("Artist Landscape", html.Div([
                html.P("🎯 Click to explore an artist's tracks", className="chart-hint"),
                dcc.Graph(
                    id='treemap-chart',
                    figure=create_artist_treemap(),
                    config={'displayModeBar': False},
                ),
            ]), "🌳", className="wide"),
        ], className="charts-row single"),
        
        html.Div([
            create_card("Playlist DNA", html.Div([
                html.P("Compare genre composition across playlists", className="chart-hint"),
                dcc.Graph(
                    id='heatmap-chart',
                    figure=create_playlist_heatmap(),
                    config={'displayModeBar': False},
                ),
            ]), "🧬"),
            create_card("Your Taste Profile", html.Div([
                html.Label("Compare with playlist:", className="input-label"),
                dcc.Dropdown(
                    id='radar-playlist-select',
                    options=[{'label': row['name'], 'value': row['playlist_id']} 
                             for _, row in dm.analyzer.playlists.iterrows()],
                    placeholder="Select a playlist...",
                    className="playlist-dropdown",
                ),
                dcc.Graph(
                    id='radar-chart',
                    figure=create_genre_radar(),
                    config={'displayModeBar': False},
                ),
            ]), "🎯"),
        ], className="charts-row"),
    ])


def page_playlists():
    """Playlist analysis page."""
    if not dm.is_loaded:
        return html.Div("Loading...", className="loading")
    
    playlists = dm.analyzer.playlists.sort_values('track_count', ascending=False)
    
    return html.Div([
        create_card("Playlist Analysis", html.Div([
            html.Div([
                html.Label("Select a playlist:", className="input-label"),
                dcc.Dropdown(
                    id='playlist-select',
                    options=[{'label': f"{row['name']} ({row['track_count']} tracks)", 'value': row['playlist_id']} 
                             for _, row in playlists.iterrows()],
                    value=playlists['playlist_id'].iloc[0] if len(playlists) > 0 else None,
                    placeholder="Choose a playlist...",
                    className="playlist-dropdown",
                ),
            ], className="input-group"),
            html.Div(id='playlist-details'),
        ]), "📂"),
    ])


def page_discover():
    """Discover similar playlists page."""
    if not dm.is_loaded:
        return html.Div("Loading...", className="loading")
    
    playlists = dm.analyzer.playlists.sort_values('track_count', ascending=False)
    
    return html.Div([
        create_card("Find Similar Playlists", html.Div([
            html.Div([
                html.Label("Select your playlist:", className="input-label"),
                dcc.Dropdown(
                    id='source-playlist',
                    options=[{'label': f"{row['name']} ({row['track_count']} tracks)", 'value': row['playlist_id']} 
                             for _, row in playlists.iterrows()],
                    placeholder="Choose a playlist to find similar ones...",
                    className="playlist-dropdown",
                ),
            ], className="input-group"),
            
            html.Div([
                html.Button("Followed", id='btn-followed', className="filter-btn active"),
                html.Button("Owned", id='btn-owned', className="filter-btn"),
                html.Button("All", id='btn-all', className="filter-btn"),
            ], className="filter-buttons"),
            
            html.Div(id='similar-results'),
        ]), "🔗"),
    ])


def page_gems():
    """Hidden gems page."""
    if not dm.is_loaded:
        return html.Div("Loading...", className="loading")
    
    df = dm.tracks_enriched.copy()
    gems = df[(df['popularity'] <= 30) & (df['popularity'] > 0)].nlargest(30, 'popularity')
    
    # Create scatter for gems
    fig = px.scatter(
        gems,
        x='year',
        y='popularity',
        size='playlist_count',
        color='core_genre',
        hover_name='name',
        hover_data={'artist_name': True, 'popularity': True},
        color_discrete_sequence=CHART_COLORS,
        size_max=20,
    )
    
    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Outfit', color=COLORS['text']),
        margin=dict(l=40, r=20, t=20, b=40),
        xaxis=dict(title='Release Year', gridcolor='#222'),
        yaxis=dict(title='Popularity', gridcolor='#222'),
        height=400,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5),
    )
    
    table_rows = [
        html.Tr([
            html.Td(row['name'][:40] + ('...' if len(str(row['name'])) > 40 else '')),
            html.Td(row['artist_name'] if pd.notna(row['artist_name']) else '-'),
            html.Td(f"{row['popularity']}", className="popularity-cell"),
            html.Td(row['core_genre']),
        ]) for _, row in gems.iterrows()
    ]
    
    return html.Div([
        create_card("Hidden Gems Explorer", html.Div([
            html.P("Low-popularity tracks that deserve more attention.", className="card-description"),
            dcc.Graph(figure=fig, config={'displayModeBar': False}),
        ]), "💎"),
        
        create_card("Gem Collection", html.Table([
            html.Thead(html.Tr([
                html.Th("Track"),
                html.Th("Artist"),
                html.Th("Popularity"),
                html.Th("Genre"),
            ])),
            html.Tbody(table_rows),
        ], className="data-table"), "📋"),
    ])


def page_clusters():
    """Playlist clustering and PCA visualization."""
    if not dm.is_loaded:
        return html.Div("Loading...", className="loading")
    
    return html.Div([
        html.Div([
            create_card("Playlist Clusters (PCA)", html.Div([
                html.P("Playlists grouped by genre similarity. Size = track count.", className="card-description"),
                dcc.Graph(
                    id='pca-chart',
                    figure=create_playlist_pca(),
                    config={'displayModeBar': False},
                ),
            ]), "🗺️", className="wide"),
        ], className="charts-row single"),
        
        html.Div([
            create_card("Playlist DNA Heatmap", html.Div([
                html.P("Genre distribution across your top playlists.", className="card-description"),
                dcc.Graph(
                    figure=create_playlist_heatmap(),
                    config={'displayModeBar': False},
                ),
            ]), "🧬"),
            create_card("Taste Profile", html.Div([
                dcc.Graph(
                    figure=create_genre_radar(),
                    config={'displayModeBar': False},
                ),
            ]), "🎯"),
        ], className="charts-row"),
    ])




def page_settings():
    """Settings page."""
    return html.Div([
        create_card("Data Settings", html.Div([
            html.Div([
                html.Label("Data Directory:", className="input-label"),
                html.Code(str(DATA_DIR), className="code-block"),
            ], className="setting-row"),
            
            html.Div([
                html.Label("Status:", className="input-label"),
                html.Span("✅ Data loaded" if dm.is_loaded else "❌ Not loaded", 
                         className="status-badge"),
            ], className="setting-row"),
            
            html.Div([
                html.Button("Reload Data", id='reload-data-btn', className="btn-secondary"),
            ], className="button-row"),
            
            html.Div(id='settings-output', className="tool-output"),
        ]), "⚙️"),
        
        create_card("Library Statistics", html.Div([
            html.Div([
                html.Div([
                    html.Span("Total Playlists", className="stat-label"),
                    html.Span(f"{len(dm.analyzer.playlists_all):,}" if dm.is_loaded else "-", className="stat-value"),
                ], className="stat-row"),
                html.Div([
                    html.Span("Owned Playlists", className="stat-label"),
                    html.Span(f"{len(dm.analyzer.playlists):,}" if dm.is_loaded else "-", className="stat-value"),
                ], className="stat-row"),
                html.Div([
                    html.Span("Followed Playlists", className="stat-label"),
                    html.Span(f"{len(dm.analyzer.playlists_all) - len(dm.analyzer.playlists):,}" if dm.is_loaded else "-", className="stat-value"),
                ], className="stat-row"),
                html.Div([
                    html.Span("Total Tracks", className="stat-label"),
                    html.Span(f"{len(dm.analyzer.tracks_all):,}" if dm.is_loaded else "-", className="stat-value"),
                ], className="stat-row"),
                html.Div([
                    html.Span("Monthly Playlists Detected", className="stat-label"),
                    html.Span(f"{len(dm.analyzer.monthly_playlist_ids):,}" if dm.is_loaded else "-", className="stat-value"),
                ], className="stat-row"),
            ], className="stats-list"),
        ]), "📊") if dm.is_loaded else html.Div(),
    ])


def page_loading():
    """Loading/login page."""
    return html.Div([
        html.Div([
            html.Div("🎵", className="login-logo"),
            html.H1("Spotim8", className="login-title"),
            html.P("Interactive visualization of your music library", className="login-subtitle"),
            html.Button("Load Library Data", id='load-data-btn', className="btn-primary"),
            html.Div(id='login-status'),
        ], className="login-card"),
    ], className="login-container")


# ============================================================================
# MAIN LAYOUT
# ============================================================================

app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    dcc.Store(id='selected-artist', data=None),
    dcc.Store(id='selected-tracks', data=[]),
    dcc.Store(id='discover-mode', data='followed'),
    dcc.Store(id='filter-state', data={'exclude_liked': False, 'exclude_monthly': False, 'selected': None}),
    html.Div(id='app-container'),
])


# ============================================================================
# CALLBACKS
# ============================================================================

@callback(
    Output('app-container', 'children'),
    Input('url', 'pathname'),
)
def render_page(pathname):
    """Render the main layout based on route."""
    if not dm.is_loaded:
        dm.initialize()
    
    if not dm.is_loaded:
        return page_loading()
    
    routes = {
        '/': page_dashboard,
        '/explore': page_explore,
        '/playlists': page_playlists,
        '/clusters': page_clusters,
        '/discover': page_discover,
        '/gems': page_gems,
        '/settings': page_settings,
    }
    
    page_func = routes.get(pathname, page_dashboard)
    page_titles = {
        '/': ('Dashboard', 'Your library at a glance'),
        '/explore': ('Deep Dive', 'Explore your music landscape'),
        '/playlists': ('Playlists', 'Analyze individual playlists'),
        '/clusters': ('Clusters', 'Playlist similarity visualization'),
        '/discover': ('Discover', 'Find playlists with similar vibes'),
        '/gems': ('Hidden Gems', 'Underrated tracks in your library'),
        '/settings': ('Settings', 'Configure the dashboard'),
    }
    
    title, subtitle = page_titles.get(pathname, page_titles['/'])
    
    # Show filter bar on analysis pages
    show_filter = pathname in ['/', '/explore', '/playlists', '/clusters']
    
    return html.Div([
        create_sidebar(),
        html.Div([
            html.Div([
                html.H1(title, className="page-title"),
                html.P(subtitle, className="page-subtitle"),
            ], className="page-header"),
            create_filter_bar() if show_filter else html.Div(),
            html.Div(page_func(), className="page-content"),
        ], className="main-content"),
    ], className="app-layout")


@callback(
    Output('scatter-chart', 'figure'),
    Output('artists-chart', 'figure'),
    Output('popularity-chart', 'figure'),
    Output('timeline-chart', 'figure'),
    Output('filter-stats', 'children'),
    Input('genre-filter', 'value'),
    Input('artists-chart', 'clickData'),
    prevent_initial_call=True,
)
def crossfilter_charts(selected_genre, click_data):
    """Update all charts based on crossfilter selections."""
    if not dm.is_loaded:
        raise PreventUpdate
    
    # Get selected artist from click
    selected_artist = None
    if click_data and 'points' in click_data:
        try:
            selected_artist = click_data['points'][0].get('customdata')
        except:
            pass
    
    genre = selected_genre if selected_genre != 'All' else None
    
    # Update all charts
    scatter = create_popularity_scatter(selected_genre=genre, selected_artist=selected_artist)
    artists = create_top_artists_bar(selected_genre=genre)
    popularity = create_popularity_distribution(selected_genre=genre)
    timeline = create_timeline_area(selected_genre=genre)
    
    # Calculate filtered stats
    df = dm.tracks_enriched
    if genre:
        df = df[df['core_genre'] == genre]
    
    stats_text = f"{len(df):,} tracks"
    if selected_artist:
        stats_text += f" by {selected_artist}"
    
    return scatter, artists, popularity, timeline, stats_text


@callback(
    Output('selected-tracks-panel', 'children'),
    Input('scatter-chart', 'selectedData'),
)
def show_selected_tracks(selected_data):
    """Show details for selected tracks from scatter plot."""
    if not selected_data or 'points' not in selected_data:
        return None
    
    points = selected_data['points']
    if not points:
        return None
    
    track_names = [p.get('hovertext', p.get('text', 'Unknown')) for p in points[:10]]
    
    return html.Div([
        html.H4(f"🎵 Selected Tracks ({len(points)})", className="panel-title"),
        html.Ul([html.Li(name) for name in track_names], className="track-list"),
        html.P(f"... and {len(points) - 10} more" if len(points) > 10 else "", className="more-text"),
    ], className="selection-content")


@callback(
    Output('radar-chart', 'figure'),
    Input('radar-playlist-select', 'value'),
)
def update_radar(playlist_id):
    """Update radar chart when playlist is selected."""
    return create_genre_radar(playlist_id)


@callback(
    Output('playlist-details', 'children'),
    Input('playlist-select', 'value'),
)
def update_playlist_details(playlist_id):
    """Show details for selected playlist."""
    if not playlist_id or not dm.is_loaded:
        return html.Div("Select a playlist to see details.", className="empty-state")
    
    playlists = dm.analyzer.playlists
    playlist = playlists[playlists['playlist_id'] == playlist_id]
    
    if len(playlist) == 0:
        return html.Div("Playlist not found.", className="empty-state")
    
    info = playlist.iloc[0]
    
    # Get genre breakdown
    genres = dm.genre_profiles.get(playlist_id, Counter())
    total = sum(genres.values()) or 1
    top_genres = genres.most_common(8)
    
    genre_bars = []
    for genre, count in top_genres:
        pct = count / total * 100
        genre_bars.append(html.Div([
            html.Div([
                html.Span(genre, className="genre-name"),
                html.Span(f"{pct:.1f}%", className="genre-pct"),
            ], className="genre-bar-header"),
            html.Div([
                html.Div(className="genre-bar-fill", style={'width': f'{pct}%'}),
            ], className="genre-bar-bg"),
        ], className="genre-bar-row"))
    
    return html.Div([
        html.Div([
            html.H3(info['name'], className="playlist-name"),
            html.P(f"{info['track_count']} tracks", className="playlist-meta"),
        ], className="playlist-header"),
        html.Div([
            html.H4("Genre Composition", className="section-title"),
            html.Div(genre_bars, className="genre-bars"),
        ], className="playlist-genres"),
        html.Div([
            dcc.Graph(
                figure=create_genre_radar(playlist_id),
                config={'displayModeBar': False},
            ),
        ], className="playlist-radar"),
    ], className="playlist-detail-content")


@callback(
    Output('similar-results', 'children'),
    Output('btn-followed', 'className'),
    Output('btn-owned', 'className'),
    Output('btn-all', 'className'),
    Output('discover-mode', 'data'),
    Input('source-playlist', 'value'),
    Input('btn-followed', 'n_clicks'),
    Input('btn-owned', 'n_clicks'),
    Input('btn-all', 'n_clicks'),
    State('discover-mode', 'data'),
)
def find_similar_playlists(playlist_id, n1, n2, n3, mode):
    """Find similar playlists."""
    triggered = ctx.triggered_id
    
    if triggered == 'btn-followed':
        mode = 'followed'
    elif triggered == 'btn-owned':
        mode = 'owned'
    elif triggered == 'btn-all':
        mode = 'all'
    
    btn_classes = {
        'followed': 'filter-btn active' if mode == 'followed' else 'filter-btn',
        'owned': 'filter-btn active' if mode == 'owned' else 'filter-btn',
        'all': 'filter-btn active' if mode == 'all' else 'filter-btn',
    }
    
    if not playlist_id or not dm.is_loaded:
        empty = html.Div([
            html.Div("🔍", className="empty-icon"),
            html.P("Select a playlist to discover similar ones", className="empty-text"),
        ], className="empty-state")
        return empty, btn_classes['followed'], btn_classes['owned'], btn_classes['all'], mode
    
    results = dm.similarity_engine.find_similar(
        playlist_id,
        top_n=10,
        only_followed=(mode == 'followed'),
        only_owned=(mode == 'owned'),
    )
    
    if not results:
        empty = html.Div([
            html.Div("😔", className="empty-icon"),
            html.P("No similar playlists found", className="empty-text"),
        ], className="empty-state")
        return empty, btn_classes['followed'], btn_classes['owned'], btn_classes['all'], mode
    
    items = []
    for i, r in enumerate(results):
        badge = html.Span("OWNED", className="badge owned") if r['is_owned'] else html.Span("FOLLOWED", className="badge followed")
        
        items.append(html.Div([
            html.Div(str(i + 1), className="rank"),
            html.Div([
                html.Div([r['name'], " ", badge], className="result-name"),
                html.Div(f"{r['track_count']} tracks", className="result-meta"),
            ], className="result-info"),
            html.Div([
                html.Div(f"{r['similarity']*100:.0f}%", className="score-value"),
                html.Div("match", className="score-label"),
            ], className="result-score"),
        ], className="result-item"))
    
    return html.Div(items, className="results-list"), btn_classes['followed'], btn_classes['owned'], btn_classes['all'], mode


@callback(
    Output('login-status', 'children'),
    Output('url', 'pathname', allow_duplicate=True),
    Input('load-data-btn', 'n_clicks'),
    prevent_initial_call=True,
)
def load_data(n_clicks):
    """Load cached data."""
    if n_clicks:
        dm.initialize()
        if dm.is_loaded:
            return html.Span("✅ Data loaded!", className="success-text"), '/'
        else:
            return html.Span("❌ Failed to load data. Run sync notebook first.", className="error-text"), no_update
    return "", no_update


@callback(
    Output('btn-exclude-liked', 'className'),
    Output('btn-exclude-monthly', 'className'),
    Output('global-filter-stats', 'children'),
    Output('filter-state', 'data'),
    Input('btn-exclude-liked', 'n_clicks'),
    Input('btn-exclude-monthly', 'n_clicks'),
    Input('global-playlist-filter', 'value'),
    State('filter-state', 'data'),
    prevent_initial_call=True,
)
def apply_global_filters(n_liked, n_monthly, selected_playlists, state):
    """Apply global playlist filters."""
    if not dm.is_loaded:
        raise PreventUpdate
    
    triggered = ctx.triggered_id
    
    if triggered == 'btn-exclude-liked':
        state['exclude_liked'] = not state.get('exclude_liked', False)
    elif triggered == 'btn-exclude-monthly':
        state['exclude_monthly'] = not state.get('exclude_monthly', False)
    
    state['selected'] = selected_playlists
    
    # Apply filters to data manager
    dm.apply_filters(
        exclude_liked=state.get('exclude_liked', False),
        exclude_monthly=state.get('exclude_monthly', False),
        selected_ids=selected_playlists if selected_playlists else None,
    )
    
    # Update button classes
    liked_class = "filter-btn active" if state.get('exclude_liked') else "filter-btn"
    monthly_class = "filter-btn active" if state.get('exclude_monthly') else "filter-btn"
    
    # Stats
    stats = dm.analyzer.stats()
    stats_text = f"{stats.get('total_playlists', 0)} playlists • {stats.get('total_tracks', 0):,} tracks"
    
    return liked_class, monthly_class, stats_text, state




@callback(
    Output('settings-output', 'children'),
    Input('reload-data-btn', 'n_clicks'),
    prevent_initial_call=True,
)
def reload_data(n_clicks):
    """Reload data from disk."""
    if n_clicks:
        dm._initialized = False
        dm.initialize()
        if dm.is_loaded:
            return html.Span("✅ Data reloaded successfully!", className="success-text")
        else:
            return html.Span("❌ Failed to reload data.", className="error-text")
    return ""


# ============================================================================
# RUN
# ============================================================================

if __name__ == '__main__':
    print("🎵 Starting Spotim8 Dashboard...")
    print(f"📁 Data directory: {DATA_DIR}")
    dm.initialize()
    app.run(debug=True, port=8050)
