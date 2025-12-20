# 🎵 Spotim8 Web

A modern, privacy-first Spotify analytics dashboard. Login with your Spotify account to visualize your music library with interactive charts and discover insights about your listening habits.

**🔒 Privacy First:** All data is processed entirely in your browser. Nothing is ever stored or sent to any server.

## 🔐 Privacy & Security

This is an **open-source academic project** with a strict privacy-first approach:

- ✅ **No server-side storage** - All data processing happens in your browser
- ✅ **No cookies or tracking** - We don't track your usage in any way
- ✅ **Session-only data** - Close the tab and all data is immediately cleared
- ✅ **No backend** - This is a purely static, client-side application
- ✅ **Open source** - The code is fully transparent and auditable
- ✅ **No commercial purpose** - Built for learning and personal use only

Your Spotify credentials are handled directly by Spotify's OAuth system. We never see or store your password.

## ✨ Features

- **📊 Interactive Dashboard** - Stats at a glance with beautiful visualizations
- **🎤 Top Artists** - See your most-featured artists
- **🎸 Genre Breakdown** - Pie chart showing your genre distribution
- **📈 Timeline** - Stacked area chart showing when your music was released
- **🌳 Artist Treemap** - Visual landscape of your top artists
- **🗺️ Playlist Clusters** - Similarity visualization of your playlists
- **💎 Hidden Gems** - Discover underrated tracks in your library
- **🎯 Taste Profile** - Radar charts showing your genre preferences

## 🚀 Tech Stack

- **React 18** with TypeScript
- **Vite** - Lightning-fast build tool
- **Tailwind CSS** - Utility-first styling with custom cyberpunk theme
- **Recharts** - Composable charting library
- **Framer Motion** - Smooth animations
- **Spotify Web API** with PKCE OAuth (no backend required)

## 🛠️ Setup

### 1. Create a Spotify App

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create a new app
3. Add your redirect URI (your GitHub Pages URL)
4. Copy your **Client ID**

### 2. Configure GitHub Secrets

Add your Spotify Client ID as a GitHub repository secret:
1. Go to your repo → Settings → Secrets and variables → Actions
2. Click "New repository secret"
3. Name: `VITE_SPOTIFY_CLIENT_ID`
4. Value: Your Spotify App Client ID

### 3. Local Development

```bash
# Clone the repository
git clone <your-repo-url>
cd spotim8/web

# Create local environment file
echo "VITE_SPOTIFY_CLIENT_ID=your_client_id_here" > .env

# Install dependencies
npm install

# Start development server
npm run dev
```

## 🌐 Deployment

The site auto-deploys to GitHub Pages when you push to `main`. Make sure:

1. GitHub Pages is enabled (Settings → Pages → Source: GitHub Actions)
2. `VITE_SPOTIFY_CLIENT_ID` secret is set
3. Redirect URI in Spotify app matches your GitHub Pages URL

## 📂 Project Structure

```
src/
├── components/        # Reusable UI components
├── context/          # React context (auth & data state)
├── lib/              # Spotify API & analytics utilities
├── pages/            # Page components
├── App.tsx           # Main app with routing
├── main.tsx          # Entry point
└── index.css         # Global styles
```

## 🔧 How It Works

1. **OAuth with PKCE** - Secure authentication without a backend server
2. **Client-side API calls** - Fetches data directly from Spotify API
3. **In-memory processing** - All analytics computed in the browser
4. **Session storage** - Auth tokens stored only in sessionStorage (cleared on tab close)

## 📜 License

MIT License - feel free to use this for your own projects!

## 🎓 Academic Project

This is an open-source academic project built for learning and personal use. It has no commercial purpose and does not collect any user data.
