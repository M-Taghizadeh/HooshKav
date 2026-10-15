# Hooshkav (هوشکاو) — AI News Telegram Bot

An automated, fully free system that collects the most important AI news from 50+ global sources, deduplicates stories, scores them by coverage frequency, and publishes Persian-language posts to a Telegram channel — powered by Google Gemini and running on GitHub Actions (no server required).

---

## System Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        GITHUB ACTIONS (Cron)                        │
│              04:30 UTC → daily digest (08:00 Iran time)             │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      STEP 1 — RSS FETCH                             │
│                                                                     │
│  50 AI-specific RSS feeds          6 Google News dynamic feeds      │
│  (TechCrunch AI, Verge AI,         (AI general, LLMs, startups,     │
│   Anthropic, OpenAI, DeepMind,      models, policy, research)       │
│   ArXiv cs.AI/LG/CL, MIT, ...)                                      │
│                                                                     │
│  Last 24 hours — articles without a date are dropped                │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  STEP 2 — SEMANTIC DEDUP + SCORING                  │
│                                                                     │
│  1. Tokenize all titles                                             │
│  2. Build TF-IDF vectors (no external libraries)                    │
│  3. Greedy cosine-similarity clustering (threshold = 0.55)          │
│     → Same story covered by N sources → merged into 1 entry        │
│  4. mention_count = number of sources that covered this story       │
│  5. Representative = article with image + most recent publish date  │
│  6. Sort by mention_count DESC (most-covered story first)           │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────┐
│   LLM CALL (digest)    │
│                        │
│  Input: all articles   │
│  + mention_count       │
│                        │
│  Output: JSON with     │
│  10 selected links +   │
│  Persian summaries     │
└───────┬────────────────┘
        │
        ▼
┌───────────────────┐
│  BUILD DIGEST     │
│  (programmatic)   │
│                   │
│  Injects <a href> │
│  on every item    │
└───────┬───────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  STEP 4 — LLM PROVIDER FALLBACK                     │
│                                                                     │
│         Gemini API  →  Groq API  →  OpenRouter API                  │
│         (primary)      (fallback)    (last resort)                  │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  STEP 5 — HTML SANITIZATION                         │
│                                                                     │
│  • Strip markdown fences (```html)                                  │
│  • Convert [text](url) → <a href="url">text</a>                     │
│  • Remove unsupported tags (div, p, span, ul, li...)                │
│  • Balance unclosed <b>, <i>, <a> tags                              │
│  • Safe truncation at Telegram limits (caption: 1024, text: 4096)  │
│    without breaking open HTML tags                                  │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  STEP 6 — TELEGRAM DISPATCH                         │
│                                                                     │
│  sendPhoto (with caption) → fallback to sendMessage (HTML)          │
│                           → fallback to sendMessage (plain text)    │
│                                                                     │
│  Retry logic: up to 3 attempts, exponential backoff on 429          │
└─────────────────────────────────────────────────────────────────────┘

Daily Output:
  08:00 Iran → digest (5 Persian headlines, text only)
  12:00 Iran → educational post (from Medium / Kaggle / TDS / …)
  18:00 Iran → educational post
```

---

## Key Features

- **50 AI-specific RSS feeds** — AI/ML news for the morning digest.
- **Educational feeds** — Medium, Towards Data Science, Kaggle Blog, Real Python, Hugging Face, and tutorial-focused Google News — rewritten into human Persian posts.
- **Admin publish mode** — `/mode news` | `/mode both` | `/mode edu` toggles what scheduled jobs send (`config/publish_mode.json`).
- **Semantic deduplication** — TF-IDF clustering + `mention_count` for digest ranking.
- **Multi-provider LLM fallback** — Gemini → Groq → OpenRouter.
- **On-demand commands** — `/digest`, `/edu`, `/single`, `/mode` for `ALLOWED_TELEGRAM_USER`.

---

## Setup

### Step 1 — Create a Telegram Bot

1. Message [@BotFather](https://t.me/BotFather) and run `/newbot`.
2. Copy the API token — this is your `TELEGRAM_BOT_TOKEN`.
3. Add the bot to your channel as **Admin** with post permission.
4. Find your channel ID:
   - **Public channel**: use `@channelname`
   - **Private channel**: send a message, then open `https://api.telegram.org/bot<TOKEN>/getUpdates` and find `"chat":{"id": -100...}`

### Step 2 — Get a Free Gemini API Key

1. Go to [aistudio.google.com](https://aistudio.google.com) and sign in.
2. Click **Get API Key** → **Create API Key**.
3. Copy the key — this is your `GEMINI_API_KEY` (free up to 1,500 requests/day).

### Step 3 — Deploy on GitHub Actions

1. Push this repository to GitHub (public or private).
2. Go to **Settings → Secrets and variables → Actions → New repository secret** and add:

| Secret | Value |
|:---|:---|
| `GEMINI_API_KEY` | Gemini API key from Google AI Studio |
| `TELEGRAM_BOT_TOKEN` | Bot token from BotFather |
| `TELEGRAM_CHAT_ID` | Channel ID (e.g. `@my_ai_channel` or `-100123456789`) |
| `ALLOWED_TELEGRAM_USER` | Telegram username allowed to trigger on-demand posts |

The workflow runs automatically on schedule. You can also trigger it manually from the **Actions** tab → **Run workflow**.

---

## Local Testing

```bash
pip install -r requirements.txt

# Copy and fill in your credentials
cp .env.example .env

# Preview digest output in terminal (no Telegram send)
python test_send.py digest

# Morning news digest
python main.py digest

# Educational post (slot 0 = noon, 1 = evening)
python main.py edu 0

# Run tests
python -m pytest test_hooshkav.py -v
```

Admin Telegram commands:

| Command | Effect |
|:---|:---|
| `/mode` | Show current publish mode |
| `/mode news` | Scheduled jobs: news only |
| `/mode both` | News + education (default) |
| `/mode edu` | Education only |
| `/digest` | Send digest now |
| `/edu` | Send one educational post now |

---

## Configuration (`main.py`)

| Variable | Default | Description |
|:---|:---|:---|
| `TARGET_DIGEST_COUNT` | `5` | Number of headlines in the daily digest |
| `LOOKBACK_HOURS` | `24` | Time window for the daily digest |
| `LOOKBACK_HOURS_EDU` | `72` | Time window for educational sources |
| `MAX_PER_FEED` | `5` | Max articles per RSS feed |
| `RSS_FEEDS` | 50 entries | News RSS feeds |
| `EDU_RSS_FEEDS` | tutorial feeds | Educational RSS feeds |
| `config/publish_mode.json` | `both` | Admin-controlled publish mode |

---

## Schedule (Iran Time)

| UTC | Iran Winter (IRST +3:30) | Iran Summer (IRDT +4:30) | Mode |
|:---|:---|:---|:---|
| 04:30 | 08:00 | 09:00 | digest (5 headlines) |
| 08:30 | 12:00 | 13:00 | educational post |
| 14:30 | 18:00 | 19:00 | educational post |
