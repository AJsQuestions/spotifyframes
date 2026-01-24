# Quick Start Guide

This guide will help you get SpotiM8 up and running in minutes.

## Prerequisites

- Python 3.10+
- Spotify Developer Account (free)
- Spotify Premium (for some features)

## Installation

```bash
# Clone the repository
git clone https://github.com/AJsQuestions/spotim8.git
cd spotim8

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -e .
```

## Spotify API Setup

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Log in with your Spotify account
3. Click **"Create app"**
4. Fill in:
   - **App name**: Spotim8 (or any name)
   - **App description**: Personal Spotify analytics
   - **Redirect URI**: `http://127.0.0.1:8888/callback` ⚠️ **Must match exactly**
   - Check **"I understand and agree..."**
5. Click **"Save"**
6. Copy your **Client ID** and **Client Secret** from Settings

## Configuration

Create a `.env` file in the project root:

```bash
cp env.example .env
```

Edit `.env` and add your credentials:

```bash
# Required
SPOTIPY_CLIENT_ID=your_client_id_here
SPOTIPY_CLIENT_SECRET=your_client_secret_here
SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback

# Optional: For automated runs
SPOTIPY_REFRESH_TOKEN=your_refresh_token_here

# Optional: Customize playlist naming
PLAYLIST_OWNER_NAME=AJ
PLAYLIST_PREFIX=Finds
```

## Get Refresh Token (Recommended)

For automated runs without browser interaction:

```bash
source venv/bin/activate
python src/scripts/utils/get_token.py
```

This will open your browser for Spotify authorization and generate a refresh token.

## First Sync

```bash
# Sync your library (first time can take 1-2+ hours for large libraries)
python src/scripts/automation/sync.py
```

## Next Steps

- Check out the [Jupyter notebooks](../src/notebooks/) for analysis
- Set up [automation](../features/automation.md) for daily syncs
- Explore [production features](../features/production-features.md)
