# 🔍 Spotify Crash Analysis Report

## Summary

Based on your exported Spotify data, I've identified **2 fatal crashes** and several contributing factors.

## 🚨 Fatal Crashes (Error Code 12)

Your Spotify app crashed **2 times** due to fatal playback errors:

1. **December 2, 2025 at 06:09:49 UTC**
   - Track: **"HONEST"** (`spotify:track:58k32my5lKofeZRtIvBDg9`)
   - Crashed at 141.9 seconds into the track
   - App Version: 9.1.0.1151
   - iOS Version: 18.6.2

2. **November 27, 2025 at 04:39:04 UTC**
   - Track: **"MONEY ON THE DASH - SPED UP"** (`spotify:track:086THPnabbu1zfDjRsxpoN`)
   - Crashed at 62.3 seconds into the track
   - App Version: 9.0.98.1187
   - iOS Version: 18.6.2

## 🔧 Root Causes Identified

### 1. Audio Driver Errors (Error Code -50)
- **3 occurrences** of iOS system error `kAudioUnitErr_InvalidProperty`
- This happens when the app tries to access the audio unit while it's being reset
- **Correlation**: All 3 errors occurred within 5 seconds of the December 2nd crash

### 2. Audio Session Resets
- **3 occurrences** of `AVAudioSessionMediaServicesWereResetNotification`
- iOS is resetting the audio session, which can cause crashes
- **Correlation**: Both crashes had audio session resets happening at the same time

### 3. Non-Fatal Errors (Error Code 8001)
- **7 occurrences** of temporary playback errors
- Usually network-related, but can indicate underlying issues

## 💡 Recommendations

### Immediate Actions:
1. **Update Spotify App**: You were using version 9.1.0.1151 during one crash. Update to the latest version.
2. **Restart Your iPhone**: This can clear audio session conflicts
3. **Check Internet Connection**: Poor connectivity can cause playback errors

### If Crashes Persist:
1. **Clear Spotify Cache**: 
   - Settings > Spotify > Clear Cache (or reinstall the app)
2. **Report Problematic Tracks**: 
   - **"HONEST"** and **"MONEY ON THE DASH - SPED UP"** caused crashes
   - These tracks may have corrupted audio files on Spotify's servers
   - Report them to Spotify support with the track IDs
3. **Check for Audio Conflicts**:
   - Close other audio apps before using Spotify
   - Avoid switching between audio apps quickly
   - Disable background audio from other apps

### Long-term Solutions:
1. **Monitor Error Patterns**: Run the analysis notebook regularly to track new issues
2. **Keep iOS Updated**: Ensure you're on the latest iOS version
3. **Network Quality**: Use Wi-Fi when possible for more stable streaming

## 📊 Error Statistics

- **Total Playback Errors**: 9
  - Fatal (crashes): 2
  - Non-fatal: 7
- **Audio Driver Errors**: 6
  - Error -50: 3 (system errors)
  - Error 0: 3 (notifications)

## 🔍 Technical Details

### Error Code 12 (Fatal)
- Indicates a fatal playback error
- Common causes:
  - Corrupted audio file on Spotify's servers
  - Network connectivity issues
  - Audio driver/system issues

### Error Code -50 (Audio Driver)
- iOS system error: `kAudioUnitErr_InvalidProperty`
- Occurs when trying to access audio unit during reset
- Often happens during audio session transitions

### Audio Session Resets
- iOS resets audio session when:
  - Another app takes control of audio
  - System audio interruptions (calls, alarms)
  - Audio hardware changes (plugging/unplugging headphones)

## 📝 Next Steps

1. Run `notebooks/07_analyze_crashes.ipynb` for detailed analysis
2. Monitor for new crashes after applying fixes
3. Report persistent issues to Spotify support with this analysis

---

*Generated from exported Spotify data analysis*

