# 🖥️ Automated Faceless YouTube Channel — CS Course Bot

Uploads a **daily 5-minute animated educational video** to YouTube — fully automated, 100% free.

**100 topics · Basic → Advanced · No manual work after setup**

---

## How It Works

```
GitHub Actions (daily cron)
  → Pick next topic from curriculum.json
  → Claude API generates script + slide content
  → edge-tts generates narration audio (free neural voice)
  → Pillow renders styled animation slides
  → MoviePy assembles video + audio
  → Pillow creates YouTube thumbnail
  → YouTube Data API uploads everything
  → curriculum.json is updated and committed
```

---

## Free Stack

| Tool | Purpose | Cost |
|------|---------|------|
| GitHub Actions | Daily scheduler | Free (public repos) |
| Anthropic Claude API | Script generation | Free tier / ~$0.01/video |
| edge-tts | Neural TTS narration | Free |
| Pillow + MoviePy | Video rendering | Free |
| YouTube Data API v3 | Upload | Free (10k units/day) |

---

## Setup Guide

### Step 1 — Clone and install locally

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
bash setup.sh
```

### Step 2 — Get your Anthropic API key

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Create an API key
3. Add it to `.env`:
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   ```

### Step 3 — Set up YouTube API

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (e.g. `youtube-bot`)
3. Enable **YouTube Data API v3**
   - APIs & Services → Enable APIs → search "YouTube Data API v3" → Enable
4. Create OAuth credentials
   - APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID
   - Application type: **Desktop app**
   - Download the JSON → save as `client_secrets.json` in this folder
5. Run the one-time auth flow:
   ```bash
   python auth_setup.py
   ```
6. A browser window opens — log in with your **YouTube channel** Google account
7. Copy the three values printed to the terminal

### Step 4 — Set GitHub Secrets

In your GitHub repo: **Settings → Secrets and variables → Actions → New repository secret**

| Secret name | Value |
|-------------|-------|
| `ANTHROPIC_API_KEY` | Your Anthropic key |
| `YOUTUBE_CLIENT_ID` | From auth_setup.py output |
| `YOUTUBE_CLIENT_SECRET` | From auth_setup.py output |
| `YOUTUBE_REFRESH_TOKEN` | From auth_setup.py output |
| `CHANNEL_NAME` | e.g. `LearnCS Daily` (optional) |
| `TTS_VOICE` | e.g. `en-US-AriaNeural` (optional) |

### Step 5 — Make the repo public (for unlimited GitHub Actions minutes)

Settings → General → Danger Zone → Change visibility → Public

### Step 6 — Test the pipeline locally

```bash
python pipeline.py
```

This will generate Day 1's video and upload it. Check your YouTube Studio.

### Step 7 — Push and let it run

```bash
git add .
git commit -m "Initial setup"
git push origin main
```

GitHub Actions will now run every day at 9:00 AM IST (3:30 AM UTC).
You can also trigger it manually from the **Actions** tab → **Daily YouTube Upload** → **Run workflow**.

---

## Project Structure

```
youtube_automation/
├── pipeline.py              # Main orchestrator — run this daily
├── curriculum.json          # 100-topic CS course (tracks progress)
├── config.py                # Env var loader
├── auth_setup.py            # One-time YouTube OAuth setup
├── setup.sh                 # Local installation script
├── requirements.txt
├── modules/
│   ├── script_generator.py  # Claude API → structured script
│   ├── animator.py          # Pillow slide renderer
│   ├── tts_narrator.py      # edge-tts narration
│   ├── video_assembler.py   # MoviePy video + audio merge
│   ├── thumbnail_generator.py
│   └── youtube_uploader.py  # YouTube Data API v3
└── .github/
    └── workflows/
        └── daily_upload.yml # GitHub Actions cron job
```

---

## Customisation

### Change the TTS voice

Edit `.env` or the GitHub Secret `TTS_VOICE`. Options:

```
en-US-AriaNeural      (warm female — default)
en-US-GuyNeural       (clear male)
en-US-JennyNeural     (professional female)
en-US-BrianNeural     (engaging male)
en-GB-SoniaNeural     (British female)
en-IN-NeerjaNeural    (Indian English female)
```

### Change upload time

Edit `.github/workflows/daily_upload.yml`:
```yaml
- cron: '30 3 * * *'   # 3:30 AM UTC = 9:00 AM IST
```
Use [crontab.guru](https://crontab.guru) to build your schedule.

### Upload as unlisted first (recommended for testing)

In `.env`:
```
VIDEO_PRIVACY=unlisted
```
Switch to `public` when you're happy with the output.

### Add your own topics

Edit `curriculum.json` — add entries to the `topics` array:
```json
{
  "id": "cs101",
  "day": 101,
  "title": "Your Custom Topic",
  "module": "Module Name",
  "level": "Beginner",
  "tags": ["tag1", "tag2"],
  "uploaded": false
}
```

---

## Troubleshooting

**`ANTHROPIC_API_KEY` not working**
→ Check console.anthropic.com for quota and billing.

**YouTube upload fails with 403**
→ Your refresh token may have expired. Re-run `python auth_setup.py` and update the GitHub Secret.

**GitHub Actions times out**
→ The pipeline takes ~20-25 min. If it times out increase `timeout-minutes` in the workflow YAML.

**Video has no audio**
→ Check that `ffmpeg` is installed (`ffmpeg -version`). MoviePy needs it for audio muxing.

**Font rendering issues on Windows**
→ The fonts fallback gracefully. Install `fonts-dejavu-core` on Linux or use WSL.

---

## Monetisation Path

Once you hit 1,000 subscribers + 4,000 watch hours:

1. Apply for YouTube Partner Programme
2. Enable AdSense on the channel
3. The bot keeps uploading — revenue runs passively

With 100 days of consistent educational content, channels in the CS/coding niche typically reach these thresholds in 3-6 months.

---

## License

MIT — use freely, modify as needed.
