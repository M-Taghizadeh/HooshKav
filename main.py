"""
Hooshkav (هوشکاو) — Daily & Single Rich AI News Telegram Bot

Features:
1. Massive RSS Coverage (50 AI-specific sources: TechCrunch, Verge, VentureBeat, MIT, Wired, OpenAI, DeepMind, Anthropic, ArXiv, Hugging Face, etc.).
2. Zero Quota Issues: Efficient generation without heavy search grounding quota usage.
3. Multi-Provider Fallback (Gemini API -> Groq API -> OpenRouter API).
4. Mode 1 (Digest): 10 top daily news summary post.
5. Mode 2 (Single Rich Post): Detailed breaking news post with Image, Catchy Persian Title, Full Explanation, and Source Link.
6. On-Demand Telegram control for user 'tqzdh' (/digest, /single, /news).
"""

import os
import sys
import json
import re
import time
import math
import datetime as dt
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import feedparser

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# 50 AI-specific RSS feeds (all scoped to AI/ML topics only)
RSS_FEEDS = [
    # --- Major Tech News: AI sections only ---
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/"),
    ("The Verge AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
    ("Ars Technica AI", "https://arstechnica.com/ai/feed/"),
    ("Wired AI", "https://www.wired.com/feed/tag/ai/latest/rss"),
    ("MIT Technology Review AI", "https://www.technologyreview.com/topic/artificial-intelligence/feed"),
    ("IEEE Spectrum AI", "https://spectrum.ieee.org/rss/topic/artificial-intelligence"),
    ("Techmeme", "https://www.techmeme.com/feed.xml"),
    ("The Register AI", "https://www.theregister.com/emergent_tech/ai_ml_research/headlines.atom"),
    ("ZDNet AI", "https://www.zdnet.com/topic/artificial-intelligence/rss.xml"),

    # --- AI Lab & Company Blogs ---
    ("OpenAI Blog", "https://openai.com/news/rss.xml"),
    ("Google DeepMind Blog", "https://deepmind.google/blog/rss.xml"),
    ("Google AI Blog", "https://blog.research.google/feeds/posts/default/-/artificial%20intelligence"),
    ("Meta AI Blog", "https://ai.meta.com/blog/rss/"),
    ("Microsoft AI Blog", "https://blogs.microsoft.com/ai/feed/"),
    ("Anthropic News", "https://www.anthropic.com/news/rss"),
    ("Mistral AI Blog", "https://mistral.ai/news/rss.xml"),
    ("Hugging Face Blog", "https://huggingface.co/blog/feed.xml"),
    ("Cohere Blog", "https://cohere.com/blog/rss"),
    ("Scale AI Blog", "https://scale.com/blog/rss.xml"),

    # --- Research & Academic ---
    ("ArXiv CS.AI (new)", "https://rss.arxiv.org/rss/cs.AI"),
    ("ArXiv CS.LG (Machine Learning)", "https://rss.arxiv.org/rss/cs.LG"),
    ("ArXiv CS.CL (NLP/LLM)", "https://rss.arxiv.org/rss/cs.CL"),
    ("Distill.pub", "https://distill.pub/rss.xml"),
    ("AI Alignment Forum", "https://www.alignmentforum.org/feed.xml"),
    ("LessWrong AI", "https://www.lesswrong.com/feed.xml?view=tag&tagId=ai"),

    # --- AI Industry & Business ---
    ("The Information AI", "https://www.theinformation.com/feed"),
    ("Reuters AI", "https://feeds.reuters.com/reuters/technologyNews"),
    ("Financial Times AI", "https://www.ft.com/artificial-intelligence?format=rss"),
    ("Wall Street Journal AI", "https://feeds.a.dj.com/rss/RSSWSJD.xml"),

    # --- Newsletters & Aggregators ---
    ("Import AI (Jack Clark)", "https://importai.substack.com/feed"),
    ("The Rundown AI", "https://www.therundown.ai/feed"),
    ("TLDR AI", "https://tldr.tech/ai/rss"),
    ("AI Business", "https://aibusiness.com/rss.xml"),
    ("Hacker News AI", "https://hnrss.org/newest?q=AI+OR+LLM+OR+GPT+OR+Claude+OR+Gemini"),
    ("Hacker News Show AI", "https://hnrss.org/show?q=AI+OR+machine+learning"),

    # --- Specialized AI Topics ---
    ("AI Safety Newsletter", "https://newsletter.safe.ai/feed"),
    ("ML Safety Blog (Anthropic)", "https://www.anthropic.com/research/rss"),
    ("Last Week in AI", "https://lastweekin.ai/feed"),
    ("Practical AI Podcast", "https://changelog.com/practicalai/feed"),
    ("Towards Data Science", "https://towardsdatascience.com/feed"),
    ("KDnuggets", "https://www.kdnuggets.com/feed"),
    ("Analytics Vidhya", "https://www.analyticsvidhya.com/feed/"),
    ("Papers With Code", "https://paperswithcode.com/rss"),

    # --- Regional AI & Global Perspective ---
    ("South China Morning Post Tech", "https://www.scmp.com/rss/91/feed"),
    ("Nikkei Asia Tech", "https://asia.nikkei.com/rss/feed/section/tech"),
    ("AI News (ainews.com)", "https://www.ainews.com/feed"),
    ("Decrypt AI", "https://decrypt.co/feed"),
    ("SiliconAngle AI", "https://siliconangle.com/category/ai/feed/"),
    ("NVIDIA AI Blog", "https://blogs.nvidia.com/category/artificial-intelligence/feed/"),
]

DYNAMIC_SEARCH_FEEDS = [
    ("Google News: AI General",         "https://news.google.com/rss/search?q=artificial+intelligence+when:2d&hl=en-US&gl=US&ceid=US:en"),
    ("Google News: LLM & Chatbots",     "https://news.google.com/rss/search?q=OpenAI+OR+Claude+OR+Gemini+OR+LLM+OR+ChatGPT+when:2d&hl=en-US&gl=US&ceid=US:en"),
    ("Google News: AI Startups",        "https://news.google.com/rss/search?q=AI+startup+OR+AI+funding+OR+AI+acquisition+when:2d&hl=en-US&gl=US&ceid=US:en"),
    ("Google News: AI Models",          "https://news.google.com/rss/search?q=AI+model+release+OR+new+AI+model+OR+foundation+model+when:2d&hl=en-US&gl=US&ceid=US:en"),
    ("Google News: AI Policy & Safety", "https://news.google.com/rss/search?q=AI+regulation+OR+AI+safety+OR+AI+policy+OR+AI+governance+when:2d&hl=en-US&gl=US&ceid=US:en"),
    ("Google News: AI Research",        "https://news.google.com/rss/search?q=AI+research+OR+machine+learning+breakthrough+when:2d&hl=en-US&gl=US&ceid=US:en"),
]

LOOKBACK_HOURS = 24        # strict 24-hour window for digest mode
LOOKBACK_HOURS_SINGLE = 8  # single posts only cover last 8 hours (fresh news only)
MAX_PER_FEED = 5
MAX_PER_DYNAMIC_FEED = 10
TARGET_DIGEST_COUNT = 10

# Telegram caption hard limit (in characters)
TELEGRAM_CAPTION_LIMIT = 1024
# Telegram message text hard limit (in characters)
TELEGRAM_MESSAGE_LIMIT = 4096

# Auto-load .env file if present
def load_env_file(filepath=".env"):
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip()
                    if k and not os.environ.get(k):
                        os.environ[k] = v

load_env_file()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
ALLOWED_TELEGRAM_USER = os.environ.get("ALLOWED_TELEGRAM_USER", "tqzdh").strip().lstrip("@")


# ---------------------------------------------------------------------------
# Step 1: Article & Image Extraction
# ---------------------------------------------------------------------------

def extract_direct_link(entry, feed_url):
    """
    Extracts the real article URL from an RSS entry.
    Google News RSS embeds the original source URL inside the <source> tag or
    as a query param — we extract it from the entry's source url attribute.
    For non-Google feeds, just returns entry.link.
    """
    link = getattr(entry, "link", "").strip()

    if "news.google.com" in feed_url:
        # Try source tag first (most reliable for Google News)
        source = getattr(entry, "source", None)
        if source and isinstance(source, dict):
            source_url = source.get("href") or source.get("url", "")
            if source_url and source_url.startswith("http") and "news.google.com" not in source_url:
                return source_url

        # Try canonical link in entry links
        for lnk in getattr(entry, "links", []):
            if isinstance(lnk, dict):
                href = lnk.get("href", "")
                rel = lnk.get("rel", "")
                if rel == "canonical" and href.startswith("http") and "news.google.com" not in href:
                    return href

        # Fallback: keep the Google News link as-is (better than a broken redirect)
        return link

    return link


def fetch_og_image(url, timeout=8):
    """
    Fetches the Open Graph image (og:image) from an article URL.
    Used as fallback when the RSS feed does not provide an image.
    Returns image URL string or None.
    """
    try:
        resp = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (compatible; Hooshkav/1.0; +https://github.com/M-Taghizadeh/HooshKav)"},
            allow_redirects=True,
        )
        if not resp.ok:
            return None
        content_type = resp.headers.get("content-type", "")
        if "text/html" not in content_type:
            return None
        match = re.search(
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            resp.text, re.IGNORECASE
        )
        if not match:
            match = re.search(
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
                resp.text, re.IGNORECASE
            )
        if match:
            img_url = match.group(1).strip()
            if img_url.startswith("http"):
                return img_url
    except Exception:
        pass
    return None


def extract_image_url(entry):
    """Extracts high quality article image from RSS entry media tags or HTML content."""
    media_content = getattr(entry, "media_content", [])
    for media in media_content:
        if isinstance(media, dict) and media.get("url"):
            return media["url"]

    media_thumb = getattr(entry, "media_thumbnail", [])
    for thumb in media_thumb:
        if isinstance(thumb, dict) and thumb.get("url"):
            return thumb["url"]

    for link_item in getattr(entry, "links", []):
        if isinstance(link_item, dict) and link_item.get("type", "").startswith("image/"):
            return link_item.get("href")

    raw_content = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
    img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', raw_content, re.IGNORECASE)
    if img_match:
        return img_match.group(1)

    return None
    """Extracts high quality article image from RSS entry media tags or HTML content."""
    media_content = getattr(entry, "media_content", [])
    for media in media_content:
        if isinstance(media, dict) and media.get("url"):
            return media["url"]

    media_thumb = getattr(entry, "media_thumbnail", [])
    for thumb in media_thumb:
        if isinstance(thumb, dict) and thumb.get("url"):
            return thumb["url"]

    for link_item in getattr(entry, "links", []):
        if isinstance(link_item, dict) and link_item.get("type", "").startswith("image/"):
            return link_item.get("href")

    raw_content = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
    img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', raw_content, re.IGNORECASE)
    if img_match:
        return img_match.group(1)

    return None


def fetch_recent_articles(lookback_hours=None):
    if lookback_hours is None:
        lookback_hours = LOOKBACK_HOURS
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=lookback_hours)
    articles_by_source = {}
    seen_links = set()

    all_feeds = RSS_FEEDS + DYNAMIC_SEARCH_FEEDS

    for source_name, feed_url in all_feeds:
        is_dynamic = any(source_name == s for s, _ in DYNAMIC_SEARCH_FEEDS)
        per_feed_limit = MAX_PER_DYNAMIC_FEED if is_dynamic else MAX_PER_FEED
        try:
            parsed = feedparser.parse(feed_url)
        except Exception as e:
            print(f"[warn] could not fetch {source_name}: {e}")
            continue

        source_articles = []
        count = 0
        for entry in parsed.entries:
            if count >= per_feed_limit:
                break

            link = getattr(entry, "link", "").strip()
            if not link or link in seen_links:
                continue
            seen_links.add(link)

            # Extract direct article URL (handles Google News redirect links)
            direct_link = extract_direct_link(entry, feed_url)

            published = None
            for key in ("published_parsed", "updated_parsed"):
                if getattr(entry, key, None):
                    try:
                        published = dt.datetime(*entry[key][:6], tzinfo=dt.timezone.utc)
                    except Exception:
                        pass
                    break

            if published and published < cutoff:
                continue

            # Drop articles with no date (can't verify they're within 24h)
            if published is None:
                continue

            title = getattr(entry, "title", "").strip()
            summary = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
            summary_clean = re.sub(r"<[^>]+>", "", summary)[:400].strip()
            image_url = extract_image_url(entry)

            if not title:
                continue

            source_articles.append({
                "source": source_name,
                "title": title,
                "link": direct_link,
                "summary": summary_clean,
                "image_url": image_url,
                "published": published.isoformat() if published else None,
            })
            count += 1

        if source_articles:
            articles_by_source[source_name] = source_articles

    interleaved = []
    max_len = max([len(v) for v in articles_by_source.values()], default=0)
    for i in range(max_len):
        for source_name, item_list in articles_by_source.items():
            if i < len(item_list):
                interleaved.append(item_list[i])

    print(f"[info] Collected {len(interleaved)} candidate articles from {len(articles_by_source)} unique sources")

    # Enrich articles missing an image by fetching og:image from the article page
    no_image = [a for a in interleaved if not a.get("image_url")]
    if no_image:
        print(f"[info] Fetching og:image for {len(no_image)} articles without RSS image...")

        def _fetch(article):
            img = fetch_og_image(article["link"])
            return article, img

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = {pool.submit(_fetch, a): a for a in no_image}
            for future in as_completed(futures):
                article, img = future.result()
                if img:
                    article["image_url"] = img

        with_image = sum(1 for a in interleaved if a.get("image_url"))
        print(f"[info] Articles with image after og:image fetch: {with_image}/{len(interleaved)}")

    return interleaved


# ---------------------------------------------------------------------------
# Step 1b: Semantic Dedup + Mention Count
# ---------------------------------------------------------------------------

def _tokenize(text):
    """Lowercase, strip punctuation, split into word tokens."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return [t for t in text.split() if len(t) > 2]


def _tfidf_vectors(docs):
    """
    Builds TF-IDF vectors for a list of tokenized documents.
    Returns (vocab, matrix) where matrix[i] is the TF-IDF vector for docs[i].
    Uses a simple in-memory implementation — no external libraries needed.
    """
    N = len(docs)
    # Document frequency
    df = defaultdict(int)
    for tokens in docs:
        for t in set(tokens):
            df[t] += 1

    vocab = list(df.keys())
    word_idx = {w: i for i, w in enumerate(vocab)}

    matrix = []
    for tokens in docs:
        vec = [0.0] * len(vocab)
        tf_count = defaultdict(int)
        for t in tokens:
            tf_count[t] += 1
        for word, cnt in tf_count.items():
            if word in word_idx:
                tf = cnt / max(len(tokens), 1)
                idf = math.log((N + 1) / (df[word] + 1)) + 1.0
                vec[word_idx[word]] = tf * idf
        # L2 normalize
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        matrix.append([v / norm for v in vec])

    return vocab, matrix


def _cosine(vec_a, vec_b):
    """Cosine similarity between two equal-length vectors."""
    return sum(a * b for a, b in zip(vec_a, vec_b))


def deduplicate_and_score(articles, similarity_threshold=0.55):
    """
    Groups articles that cover the same story (by title similarity),
    keeps one representative per group (best: has image + most recent),
    and adds 'mention_count' = number of sources that covered the story.

    Steps:
      1. Tokenize all titles
      2. Build TF-IDF vectors
      3. Greedy clustering: each article joins the first existing cluster
         whose centroid has cosine similarity >= threshold
      4. Return one article per cluster with mention_count attached
    """
    if not articles:
        return []

    titles = [a["title"] for a in articles]
    tokenized = [_tokenize(t) for t in titles]
    _, matrix = _tfidf_vectors(tokenized)

    clusters = []          # list of list-of-indices
    centroids = []         # centroid vector per cluster

    for i, vec in enumerate(matrix):
        best_cluster = -1
        best_sim = similarity_threshold - 1e-9
        for c_idx, centroid in enumerate(centroids):
            sim = _cosine(vec, centroid)
            if sim > best_sim:
                best_sim = sim
                best_cluster = c_idx

        if best_cluster == -1:
            # New cluster
            clusters.append([i])
            centroids.append(vec[:])
        else:
            # Join existing cluster and update centroid (mean)
            clusters[best_cluster].append(i)
            members = clusters[best_cluster]
            new_centroid = [
                sum(matrix[m][d] for m in members) / len(members)
                for d in range(len(vec))
            ]
            centroids[best_cluster] = new_centroid

    deduped = []
    for cluster in clusters:
        mention_count = len(cluster)
        # Pick best representative: prefer has_image, then most recent
        def score(idx):
            a = articles[idx]
            has_image = 1 if a.get("image_url") else 0
            pub = a.get("published") or "0000"
            return (has_image, pub)

        best_idx = max(cluster, key=score)
        representative = dict(articles[best_idx])
        representative["mention_count"] = mention_count
        # Collect all unique sources that covered this story
        representative["also_covered_by"] = list({
            articles[i]["source"] for i in cluster if i != best_idx
        })
        deduped.append(representative)

    # Sort by mention_count desc, then by published desc
    deduped.sort(key=lambda a: (a["mention_count"], a.get("published") or ""), reverse=True)

    print(f"[info] After dedup: {len(articles)} → {len(deduped)} unique stories "
          f"(threshold={similarity_threshold})")
    return deduped


# ---------------------------------------------------------------------------
# Step 2: Multi-Provider LLM Integration (Gemini -> Groq -> OpenRouter)
# ---------------------------------------------------------------------------

def get_available_gemini_models():
    """Fetches supported text models directly from Google Gemini API."""
    if not GEMINI_API_KEY:
        return []
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
    try:
        resp = requests.get(url, timeout=15)
        if resp.ok:
            data = resp.json()
            valid_models = []
            for m in data.get("models", []):
                name = m.get("name", "").replace("models/", "")
                methods = m.get("supportedGenerationMethods", [])
                if "generateContent" in methods:
                    valid_models.append(name)
            if valid_models:
                text_models = [
                    m for m in valid_models
                    if not any(skip in m for skip in ["tts", "image", "clip", "computer-use", "robotics"])
                ]
                preferred = ["gemini-flash-lite-latest", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest"]
                sorted_models = [m for m in preferred if m in text_models]
                for m in text_models:
                    if m not in sorted_models:
                        sorted_models.append(m)
                return sorted_models
    except Exception as e:
        print(f"[warn] Could not list Gemini models: {e}")

    return ["gemini-2.5-flash-lite", "gemini-flash-lite-latest", "gemini-3.5-flash"]


def call_gemini(system_prompt, user_prompt):
    """Executes Gemini API call using standard token quota (without search grounding overhead)."""
    if not GEMINI_API_KEY:
        return None

    models_to_try = get_available_gemini_models()

    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"

        payload = {
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [
                {
                    "parts": [{"text": user_prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 4096,
            }
        }

        try:
            resp = requests.post(url, json=payload, timeout=60)
            if resp.ok:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    text = "".join(p.get("text", "") for p in parts).strip()
                    if text:
                        print(f"[info] Gemini API succeeded with model: {model_name}")
                        return text
            else:
                print(f"[warn] Gemini model {model_name} status {resp.status_code}: {resp.text}")
        except Exception as e:
            print(f"[warn] Gemini exception for {model_name}: {e}")

    return None


def call_groq(system_prompt, user_prompt):
    """Fallback LLM via Groq API (Llama-3.3-70B - 14,400 free requests/day)."""
    if not GROQ_API_KEY:
        return None

    print("[info] Attempting generation via Groq API (Llama 3.3 70B)...")
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 4096,
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        if resp.ok:
            data = resp.json()
            choices = data.get("choices", [])
            if choices:
                text = choices[0].get("message", {}).get("content", "").strip()
                if text:
                    print("[info] Groq API succeeded!")
                    return text
        else:
            print(f"[warn] Groq API error ({resp.status_code}): {resp.text}")
    except Exception as e:
        print(f"[warn] Groq API exception: {e}")

    return None


def call_openrouter(system_prompt, user_prompt):
    """Fallback LLM via OpenRouter API (Free Tier Models)."""
    if not OPENROUTER_API_KEY:
        return None

    print("[info] Attempting generation via OpenRouter API...")
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    models = ["meta-llama/llama-3.3-70b-instruct:free", "google/gemini-2.0-flash-lite-preview-02-05:free"]

    for model in models:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            if resp.ok:
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    text = choices[0].get("message", {}).get("content", "").strip()
                    if text:
                        print(f"[info] OpenRouter API succeeded with model: {model}")
                        return text
        except Exception as e:
            print(f"[warn] OpenRouter exception: {e}")

    return None


def generate_llm_text(system_prompt, user_prompt):
    """Unified LLM caller with robust multi-provider fallback."""
    text = call_gemini(system_prompt, user_prompt)
    if text:
        return text

    text = call_groq(system_prompt, user_prompt)
    if text:
        return text

    text = call_openrouter(system_prompt, user_prompt)
    if text:
        return text

    raise RuntimeError("All LLM providers (Gemini, Groq, OpenRouter) failed or hit quota limits.")


# ---------------------------------------------------------------------------
# Step 3: Digest Generation & Single Rich Post Generation
# ---------------------------------------------------------------------------

DIGEST_EMOJIS = ["🧠", "📋", "🛠", "🔐", "💸", "🎬", "🚀", "⚡", "🌐", "📊"]


def _extract_json_from_llm(raw: str):
    """Parses a JSON object from LLM output, tolerating markdown fences."""
    if not raw:
        return None

    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None


def _inject_link_in_summary(summary: str, word: str, link: str) -> str:
    """Ensures each digest item contains a clickable link to the source article."""
    if not link or not link.startswith("http"):
        return summary

    if re.search(rf'href=["\']{re.escape(link)}["\']', summary):
        return summary

    word = (word or "").strip()
    if word and word in summary:
        return summary.replace(word, f'<a href="{link}">{word}</a>', 1)

    return f'{summary} — <a href="{link}">مطالعه خبر</a>'


def _build_digest_html(items: list, channel_footer: str = "") -> str:
    """Builds the final Telegram digest HTML with guaranteed links on every item."""
    lines = ["<b>مهم‌ترین‌های ۲۴ ساعت اخیر هوش مصنوعی</b>", ""]

    for i, item in enumerate(items):
        emoji = DIGEST_EMOJIS[i % len(DIGEST_EMOJIS)]
        summary = _inject_link_in_summary(
            item.get("summary", "").strip(),
            item.get("highlight_word", ""),
            item.get("link", ""),
        )
        lines.append(f"{emoji} <b>خبر {i + 1}:</b> {summary}")
        lines.append("")

    if channel_footer:
        lines.append(channel_footer.strip())

    return "\n".join(lines).strip()


def _fallback_digest_items(articles: list, count: int = TARGET_DIGEST_COUNT) -> list:
    """Fallback digest items when LLM JSON parsing fails."""
    items = []
    for article in articles[:count]:
        title = article.get("title", "").strip()
        source = article.get("source", "").strip()
        summary = title
        if source:
            summary = f"{title} ({source})"
        items.append({
            "link": article.get("link", ""),
            "summary": summary,
            "highlight_word": source or title.split()[0] if title else "منبع",
        })
    return items


def _parse_digest_items(raw: str, articles: list) -> list:
    """
    Parses LLM JSON output into validated digest items.
    Falls back to top articles by mention_count when parsing fails.
    """
    link_to_article = {a["link"]: a for a in articles if a.get("link")}
    data = _extract_json_from_llm(raw)

    if not isinstance(data, dict):
        print("[warn] Digest JSON parse failed — using fallback items")
        return _fallback_digest_items(articles)

    raw_items = data.get("items", [])
    if not isinstance(raw_items, list):
        print("[warn] Digest JSON missing items array — using fallback items")
        return _fallback_digest_items(articles)

    valid_items = []
    seen_links = set()

    for item in raw_items:
        if not isinstance(item, dict):
            continue

        link = (item.get("link") or "").strip()
        summary = (item.get("summary") or "").strip()
        highlight_word = (item.get("highlight_word") or "").strip()

        if not link or link not in link_to_article or link in seen_links:
            continue
        if not summary:
            article = link_to_article[link]
            summary = article.get("title", "").strip() or "خبر مهم هوش مصنوعی"

        valid_items.append({
            "link": link,
            "summary": summary,
            "highlight_word": highlight_word,
        })
        seen_links.add(link)

        if len(valid_items) >= TARGET_DIGEST_COUNT:
            break

    if len(valid_items) < TARGET_DIGEST_COUNT:
        print(f"[warn] Only {len(valid_items)} valid digest items parsed — filling from top articles")
        for article in articles:
            link = article.get("link", "")
            if not link or link in seen_links:
                continue
            valid_items.append({
                "link": link,
                "summary": article.get("title", "").strip() or "خبر مهم هوش مصنوعی",
                "highlight_word": article.get("source", "").strip() or "منبع",
            })
            seen_links.add(link)
            if len(valid_items) >= TARGET_DIGEST_COUNT:
                break

    return valid_items[:TARGET_DIGEST_COUNT]


def generate_daily_digest(articles):
    """
    Generates the daily digest post with guaranteed source links on every item.

    Returns: digest_text (str)
    """
    compact = []
    for a in articles:
        compact.append({
            "title": a["title"],
            "source": a["source"],
            "link": a["link"],
            "summary": a.get("summary", "")[:150],
            "mention_count": a.get("mention_count", 1),
            "also_covered_by": a.get("also_covered_by", []),
        })

    articles_json = json.dumps(compact, ensure_ascii=False, indent=2)
    channel_footer = f"\n\n{TELEGRAM_CHAT_ID}" if TELEGRAM_CHAT_ID else ""

    system_prompt = (
        "تو یک روزنامه‌نگار و فیلترکننده ارشد اخبار فناوری و هوش مصنوعی هستی. "
        f"وظیفه تو انتخاب {TARGET_DIGEST_COUNT} خبر مهم و نوشتن خلاصه فارسی برای هر کدام است."
    )

    user_prompt = f"""
از بین مقالات ورودی زیر (که از بیش از ۵۰ منبع مختلف جهانی جمع‌آوری و پردازش شده‌اند):

نکته مهم: هر مقاله یک فیلد «mention_count» دارد که نشان می‌دهد چند منبع مختلف همین خبر را پوشش داده‌اند.
خبری که mention_count بالاتری دارد اهمیت بیشتری دارد و باید در اولویت انتخاب قرار گیرد.

بالضبط {TARGET_DIGEST_COUNT} خبر بسیار مهم و متنوع هوش مصنوعی را انتخاب کن.

خروجی فقط یک JSON معتبر باشد (بدون ```json و بدون توضیح اضافه) با این ساختار:

{{
  "items": [
    {{
      "link": "لینک دقیق مقاله از فیلد link ورودی",
      "summary": "خلاصه کوتاه، روان و کاربردی خبر به فارسی (بدون HTML)",
      "highlight_word": "یک کلمه کلیدی از summary که باید لینک‌دار شود"
    }}
  ]
}}

قوانین الزامی:
- دقیقاً {TARGET_DIGEST_COUNT} آیتم در items باشد.
- فیلد link باید عیناً از فیلد link مقالات ورودی کپی شود.
- highlight_word باید دقیقاً یکی از کلمات داخل summary باشد.
- اخبار با mention_count بالاتر را در اولویت قرار بده.
- اخبار را از منابع متنوع انتخاب کن.
- summary نباید HTML یا لینک داشته باشد.

مقالات ورودی:
{articles_json}
"""

    raw = generate_llm_text(system_prompt, user_prompt)
    items = _parse_digest_items(raw, articles)
    return _build_digest_html(items, channel_footer)


def select_best_article_for_single_post(articles):
    """
    Uses the LLM to select the most newsworthy article that HAS an image.
    Falls back to first article with an image if LLM fails.
    Returns None if no articles have an image.
    """
    # Only consider articles that have an image
    candidates_with_image = [a for a in articles if a.get("image_url")]

    if not candidates_with_image:
        print("[warn] No articles with images found — skipping single post")
        return None

    candidates = []
    for i, a in enumerate(candidates_with_image):
        candidates.append({
            "index": i,
            "title": a.get("title", ""),
            "source": a.get("source", ""),
            "summary": a.get("summary", "")[:150],
            "mention_count": a.get("mention_count", 1),
        })

    candidates_json = json.dumps(candidates, ensure_ascii=False, indent=2)

    system_prompt = (
        "تو یک سردبیر خبر هوش مصنوعی هستی. وظیفه تو انتخاب مهم‌ترین و جذاب‌ترین خبر روز "
        "برای یک پست تکی تلگرامی است."
    )

    user_prompt = f"""
از لیست مقالات زیر، فقط یک مقاله را انتخاب کن که:
۱. مهم‌ترین و تاثیرگذارترین خبر هوش مصنوعی روز باشد.
۲. mention_count بالاتر نشان‌دهنده اهمیت بیشتر است — آن را در اولویت قرار بده.
۳. در صورت امکان has_image: true داشته باشد.

خروجی فقط یک عدد صحیح باشد: index مقاله انتخابی. هیچ توضیح دیگری ندهید.

مقالات:
{candidates_json}
"""

    try:
        result = generate_llm_text(system_prompt, user_prompt).strip()
        match = re.search(r"\d+", result)
        if match:
            idx = int(match.group())
            if 0 <= idx < len(candidates_with_image):
                print(f"[info] LLM selected article index {idx}: {candidates_with_image[idx].get('title', '')[:80]}")
                return candidates_with_image[idx]
    except Exception as e:
        print(f"[warn] LLM article selection failed: {e}, using fallback")

    return candidates_with_image[0]


def generate_single_rich_post(articles):
    """Generates a detailed, rich single-news post with title, full analysis, image, and link."""
    selected_article = select_best_article_for_single_post(articles)

    if not selected_article:
        return None, None

    article_json = json.dumps(selected_article, ensure_ascii=False, indent=2)
    channel_footer = f"\n\n{TELEGRAM_CHAT_ID}" if TELEGRAM_CHAT_ID else ""

    system_prompt = (
        "تو یک سردبیر خبر هوش مصنوعی هستی. وظیفه تو ساخت یک پست تلگرامی بسیار جذاب، کامل، "
        "خواندنی و تحلیل‌شده درباره مهم‌ترین خبر روز است."
    )

    user_prompt = f"""
درباره مقاله زیر، یک پست کامل، شکیل و جذاب به زبان فارسی بنویس.

ساختار خروجی:
🔥 <b>عنوان جذاب و داغ فارسی</b>

یک یا دو پاراگراف توضیحات روان و کامل درباره این خبر، اهمیت آن و پیامدهای آن در صنعت هوش مصنوعی به فارسی.

منبع: {selected_article.get('source')} — <a href="{selected_article.get('link')}">مطالعه مقاله کامل</a>
{channel_footer}

قوانین:
- خروجی را مستقیماً از عنوان شروع کن (بدون هیچ مقدمه انگلیسی یا توضیحات اضافه).
- عنوان جذاب با ایموجی شروع شود.
- متن توضیحات بین ۱۵۰ تا ۲۵۰ کلمه و بسیار خوانا باشد.
- لینک منبع دقیقاً به صورت HTML <a href="...">مطالعه مقاله کامل</a> باشد.
- فقط متن نهایی را بدون توضیحات اضافه و بدون ```html بده.

اطلاعات مقاله:
{article_json}
"""

    post_text = generate_llm_text(system_prompt, user_prompt)
    image_url = selected_article.get("image_url")

    return post_text, image_url


# ---------------------------------------------------------------------------
# Step 4: HTML Sanitization Helpers
# ---------------------------------------------------------------------------

def safe_truncate_html(text, max_chars):
    """
    Truncates text to max_chars without breaking open HTML tags.
    Closes any unclosed tags after truncation.
    """
    if len(text) <= max_chars:
        return text

    truncated = text[:max_chars]

    # Remove any incomplete opening tag at the end (e.g. "<a hr")
    truncated = re.sub(r"<[^>]*$", "", truncated)

    # Track open tags and close them
    open_tags = re.findall(r"<([a-zA-Z][a-zA-Z0-9]*)\b[^>]*>", truncated)
    close_tags = re.findall(r"</([a-zA-Z][a-zA-Z0-9]*)>", truncated)

    # Build stack of unclosed tags
    stack = []
    for tag in open_tags:
        tag_lower = tag.lower()
        if tag_lower not in ("br", "img", "hr", "input"):
            stack.append(tag_lower)
    for tag in close_tags:
        tag_lower = tag.lower()
        if tag_lower in stack:
            stack.remove(tag_lower)

    # Close unclosed tags in reverse order
    for tag in reversed(stack):
        truncated += f"</{tag}>"

    return truncated.strip()


def clean_html_for_telegram(text, post_type="digest"):
    """
    Cleans up LLM text, strips preambles, balances tags, and converts markdown to HTML.
    post_type: 'digest' or 'single' — controls how preamble stripping works.
    """
    if not text:
        return text

    # Strip markdown code fences
    text = re.sub(r"^```html\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE).strip()

    if post_type == "digest":
        # For digest: strip everything before the expected header
        title_match = re.search(r"(<b>\s*مهم‌?ترین.*)", text, flags=re.DOTALL | re.IGNORECASE)
        if title_match:
            text = title_match.group(1)
        else:
            title_match = re.search(r"(مهم‌?ترین.*)", text, flags=re.DOTALL | re.IGNORECASE)
            if title_match:
                text = title_match.group(1)
    else:
        # For single posts: strip any plain-text or English preamble before the first emoji/bold tag
        # Look for start of actual post content (emoji or <b> tag)
        content_match = re.search(
            r"([🔥🚀🧠📋🛠🔐💸🎬⚡🌐🤖💡🔬📡🏆]|<b>)",
            text
        )
        if content_match:
            text = text[content_match.start():]

    # Convert markdown links [title](url) to HTML <a href="url">title</a>
    text = re.sub(r"\[([^\]]+)\]\((https?://[^\)]+)\)", r'<a href="\2">\1</a>', text)

    # Remove unsupported HTML tags, replace with newlines
    text = re.sub(r"</?(?:p|div|span|ul|ol|li|br|h[1-6])[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    balanced_lines = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            balanced_lines.append("")
            continue

        # Remove incomplete <a> tags at end of line
        line = re.sub(r'<a\s+href="[^"]*$', "", line, flags=re.IGNORECASE)

        # Balance <a> tags
        open_a = len(re.findall(r"<a\b[^>]*>", line))
        close_a = line.count("</a>")
        if open_a > close_a:
            line += "</a>" * (open_a - close_a)
        elif close_a > open_a:
            line = re.sub(r"</a>", "", line, count=close_a - open_a)

        # Balance <b> tags
        open_b = line.count("<b>")
        close_b = line.count("</b>")
        if open_b > close_b:
            line += "</b>" * (open_b - close_b)
        elif close_b > open_b:
            line = re.sub(r"</b>", "", line, count=close_b - open_b)

        # Balance <i> tags
        open_i = line.count("<i>")
        close_i = line.count("</i>")
        if open_i > close_i:
            line += "</i>" * (open_i - close_i)
        elif close_i > open_i:
            line = re.sub(r"</i>", "", line, count=close_i - open_i)

        balanced_lines.append(line)

    # Remove leading/trailing blank lines, collapse internal multiple blanks
    result = "\n".join(balanced_lines)
    result = re.sub(r"\n{3,}", "\n\n", result).strip()
    return result


# ---------------------------------------------------------------------------
# Step 5: Telegram Dispatcher with Retry & Rate-Limit Handling
# ---------------------------------------------------------------------------

def _telegram_request(method, payload, retries=3):
    """
    Makes a Telegram Bot API call with retry logic for rate-limit (429) errors.
    Returns the response object on success, raises on persistent failure.
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"
    last_resp = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(url, json=payload, timeout=30)
            last_resp = resp
            if resp.ok:
                return resp
            if resp.status_code == 429:
                retry_after = resp.json().get("parameters", {}).get("retry_after", 5)
                print(f"[warn] Telegram rate-limited (429). Retrying after {retry_after}s (attempt {attempt}/{retries})...")
                time.sleep(retry_after)
                continue
            # Non-retryable error — return immediately
            return resp
        except requests.exceptions.RequestException as e:
            print(f"[warn] Telegram request exception on attempt {attempt}/{retries}: {e}")
            if attempt < retries:
                time.sleep(2 ** attempt)  # exponential backoff
    return last_resp


def send_telegram_post(chat_id, html_text, image_url=None, post_type="digest"):
    """Sends text or photo post with caption to Telegram, with retry and safe truncation."""
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is not set.")

    cleaned_text = clean_html_for_telegram(html_text, post_type=post_type)

    if image_url:
        caption = safe_truncate_html(cleaned_text, TELEGRAM_CAPTION_LIMIT)
        resp = _telegram_request("sendPhoto", {
            "chat_id": chat_id,
            "photo": image_url,
            "caption": caption,
            "parse_mode": "HTML",
        })
        if resp is not None and resp.ok:
            print(f"[info] Photo message successfully sent to Telegram: {chat_id}")
            return
        else:
            status = resp.status_code if resp is not None else "timeout"
            print(f"[warn] sendPhoto failed ({status}), falling back to sendMessage")

    # Send as text message (with HTML)
    text_body = safe_truncate_html(cleaned_text, TELEGRAM_MESSAGE_LIMIT)
    resp = _telegram_request("sendMessage", {
        "chat_id": chat_id,
        "text": text_body,
        "parse_mode": "HTML",
        "disable_web_page_preview": not bool(image_url),
    })

    if resp is None or not resp.ok:
        status = resp.status_code if resp is not None else "timeout"
        print(f"[warn] Telegram HTML sendMessage failed ({status}), retrying as plain text")
        plain_text = re.sub(r"<[^>]+>", "", cleaned_text)[:TELEGRAM_MESSAGE_LIMIT]
        resp_fallback = _telegram_request("sendMessage", {
            "chat_id": chat_id,
            "text": plain_text,
            "disable_web_page_preview": True,
        })
        if resp_fallback is None or not resp_fallback.ok:
            err = resp_fallback.text if resp_fallback is not None else "no response"
            raise RuntimeError(f"All Telegram send attempts failed: {err}")

    print(f"[info] Text message successfully sent to Telegram: {chat_id}")


# ---------------------------------------------------------------------------
# Step 6: On-Demand Telegram Command Handler
# ---------------------------------------------------------------------------

def check_and_handle_on_demand_requests():
    """
    Checks for Telegram commands from the authorized user (/news, /digest, /single).
    Uses offset to avoid reprocessing already-seen updates.
    Returns list of (chat_id, mode) tuples to handle, or empty list.
    """
    if not TELEGRAM_BOT_TOKEN:
        return []

    try:
        # First call: fetch all pending updates to find the latest offset
        resp = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates",
            timeout=15,
        )
        if not resp.ok:
            return []

        data = resp.json()
        updates = data.get("result", [])

        if not updates:
            return []

        on_demand_chats = []
        max_update_id = 0

        for update in updates:
            update_id = update.get("update_id", 0)
            if update_id > max_update_id:
                max_update_id = update_id

            msg = update.get("message", {})
            sender = msg.get("from", {})
            username = (sender.get("username") or "").strip().lstrip("@")
            chat_id = msg.get("chat", {}).get("id")
            text = (msg.get("text") or "").strip().lower()

            if text in ["/news", "/digest", "/single", "/latest", "/start", "اخبار", "خبر", "پست"]:
                if username.lower() == ALLOWED_TELEGRAM_USER.lower():
                    mode = "single" if text in ["/single", "پست"] else "digest"
                    print(f"[info] Authorized command '{text}' received from @{username} (mode: {mode})")
                    on_demand_chats.append((chat_id, mode))
                else:
                    deny_text = (
                        f"⛔️ <b>دسترسی غیرمجاز</b>\n"
                        f"این ربات فقط توسط کاربر @{ALLOWED_TELEGRAM_USER} قابل فراخوانی است."
                    )
                    try:
                        send_telegram_post(chat_id, deny_text)
                    except Exception:
                        pass

        # Acknowledge all processed updates so they won't appear again
        if max_update_id > 0:
            requests.get(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates",
                params={"offset": max_update_id + 1, "limit": 1},
                timeout=15,
            )
            print(f"[info] Acknowledged Telegram updates up to update_id={max_update_id}")

        return on_demand_chats

    except Exception as e:
        print(f"[warn] Could not check Telegram updates: {e}")
        return []


# ---------------------------------------------------------------------------
# Main Routine
# ---------------------------------------------------------------------------

def main():
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "digest"
    print(f"=== Hooshkav AI News Bot (Execution Mode: {mode}) ===")

    on_demand_requests = check_and_handle_on_demand_requests()

    # digest uses 24h window; single uses 8h to avoid repeating morning digest stories
    lookback = LOOKBACK_HOURS if mode == "digest" else LOOKBACK_HOURS_SINGLE
    articles = fetch_recent_articles(lookback_hours=lookback)

    if not articles:
        print(f"[warn] No articles found in the last {lookback} hours.")
        return

    # Semantic dedup + mention_count scoring
    articles = deduplicate_and_score(articles)

    targets = set()
    if TELEGRAM_CHAT_ID:
        targets.add(TELEGRAM_CHAT_ID)

    if mode == "digest":
        print("[info] Generating Daily Digest...")

        digest_text = generate_daily_digest(articles)

        if digest_text:
            for chat in targets:
                send_telegram_post(chat, digest_text, post_type="digest")

        for chat_id, req_mode in on_demand_requests:
            if req_mode == "digest" and digest_text:
                send_telegram_post(chat_id, digest_text, post_type="digest")

    else:
        # single mode: just one rich post (for manual/on-demand use)
        print("[info] Generating Single Rich News Post...")
        post_text, image_url = generate_single_rich_post(articles)
        if post_text:
            for chat in targets:
                send_telegram_post(chat, post_text, image_url, post_type="single")

        for chat_id, req_mode in on_demand_requests:
            if post_text:
                send_telegram_post(chat_id, post_text, image_url, post_type="single")

    print("=== Job Completed Successfully ===")


if __name__ == "__main__":
    main()
