# Hooshkav (هوشکاو) — AI News Telegram Bot

An automated, fully free system that collects the most important AI news from 50+ global sources, deduplicates stories, scores them by coverage frequency, and publishes Persian-language posts to a Telegram channel — powered by Google Gemini and running on GitHub Actions (no server required).

---

## System Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        GITHUB ACTIONS (Cron)                        │
│   08:30 UTC → digest mode      08:00 / 12:00 / 16:00 UTC → single   │
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
│  digest: last 24 hours             single: last 8 hours only        │
│  Articles without a date → dropped                                  │
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
              ┌──────────┴──────────┐
              │                     │
              ▼                     ▼
     ┌────────────────┐    ┌─────────────────────┐
     │  DIGEST MODE   │    │    SINGLE MODE       │
     │  (08:30 UTC)   │    │ (08/12/16 UTC)       │
     └───────┬────────┘    └──────────┬───────────┘
             │                        │
             ▼                        ▼
┌────────────────────────┐  ┌─────────────────────────────────────────┐
│   LLM CALL 1 (digest)  │  │         LLM CALL 1 (select)             │
│                        │  │                                         │
│  Input: all articles   │  │  Input: article list + mention_count    │
│  + mention_count       │  │  Output: index of most important story  │
│                        │  └──────────────────┬──────────────────────┘
│  Output:               │                     │
│  • Digest post (10     │                     ▼
│    news items in       │  ┌─────────────────────────────────────────┐
│    Persian HTML)       │  │         LLM CALL 2 (write post)         │
│  • TOP3_JSON block     │  │                                         │
│    (3 best link URLs)  │  │  Input: selected article                │
└───────┬────────────────┘  │  Output: full rich Persian post         │
        │                   └──────────────────┬──────────────────────┘
        ▼                                      │
┌───────────────────┐                          │
│  LLM CALLS 2-4    │                          │
│  (3x rich posts)  │                          │
│                   │                          │
│  One call per     │                          │
│  top-3 story →    │                          │
│  full Persian     │                          │
│  analysis post    │                          │
└───────┬───────────┘                          │
        │                                      │
        └──────────────────┬───────────────────┘
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
  08:00 Iran → 1 digest post (10 headlines) + 3 full analysis posts
  11:30 Iran → 1 fresh rich post (last 8h news only)
  15:30 Iran → 1 fresh rich post (last 8h news only)
  19:30 Iran → 1 fresh rich post (last 8h news only)
```

---

## Key Features

- **50 AI-specific RSS feeds** — all scoped to AI/ML: lab blogs (OpenAI, DeepMind, Anthropic, Meta AI, Mistral), research (ArXiv cs.AI/LG/CL, Papers With Code), news (TechCrunch AI, The Verge AI, MIT Tech Review, Wired AI), newsletters (Import AI, TLDR AI, Last Week in AI), and more.
- **Semantic deduplication** — TF-IDF cosine similarity clusters near-duplicate titles across sources; `mention_count` tracks how many outlets covered the same story.
- **mention_count signal** — stories covered by more sources rank higher in the LLM prompt, producing more reliable importance scoring.
- **Strict time windows** — digest uses last 24 hours; single posts use last 8 hours to avoid repeating morning stories.
- **Multi-provider LLM fallback** — Gemini → Groq (Llama 3.3 70B) → OpenRouter; all free tiers.
- **Safe HTML output** — balanced tags, safe truncation, markdown-to-HTML conversion, Telegram parse mode compatibility.
- **Telegram retry** — handles rate limits (429) with exponential backoff.
- **On-demand commands** — authorized user (`ALLOWED_TELEGRAM_USER`) can trigger `/digest` or `/single` from Telegram at any time.

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

# Preview single post output in terminal
python test_send.py single

# Run the full bot (sends to Telegram)
python main.py digest
python main.py single

# Run tests
python -m pytest test_hooshkav.py -v
```

---

## Configuration (`main.py`)

| Variable | Default | Description |
|:---|:---|:---|
| `TARGET_DIGEST_COUNT` | `10` | Number of headlines in the daily digest |
| `LOOKBACK_HOURS` | `24` | Time window for digest mode |
| `LOOKBACK_HOURS_SINGLE` | `8` | Time window for single post mode |
| `MAX_PER_FEED` | `5` | Max articles per RSS feed |
| `MAX_PER_DYNAMIC_FEED` | `10` | Max articles per Google News feed |
| `RSS_FEEDS` | 50 entries | List of AI-specific RSS feeds |
| `DYNAMIC_SEARCH_FEEDS` | 6 entries | Google News dynamic search feeds |

---

## Schedule (Iran Time)

| UTC | Iran Winter (IRST +3:30) | Iran Summer (IRDT +4:30) | Mode |
|:---|:---|:---|:---|
| 04:30 | 08:00 | 09:00 | digest + 3 rich posts |
| 08:00 | 11:30 | 12:30 | single (last 8h) |
| 12:00 | 15:30 | 16:30 | single (last 8h) |
| 16:00 | 19:30 | 20:30 | single (last 8h) |
