# VELAR

Proactive personal AI assistant. Voice-first, bilingual (Turkish/English), always-on Mac daemon with memory.

---

## Quick Start

### 1. Clone

```bash
git clone https://github.com/oguzhan-kara/velar.git
cd velar
```

### 2. Backend Setup

```bash
cd velar-backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# → Fill in .env with your API keys (see Keys section below)
```

Run database migrations:
```bash
# Apply all migrations in supabase/migrations/ via Supabase dashboard SQL editor
# or using the Supabase CLI:
supabase db push
```

Start the backend:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Health check:
```bash
curl http://localhost:8000/health
```

### 3. Get a JWT Token

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"your@email.com","password":"yourpassword"}' \
  | python3 -m json.tool
# Copy the access_token value
```

### 4. Mac Daemon Setup (macOS only)

```bash
cd velar-daemon
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create daemon config:
```bash
mkdir -p ~/.velar
cat > ~/.velar/daemon.json << 'EOF'
{
  "backend_url": "http://localhost:8000",
  "wake_sensitivity": 0.5,
  "audio_device_index": null,
  "auth_token": "PASTE_YOUR_JWT_HERE"
}
EOF
```

Start the daemon (backend must be running first):
```bash
python daemon.py
```

Gray dot `●` appears in menu bar → say **"Hey Jarvis"** → chime plays → speak your question.

Install for boot persistence (optional):
```bash
./install.sh
```

---

## API Keys

| Key | Where to get it |
|-----|----------------|
| `SUPABASE_URL` | Supabase dashboard → Settings → API |
| `SUPABASE_ANON_KEY` | Supabase → Settings → API → anon/public |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase → Settings → API → service_role |
| `SUPABASE_JWT_SECRET` | Supabase → Settings → API → JWT Secret |
| `DATABASE_URL` | Supabase → Settings → Database → URI (use `postgresql+asyncpg://` prefix) |
| `ANTHROPIC_API_KEY` | console.anthropic.com |
| `ELEVENLABS_API_KEY` | elevenlabs.io → Profile → API Keys |
| `OPENAI_API_KEY` | platform.openai.com → API keys (used for memory embeddings) |
| `OPENWEATHERMAP_API_KEY` | openweathermap.org → API keys → subscribe to **One Call by Call** |
| `GOOGLE_PLACES_API_KEY` | Google Cloud Console → APIs & Services → Credentials → enable **Places API (New)** |
| `GOOGLE_CALENDAR_CREDENTIALS_PATH` | Google Cloud Console → Credentials → OAuth 2.0 Client ID (Desktop) → download JSON → save to `~/.velar/google_credentials.json` |

---

## Testing the Backend

```bash
cd velar-backend
source .venv/bin/activate
pytest tests/ -v
```

Text chat (no microphone needed):
```bash
curl -s -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer YOUR_JWT" \
  -H "Content-Type: application/json" \
  -d '{"message": "Merhaba, nasılsın?"}' \
  | python3 -m json.tool
```

---

## Project Structure

```
velar/
├── velar-backend/          # FastAPI backend
│   ├── app/
│   │   ├── auth/           # Supabase JWT auth
│   │   ├── memory/         # pgvector memory system
│   │   ├── users/          # User profile
│   │   ├── voice/          # STT, TTS, Claude loop, integrations
│   │   │   └── tools/      # Calendar, weather, reminders, places
│   │   └── health/         # Health endpoint
│   ├── supabase/
│   │   └── migrations/     # Database schema
│   └── tests/
├── velar-daemon/           # macOS menu bar daemon
│   ├── daemon.py           # rumps App, thread orchestration
│   ├── wakeword.py         # openwakeword hey_jarvis listener
│   ├── audio_capture.py    # Silero VAD recording
│   ├── chime.py            # Activation sound
│   ├── backend_client.py   # HTTP client to backend
│   ├── config.py           # ~/.velar/daemon.json loader
│   └── launchd/            # Boot persistence plist
└── .planning/              # GSD planning docs (roadmap, phases, research)
```

---

## Phases

| Phase | Status | What it is |
|-------|--------|-----------|
| 1. Foundation | ✓ Complete | FastAPI, Supabase, auth, RLS |
| 2. Voice Pipeline | ✓ Complete | Whisper STT, Claude, ElevenLabs TTS |
| 3. Memory System | ✓ Complete | pgvector, auto-extraction, /memory API |
| 4. Mac Daemon | ◆ In Progress | Wake word, menu bar, integrations |
| 5. Proactive Engine | ○ Planned | Morning briefing, push notifications |
| 6. iPhone App | ○ Planned | Flutter mobile client |
| 7. Watch App | ○ Planned | Apple Watch + advice features |
