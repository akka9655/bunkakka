# Smart Bunker - PSG Tech Attendance Tracker

**Premium attendance and bunk planner for PSG Tech students**

## 🚀 Quick Start

### For Deployment

1. **Upload to GitHub**
   ```bash
   git init
   git add .
   git commit -m "Smart Bunker v2.0"
   git push
   ```

2. **Deploy to Vercel**
   - Go to [vercel.com](https://vercel.com)
   - Import your repository
   - Deploy (auto-configured)

3. **Done!** Your app is live 🎉

## 📁 Project Structure

```
/
├── api/
│   ├── index.py           # Flask backend with scraping
│   ├── favicon.py         # Favicon handler
│   └── templates/
│       └── index.html     # Complete UI (from 33.html)
├── static/
│   └── manifest.json      # PWA manifest
├── requirements.txt
└── vercel.json
```

## ⚙️ Configuration (Each Semester)

**File:** `api/index.py` (Lines 18-69)

Update these values:
- `API_YEAR`: Current academic year (e.g., 2025)
- `PLANNER_MAP`: Planner IDs if changed by college
- `COURSE_CODES`: Add new roll number patterns if introduced

## ✨ Features

- ✅ Login with eCampus credentials
- ✅ Works without attendance data (shows timetable & calendar)
- ✅ Real-time bunk simulator
- ✅ Manual attendance tracking
- ✅ Academic calendar with holiday themes
- ✅ PWA (installable app)
- ✅ Performance mode toggle
- ✅ SEO optimized

## 🎯 API Endpoints

- `GET /` - Main application
- `POST /api/login` - Authenticate user
- `GET /api/calendar/<roll_number>` - Fetch academic calendar
- `GET /api/health` - Health check

## 📱 PWA Support

App can be installed on mobile devices for full-screen experience.

## 🔒 Security

- No passwords stored
- Session-based authentication
- CORS handled via backend proxy

## 📝 Notes

- Calendar data proxied through backend (avoids CORS)
- Login succeeds with timetable only (attendance optional)
- Ghost animation shows when attendance updating
- Manual tracking auto-syncswith college updates

---

**Created for PSG Tech Students** • *Use at your own risk*
