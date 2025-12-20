# 🎵 Spotim8 Web

A modern, privacy-first Spotify analytics dashboard. **Anyone** can login with their Spotify account to visualize their music library.

**🔒 Privacy First:** All data is processed entirely in your browser. Nothing is ever stored or sent to any server.

## 🌐 Live Demo

**https://ajsquestions.github.io/spotiframes/**

## ✨ How It Works

1. Click "Connect with Spotify"
2. Authorize with your Spotify account
3. Your library is analyzed **entirely in your browser**
4. Close the tab → all data is gone (nothing stored)

## 🔐 Privacy & Security

- ✅ **No server** - Purely static site, no backend
- ✅ **No database** - Nothing is ever stored
- ✅ **No tracking** - No cookies, no analytics
- ✅ **Session only** - Data cleared when you close the tab
- ✅ **Open source** - Code is fully auditable
- ✅ **PKCE OAuth** - Secure authentication without secrets

Your Spotify password is handled directly by Spotify. We never see it.

## ✨ Features

- 📊 **Dashboard** - Library stats at a glance
- 🎤 **Top Artists** - Artist treemap visualization
- 🎸 **Genre Breakdown** - Pie chart of your genres
- 📈 **Timeline** - When your music was released
- 🗺️ **Playlist Clusters** - Similarity visualization
- 💎 **Hidden Gems** - Discover underrated tracks
- 🎯 **Taste Profile** - Radar charts of preferences

## 🛠️ Self-Hosting

Want to host your own instance?

### 1. Create a Spotify App
1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create a new app
3. Set **Redirect URI** to your GitHub Pages URL (e.g., `https://yourusername.github.io/your-repo/`)
4. Copy your **Client ID**

### 2. Fork & Configure
1. Fork this repo
2. Go to Settings → Secrets → Actions
3. Add secret: `SPOTIPY_CLIENT_ID` = your Client ID

### 3. Enable GitHub Pages
1. Settings → Pages → Source: **GitHub Actions**
2. Push any change to trigger deploy

### 4. Allow Users (Development Mode)
By default, Spotify apps are in "Development Mode" which allows up to **25 users**. To allow more:
1. Go to your app in Spotify Dashboard
2. Click "Request Extension" for Extended Quota
3. Fill out the form (takes ~1 week to approve)

## 🖥️ Local Development

```bash
cd web

# Create .env file
echo "VITE_SPOTIFY_CLIENT_ID=your_client_id" > .env

# Install & run
npm install
npm run dev
```

Add `http://localhost:5173/spotiframes/` as a Redirect URI in your Spotify app.

## 🚀 Tech Stack

- **React 18** + TypeScript
- **Vite** - Fast builds
- **Tailwind CSS** - Styling
- **Recharts** - Charts
- **Framer Motion** - Animations
- **Spotify PKCE OAuth** - No backend needed

## 📄 License

MIT - Use freely for your own projects!
