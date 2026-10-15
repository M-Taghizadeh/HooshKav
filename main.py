"""
Hooshkav (هوشکاو) — AI News + Educational Telegram Bot

Features:
1. Morning digest: top AI news in Persian (text only).
2. Daytime educational posts from real tutorial sources (Medium, Kaggle, TDS, …).
3. Multi-Provider Fallback (Gemini -> Groq -> OpenRouter).
4. Admin publish-mode control via Telegram (/mode news|both|edu).
5. On-demand commands: /digest, /edu, /single, /mode.
"""

import os
import sys
import json
import re
import time
import math
import hashlib
import subprocess
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

# Educational / tutorial sources for daytime posts (separate from news digest)
EDU_RSS_FEEDS = [
    ("Towards Data Science", "https://towardsdatascience.com/feed"),
    ("Medium: Artificial Intelligence", "https://medium.com/feed/tag/artificial-intelligence"),
    ("Medium: Machine Learning", "https://medium.com/feed/tag/machine-learning"),
    ("Medium: Python", "https://medium.com/feed/tag/python"),
    ("Medium: Large Language Models", "https://medium.com/feed/tag/large-language-models"),
    ("Medium: LangChain", "https://medium.com/feed/tag/langchain"),
    ("Kaggle Blog", "https://medium.com/feed/kaggle-blog"),
    ("Hugging Face Blog", "https://huggingface.co/blog/feed.xml"),
    ("Real Python", "https://realpython.com/atom.xml"),
    ("KDnuggets", "https://www.kdnuggets.com/feed"),
    ("Analytics Vidhya", "https://www.analyticsvidhya.com/feed/"),
    ("PyImageSearch", "https://pyimagesearch.com/feed/"),
    ("Google News: AI Tutorials", "https://news.google.com/rss/search?q=AI+OR+LLM+OR+Python+(tutorial+OR+guide+OR+%22how+to%22)+when:7d&hl=en-US&gl=US&ceid=US:en"),
    ("Google News: ScienceDirect ML", "https://news.google.com/rss/search?q=site:sciencedirect.com+(machine+learning+OR+deep+learning+OR+LLM)+when:30d&hl=en-US&gl=US&ceid=US:en"),
]

LOOKBACK_HOURS = 24        # strict 24-hour window for digest mode
LOOKBACK_HOURS_SINGLE = 8  # single posts only cover last 8 hours (fresh news only)
LOOKBACK_HOURS_EDU = 72    # educational content ages slower
MAX_PER_FEED = 5
MAX_PER_DYNAMIC_FEED = 10
MAX_PER_EDU_FEED = 6
TARGET_DIGEST_COUNT = 5

PUBLISH_MODES = ("both", "news", "edu")
PUBLISH_MODE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "publish_mode.json")

EDU_TITLE_SIGNALS = [
    "how to", "tutorial", "guide", "explained", "walkthrough", "hands-on",
    "with python", "in python", "for beginners", "step by step", "step-by-step",
    "intro to", "introduction", "deep dive", "build a", "building", "learn",
    "rag", "fine-tun", "prompt", "langchain", "llamaindex", "transformers",
    "openai", "ollama", "fastapi", "pytorch", "tensorflow", "scikit",
    "pandas", "numpy", "jupyter", "dataset", "notebook", "llm", "embedding",
]
EDU_TITLE_BLOCKLIST = [
    "raises $", "funding", "acquires", "acquisition", "ipo", "layoffs",
    "stock", "shares surge", "lawsuit", "sues ",
]

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


def _is_edu_candidate(title: str) -> bool:
    """Heuristic: prefer tutorial/how-to titles, drop corporate news."""
    t = (title or "").lower()
    if any(b in t for b in EDU_TITLE_BLOCKLIST):
        return False
    # Always keep known educational publishers even without signal words
    return True


def _edu_relevance_score(article: dict) -> float:
    title = (article.get("title") or "").lower()
    summary = (article.get("summary") or "").lower()
    blob = f"{title} {summary}"
    score = 0.0
    for sig in EDU_TITLE_SIGNALS:
        if sig in blob:
            score += 1.5
    source = (article.get("source") or "").lower()
    if any(k in source for k in ("towards", "kaggle", "real python", "medium", "kdnuggets", "huggingface", "analytics")):
        score += 2.0
    if any(b in title for b in EDU_TITLE_BLOCKLIST):
        score -= 5.0
    return score


def fetch_edu_articles(lookback_hours=None):
    """
    Fetches educational/tutorial articles from EDU_RSS_FEEDS.
    Allows undated entries (common on Medium) within per-feed cap.
    """
    if lookback_hours is None:
        lookback_hours = LOOKBACK_HOURS_EDU
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=lookback_hours)
    articles = []
    seen_links = set()

    for source_name, feed_url in EDU_RSS_FEEDS:
        try:
            parsed = feedparser.parse(feed_url)
        except Exception as e:
            print(f"[warn] edu feed failed {source_name}: {e}")
            continue

        count = 0
        for entry in parsed.entries:
            if count >= MAX_PER_EDU_FEED:
                break

            link = getattr(entry, "link", "").strip()
            if not link or link in seen_links:
                continue

            direct_link = extract_direct_link(entry, feed_url)
            if not direct_link or direct_link in seen_links:
                continue

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

            title = getattr(entry, "title", "").strip()
            if not title or not _is_edu_candidate(title):
                continue

            summary = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
            summary_clean = re.sub(r"<[^>]+>", "", summary)[:500].strip()

            seen_links.add(link)
            seen_links.add(direct_link)
            articles.append({
                "source": source_name,
                "title": title,
                "link": direct_link,
                "summary": summary_clean,
                "published": published.isoformat() if published else None,
            })
            count += 1

    articles.sort(key=_edu_relevance_score, reverse=True)
    print(f"[info] Collected {len(articles)} educational candidates from {len(EDU_RSS_FEEDS)} edu feeds")
    return articles


def select_edu_article(articles: list, slot: int = 0):
    """
    Picks one educational article for the given daily slot.
    Uses date+slot hashing so noon/evening posts differ and rotate across days.
    """
    if not articles:
        return None

    # Prefer items with educational signal words
    scored = [(a, _edu_relevance_score(a)) for a in articles]
    scored = [x for x in scored if x[1] > 0] or scored
    pool = [a for a, _ in scored[:40]]

    day_key = dt.date.today().isoformat()
    seed = int(hashlib.md5(f"{day_key}:{slot}".encode()).hexdigest(), 16)
    # Rotate through pool so slot 0 and slot 1 diverge
    idx = (seed + slot * 7) % len(pool)
    chosen = pool[idx]

    # Avoid same link for both slots on the same day when possible
    if slot > 0 and len(pool) > 1:
        alt_seed = int(hashlib.md5(f"{day_key}:0".encode()).hexdigest(), 16)
        first_idx = (alt_seed + 0) % len(pool)
        if pool[first_idx].get("link") == chosen.get("link"):
            chosen = pool[(idx + 1) % len(pool)]

    print(f"[info] Edu slot {slot} selected: {chosen.get('title', '')[:80]}")
    return chosen


# ---------------------------------------------------------------------------
# Publish mode (admin-controlled: both | news | edu)
# ---------------------------------------------------------------------------

def load_publish_mode() -> str:
    try:
        with open(PUBLISH_MODE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        mode = (data.get("mode") or "both").strip().lower()
        if mode in PUBLISH_MODES:
            return mode
    except Exception as e:
        print(f"[warn] Could not read publish mode file: {e}")
    return "both"


def save_publish_mode(mode: str) -> bool:
    mode = (mode or "").strip().lower()
    if mode not in PUBLISH_MODES:
        return False

    os.makedirs(os.path.dirname(PUBLISH_MODE_FILE), exist_ok=True)
    with open(PUBLISH_MODE_FILE, "w", encoding="utf-8") as f:
        json.dump({"mode": mode}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"[info] Publish mode saved: {mode}")

    # Persist across GitHub Actions runs by committing the config file
    if os.environ.get("GITHUB_ACTIONS") == "true":
        try:
            rel = os.path.relpath(PUBLISH_MODE_FILE)
            subprocess.run(["git", "add", rel], check=True, capture_output=True)
            diff = subprocess.run(["git", "diff", "--cached", "--quiet"])
            if diff.returncode != 0:
                subprocess.run(
                    [
                        "git",
                        "-c", "user.name=hooshkav-bot",
                        "-c", "user.email=hooshkav-bot@users.noreply.github.com",
                        "commit", "-m", f"chore: set publish mode to {mode}",
                    ],
                    check=True,
                    capture_output=True,
                )
                subprocess.run(["git", "push"], check=True, capture_output=True)
                print("[info] Publish mode committed and pushed to repo")
            else:
                print("[info] Publish mode unchanged on disk — no commit")
        except Exception as e:
            print(f"[warn] Could not persist publish mode via git: {e}")

    return True


def publish_mode_label(mode: str) -> str:
    return {
        "both": "خبر + آموزش",
        "news": "فقط خبر",
        "edu": "فقط آموزش",
    }.get(mode, mode)


def mode_allows_job(publish_mode: str, job: str) -> bool:
    """Whether a scheduled job (digest|edu) should run for the current publish mode."""
    if publish_mode == "both":
        return True
    if publish_mode == "news":
        return job == "digest"
    if publish_mode == "edu":
        return job == "edu"
    return True


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

    # Sort by mention_count desc, then has_image, then by published desc
    deduped.sort(
        key=lambda a: (
            a["mention_count"],
            1 if a.get("image_url") else 0,
            a.get("published") or "",
        ),
        reverse=True,
    )

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

# Category-based emojis for digest items (matched by LLM to topic)
DIGEST_EMOJIS = ["🧠", "📋", "🛠", "🔐", "💸", "🎬", "🚀", "⚡", "🌐", "📊"]

# Thematic emojis for digest — LLM picks the best fit per news item
CATEGORY_EMOJIS = {
    "model":      "🤖",   # new AI model / LLM release
    "research":   "🔬",   # research paper / academic
    "tool":       "🛠",   # developer tool / SDK / API
    "business":   "💰",   # funding / acquisition / startup
    "safety":     "🔐",   # AI safety / regulation / policy
    "education":  "🎓",   # education / tutorial / learning
    "product":    "🚀",   # product launch / feature release
    "data":       "📊",   # dataset / benchmark
    "hardware":   "⚡",   # chip / hardware / infrastructure
    "society":    "⚖️",   # ethics / society / law
    "other":      "📌",   # fallback
}


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


def _is_mostly_persian(text: str, max_ascii_ratio: float = 0.45) -> bool:
    """True if alphabetic characters are mostly non-ASCII (Persian/Arabic script)."""
    if not text or not text.strip():
        return False
    ascii_letters = sum(1 for c in text if c.isascii() and c.isalpha())
    total_letters = sum(1 for c in text if c.isalpha())
    if total_letters == 0:
        return False
    return (ascii_letters / total_letters) <= max_ascii_ratio


def _summarize_articles_in_persian(articles: list) -> dict:
    """
    Translates/summarizes a batch of English articles into short Persian digests.
    Returns {link: {"summary": str, "category": str}} for successfully translated items.
    """
    if not articles:
        return {}

    compact = []
    for a in articles:
        compact.append({
            "link": a.get("link", ""),
            "title": a.get("title", ""),
            "source": a.get("source", ""),
            "summary": (a.get("summary") or "")[:200],
        })

    articles_json = json.dumps(compact, ensure_ascii=False, indent=2)

    system_prompt = (
        "تو مترجم و خلاصه‌نویس خبر هوش مصنوعی برای مخاطبان فارسی‌زبان هستی. "
        "فقط JSON معتبر برگردان. خلاصه‌ها باید ۱۰۰٪ فارسی روان باشند."
    )

    user_prompt = f"""
برای هر مقاله زیر یک خلاصه کوتاه فارسی بنویس.

خروجی فقط JSON معتبر (بدون ```):
{{
  "items": [
    {{
      "link": "همان لینک ورودی",
      "summary": "۱ تا ۲ جمله فارسی روان (۳۰ تا ۵۰ کلمه) — هیچ جمله انگلیسی مجاز نیست",
      "category": "یکی از: model | research | tool | business | safety | education | product | data | hardware | society | other"
    }}
  ]
}}

قوانین:
- برای تک‌تک مقالات ورودی دقیقاً یک آیتم برگردان
- link را عیناً کپی کن
- summary کاملاً فارسی باشد؛ فقط نام محصولات/شرکت‌ها (مثل GPT-4، Claude، Workday) می‌تواند انگلیسی بماند

مقالات:
{articles_json}
"""

    try:
        raw = generate_llm_text(system_prompt, user_prompt)
    except Exception as e:
        print(f"[warn] Persian re-translate batch failed: {e}")
        return {}

    data = _extract_json_from_llm(raw)
    if not isinstance(data, dict):
        return {}

    result = {}
    for item in data.get("items", []) or []:
        if not isinstance(item, dict):
            continue
        link = (item.get("link") or "").strip()
        summary = (item.get("summary") or "").strip()
        category = (item.get("category") or "other").strip().lower()
        if not link or not summary or not _is_mostly_persian(summary):
            continue
        result[link] = {"summary": summary, "category": category}

    print(f"[info] Persian re-translate: {len(result)}/{len(articles)} items OK")
    return result


def _build_digest_html(items: list, channel_footer: str = "") -> str:
    """
    Builds the final Telegram digest as HTML (parse_mode=HTML).

    Output format — link is hidden inside the summary text (clickable):

        مهم‌ترین‌های ۲۴ ساعت اخیر هوش مصنوعی

         🎓 خبر ۱: <a href="https://...">خلاصه فارسی خبر ...</a>

         🤖 خبر ۲: <a href="https://...">خلاصه فارسی خبر ...</a>

        @channel
    """
    # Persian digit map
    persian_digits = {"0": "۰", "1": "۱", "2": "۲", "3": "۳", "4": "۴",
                      "5": "۵", "6": "۶", "7": "۷", "8": "۸", "9": "۹"}

    def to_persian_num(n: int) -> str:
        return "".join(persian_digits.get(d, d) for d in str(n))

    lines = ["<b>مهم‌ترین‌های ۲۴ ساعت اخیر هوش مصنوعی</b>", ""]

    for i, item in enumerate(items):
        # Pick emoji based on category supplied by LLM
        category = item.get("category", "").lower().strip()
        emoji = CATEGORY_EMOJIS.get(category, DIGEST_EMOJIS[i % len(DIGEST_EMOJIS)])

        summary = item.get("summary", "").strip()
        link    = item.get("link", "").strip()
        num     = to_persian_num(i + 1)

        # Link is on the number only — user clicks "خبر ۱" to open article
        if link and link.startswith("http"):
            line = f' {emoji} <a href="{link}"><b>خبر {num}</b></a>: {summary}'
        else:
            line = f" {emoji} <b>خبر {num}:</b> {summary}"

        lines.append(line)
        lines.append("")

    if channel_footer:
        lines.append(channel_footer.strip())

    return "\n".join(lines).strip()


def _fallback_digest_items(articles: list, count: int = TARGET_DIGEST_COUNT) -> list:
    """Fallback digest items when LLM JSON parsing fails — always Persian summaries."""
    candidates = [a for a in articles if a.get("link")][:count]
    if not candidates:
        return []

    translated = _summarize_articles_in_persian(candidates)
    items = []
    for article in candidates:
        link = article.get("link", "")
        tr = translated.get(link)
        if tr:
            items.append({
                "link": link,
                "summary": tr["summary"],
                "category": tr.get("category", "other"),
            })
        else:
            # Last resort: skip English titles entirely rather than posting them
            print(f"[warn] Skipping untranslated fallback item: {article.get('title', '')[:60]}")
    return items


def _parse_digest_items(raw: str, articles: list) -> list:
    """
    Parses LLM JSON output into validated digest items.
    Falls back to top articles by mention_count when parsing fails.
    Never inserts English titles into the digest — re-translates instead.
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
    needs_retranslate = []  # English summaries that still have a valid link

    for item in raw_items:
        if not isinstance(item, dict):
            continue

        link = (item.get("link") or "").strip()
        summary = (item.get("summary") or "").strip()
        category = (item.get("category") or "other").strip().lower()

        if not link or link not in link_to_article or link in seen_links:
            continue

        if not summary or not _is_mostly_persian(summary):
            ascii_letters = sum(1 for c in (summary or "") if c.isascii() and c.isalpha())
            total_letters = sum(1 for c in (summary or "") if c.isalpha()) or 1
            print(
                f"[warn] Summary appears non-Persian "
                f"(ASCII ratio={ascii_letters/total_letters:.2f}), will re-translate: "
                f"{(summary or link_to_article[link].get('title', ''))[:60]}"
            )
            needs_retranslate.append(link_to_article[link])
            seen_links.add(link)
            continue

        valid_items.append({
            "link": link,
            "summary": summary,
            "category": category,
        })
        seen_links.add(link)

        if len(valid_items) >= TARGET_DIGEST_COUNT:
            break

    # Re-translate any English LLM summaries before filling gaps
    if needs_retranslate and len(valid_items) < TARGET_DIGEST_COUNT:
        translated = _summarize_articles_in_persian(needs_retranslate)
        for article in needs_retranslate:
            if len(valid_items) >= TARGET_DIGEST_COUNT:
                break
            link = article.get("link", "")
            tr = translated.get(link)
            if not tr:
                continue
            valid_items.append({
                "link": link,
                "summary": tr["summary"],
                "category": tr.get("category", "other"),
            })

    if len(valid_items) < TARGET_DIGEST_COUNT:
        print(f"[warn] Only {len(valid_items)} valid digest items — filling with Persian re-translate")
        fill_candidates = []
        for article in articles:
            link = article.get("link", "")
            if not link or link in seen_links:
                continue
            fill_candidates.append(article)
            seen_links.add(link)
            if len(fill_candidates) >= (TARGET_DIGEST_COUNT - len(valid_items)):
                break

        if fill_candidates:
            translated = _summarize_articles_in_persian(fill_candidates)
            for article in fill_candidates:
                if len(valid_items) >= TARGET_DIGEST_COUNT:
                    break
                link = article.get("link", "")
                tr = translated.get(link)
                if not tr:
                    print(f"[warn] Skipping untranslated fill item: {article.get('title', '')[:60]}")
                    continue
                valid_items.append({
                    "link": link,
                    "summary": tr["summary"],
                    "category": tr.get("category", "other"),
                })

    return valid_items[:TARGET_DIGEST_COUNT]


def _quality_score(article: dict) -> float:
    """
    Assigns a quality score to an article based on source authority,
    mention count, and title signal words.
    Higher = more likely to be selected for the digest.
    """
    score = 0.0

    # Tier-1 sources get a bonus (authoritative AI-specific outlets)
    tier1_sources = {
        "OpenAI Blog", "Google DeepMind Blog", "Anthropic News", "Meta AI Blog",
        "Microsoft AI Blog", "Hugging Face Blog", "MIT Technology Review AI",
        "TechCrunch AI", "VentureBeat AI", "The Verge AI", "Wired AI",
        "ArXiv CS.AI (new)", "ArXiv CS.LG (Machine Learning)", "ArXiv CS.CL (NLP/LLM)",
        "Papers With Code", "Import AI (Jack Clark)", "Mistral AI Blog",
    }
    if article.get("source") in tier1_sources:
        score += 3.0

    # Mention count is the strongest signal
    score += min(article.get("mention_count", 1) * 2.0, 10.0)

    # Title keyword signals
    title_lower = article.get("title", "").lower()
    high_value_keywords = [
        "release", "launch", "announces", "introduces", "new model",
        "open source", "open-source", "benchmark", "breakthrough",
        "raises", "funding", "acqui", "billion", "million",
        "gpt", "claude", "gemini", "llama", "mistral", "deepseek",
        "regulation", "safety", "alignment", "policy",
        "agent", "multimodal", "reasoning", "fine-tun",
    ]
    for kw in high_value_keywords:
        if kw in title_lower:
            score += 1.0

    # Penalize low-signal titles
    low_value_keywords = ["how to", "tutorial", "explained", "what is", "guide to", "tips for"]
    for kw in low_value_keywords:
        if kw in title_lower:
            score -= 1.5

    # Bonus for having an image (visual posts perform better)
    if article.get("image_url"):
        score += 0.5

    return score


def filter_and_rank_articles(articles: list, top_n: int = 40) -> list:
    """
    Filters out low-quality articles and returns the top_n by quality score.
    This runs before the LLM to reduce prompt size and improve selection quality.
    """
    scored = [(a, _quality_score(a)) for a in articles]
    scored.sort(key=lambda x: x[1], reverse=True)
    top = [a for a, _ in scored[:top_n]]
    print(f"[info] Quality filter: {len(articles)} → {len(top)} articles sent to LLM")
    return top


def generate_daily_digest(articles):
    """
    Generates the daily digest post.
    Returns: digest_text (str)
    """
    # Pre-filter to top quality articles before sending to LLM
    top_articles = filter_and_rank_articles(articles, top_n=40)

    compact = []
    for a in top_articles:
        compact.append({
            "title": a["title"],
            "source": a["source"],
            "link": a["link"],
            "summary": a.get("summary", "")[:150],
            "mention_count": a.get("mention_count", 1),
            "also_covered_by": a.get("also_covered_by", []),
        })

    articles_json = json.dumps(compact, ensure_ascii=False, indent=2)
    channel_footer = TELEGRAM_CHAT_ID if TELEGRAM_CHAT_ID else ""

    system_prompt = (
        "تو یک روزنامه‌نگار ارشد متخصص در حوزه هوش مصنوعی هستی که برای مخاطبان فارسی‌زبان "
        "فنی و توسعه‌دهنده می‌نویسی. "
        "تمام خروجی‌ات باید ۱۰۰٪ به زبان فارسی روان و تخصصی باشد — هیچ کلمه انگلیسی، "
        "هیچ جمله انگلیسی، و هیچ ترجمه‌نشده‌ای مجاز نیست. "
        "اگر نام یک محصول یا شرکت انگلیسی است (مثل GPT-4، Claude، Gemini) می‌توانی نام را "
        "نگه داری ولی توضیحات اطرافش باید کاملاً فارسی باشد."
    )

    user_prompt = f"""
از بین مقالات ورودی زیر (که از بیش از ۵۰ منبع مختلف جهانی جمع‌آوری شده‌اند)، دقیقاً {TARGET_DIGEST_COUNT} خبر انتخاب کن.

معیارهای انتخاب (به ترتیب اولویت):
۱. خبرهایی که mention_count بالاتری دارند — یعنی چند منبع مختلف آن‌ها را پوشش داده‌اند
۲. خبرهای فنی و کاربردی که برای توسعه‌دهندگان، محققان، و متخصصان AI مفید هستند
۳. معرفی مدل‌های جدید، ابزارهای توسعه، پیشرفت‌های پژوهشی، تامین مالی مهم، قوانین جدید
۴. از اخبار سطحی، تکراری، یا صرفاً تبلیغاتی بپرهیز

خروجی فقط یک JSON معتبر باشد (بدون ```json و بدون توضیح اضافه) با این ساختار دقیق:

{{
  "items": [
    {{
      "link": "لینک دقیق مقاله از فیلد link ورودی (بدون تغییر)",
      "summary": "خلاصه کوتاه، روان، تخصصی و کاملاً فارسی (۱ تا ۲ جمله، ۳۰ تا ۵۰ کلمه، بدون HTML)",
      "category": "یکی از: model | research | tool | business | safety | education | product | data | hardware | society | other"
    }}
  ]
}}

قوانین الزامی — نقض هر کدام خروجی را باطل می‌کند:
- دقیقاً {TARGET_DIGEST_COUNT} آیتم در items باشد
- فیلد link باید عیناً از فیلد link مقالات ورودی کپی شود — هیچ تغییری نده
- summary باید ۱۰۰٪ فارسی روان باشد — حتی یک جمله انگلیسی هم مجاز نیست
- اخبار متنوع از دسته‌های مختلف (مدل، ابزار، پژوهش، کسب‌وکار، ...) انتخاب کن
- از نوشتن خلاصه‌های تکراری یا مشابه خودداری کن

مقالات ورودی:
{articles_json}
"""

    raw = generate_llm_text(system_prompt, user_prompt)
    items = _parse_digest_items(raw, top_articles)
    return _build_digest_html(items, channel_footer), items


def select_best_article_for_single_post(articles):
    """
    Uses the LLM to select the most newsworthy article that HAS an image.
    Falls back to first article with an image if LLM fails.
    Returns None if no articles have an image.
    """
    # Pre-filter quality, then keep only those with an image
    top_articles = filter_and_rank_articles(articles, top_n=30)
    candidates_with_image = [a for a in top_articles if a.get("image_url")]

    # Fallback: if top-30 has no images, expand search to all
    if not candidates_with_image:
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
        "تو یک سردبیر و تحلیلگر ارشد خبر هوش مصنوعی هستی که برای مخاطبان فارسی‌زبان فنی می‌نویسی. "
        "تمام خروجی‌ات باید ۱۰۰٪ به زبان فارسی روان و تخصصی باشد — هیچ جمله یا پاراگراف انگلیسی مجاز نیست. "
        "نام‌های خاص محصولات و شرکت‌ها (مثل GPT-4o، Claude Sonnet، Gemini) را می‌توانی نگه داری."
    )

    user_prompt = f"""
درباره مقاله زیر، یک پست کامل، شکیل و تحلیلی به زبان فارسی روان بنویس.

ساختار خروجی (دقیقاً همین فرمت):
🔥 <b>عنوان جذاب و داغ فارسی</b>

[یک یا دو پاراگراف تحلیلی — ببین این خبر چه چیزی را تغییر می‌دهد، چرا اهمیت دارد، و چه پیامدی برای توسعه‌دهندگان یا صنعت AI دارد]

منبع: {selected_article.get('source')} — <a href="{selected_article.get('link')}">مطالعه مقاله کامل</a>
{channel_footer}

قوانین الزامی:
- خروجی را مستقیماً از عنوان شروع کن (بدون هیچ مقدمه، توضیح یا متن انگلیسی).
- عنوان با ایموجی شروع شود و با <b> و </b> احاطه شود.
- تمام متن توضیحات (۱۵۰ تا ۲۵۰ کلمه) باید فارسی روان و تخصصی باشد.
- لینک منبع دقیقاً به صورت <a href="...">مطالعه مقاله کامل</a> باشد.
- هیچ ```html یا توضیحات اضافه در خروجی نباشد.

اطلاعات مقاله:
{article_json}
"""

    post_text = generate_llm_text(system_prompt, user_prompt)
    image_url = selected_article.get("image_url")

    return post_text, image_url


def generate_educational_post(article: dict) -> str:
    """
    Rewrites a real educational article into a human-sounding Persian Telegram post.
    Always includes a short code sample and a link back to the source.
    """
    channel_footer = TELEGRAM_CHAT_ID if TELEGRAM_CHAT_ID else ""
    article_json = json.dumps({
        "title": article.get("title", ""),
        "source": article.get("source", ""),
        "link": article.get("link", ""),
        "summary": (article.get("summary") or "")[:600],
    }, ensure_ascii=False, indent=2)

    system_prompt = (
        "تو نویسندهٔ یک کانال تلگرام فنی فارسی هستی — نه ربات، نه مترجم رسمی. "
        "مثل یک برنامه‌نویس با‌تجربه حرف می‌زنی که برای دوستش توضیح می‌دهد. "
        "لحنت محاوره‌ای، دقیق و خودمونی است. "
        "هرگز شبیه متن تولیدشده با هوش مصنوعی ننویس."
    )

    user_prompt = f"""
از روی این مقاله آموزشی واقعی، یک پست تلگرامی آموزشی به فارسی بنویس.
محتوا را بازنویسی کن و با زبان خودت توضیح بده — ترجمهٔ لفظ‌به‌لفظ ممنوع.

ساختار خروجی (دقیقاً HTML تلگرام، بدون ``` و بدون توضیح اضافه):

<b>عنوان کوتاه و جذاب فارسی</b>

پاراگراف ۱ (شروع انسانی؛ مثلاً با یک مشاهده، سوال، یا اشتباه رایج)

پاراگراف ۲–۳ (اصل مطلب؛ جملات کوتاه؛ بدون فهرست شماره‌دار خشک)

<pre>یک تکه کد کوتاه و واقعی پایتون (۵ تا ۱۲ خط) که همان نکته را نشان دهد</pre>

منبع: <a href="{article.get('link', '')}">{article.get('source', 'منبع')}</a>

یک سوال کوتاه در آخر برای دعوت به کامنت

{channel_footer}

قوانین سخت:
- کل متن فارسی باشد؛ فقط نام کتابخانه/توابع/کد می‌تواند انگلیسی باشد
- ممنوع: «در این مطلب به بررسی می‌پردازیم»، «نکته مهم این است که»، «در نتیجه می‌توان گفت»، «بیایید بررسی کنیم»، لحن مقاله‌ای
- ممنوع: ایموجی زیاد (حداکثر یکی در کل پست، آن هم اختیاری)
- کد داخل <pre> باشد نه markdown
- لینک منبع را عوض نکن
- طول کل پست حدود ۲۰۰ تا ۳۵۰ کلمه

اطلاعات مقاله منبع:
{article_json}
"""

    return generate_llm_text(system_prompt, user_prompt)


# ---------------------------------------------------------------------------
# Step 3b: Infographic Generation (HTML → Playwright screenshot)
# ---------------------------------------------------------------------------

# ── Themes ──────────────────────────────────────────────────────────────────
# Each theme defines CSS variable values injected into infographic_template.html
INFOGRAPHIC_THEMES = {
    "purple": """
:root {
  --bg-base: #0A0818;
  --blob-a: #3B1FA8; --blob-b: #1A1060; --blob-c: #110D2E;
  --glow-a: rgba(99,76,255,.28); --glow-b: rgba(139,92,246,.18); --glow-c: rgba(56,189,248,.12);
  --dot-color: rgba(255,255,255,.06);
  --accent-grad: linear-gradient(135deg,#6D4FE8,#A78BFA);
  --icon-glow: rgba(109,79,232,.55);
  --accent-1: #A78BFA;
  --text-primary: #F1EFFF; --text-muted: rgba(255,255,255,.42); --text-footer: rgba(255,255,255,.7);
  --pill-bg: rgba(255,255,255,.07); --pill-border: rgba(255,255,255,.14);
  --badge-bg: rgba(167,139,250,.12); --badge-border: rgba(167,139,250,.3); --badge-text: #C4B5FD;
  --grad-1: linear-gradient(90deg,#818CF8,#C084FC,#F472B6);
  --grad-2: linear-gradient(90deg,#38BDF8,#818CF8);
  --sep-color-a: rgba(167,139,250,.6); --sep-color-b: rgba(56,189,248,.4);
  --card-bg: rgba(255,255,255,.045); --card-border: rgba(255,255,255,.09);
  --card-text-color: rgba(255,255,255,.88);
  --footer-border: rgba(255,255,255,.08);
  --c1:#818CF8; --c1-dark:#6366F1; --c1-border:rgba(129,140,248,.25); --c1-shadow:rgba(99,102,241,.5);
  --c2:#C084FC; --c2-dark:#A855F7; --c2-border:rgba(192,132,252,.22); --c2-shadow:rgba(168,85,247,.5);
  --c3:#38BDF8; --c3-dark:#0EA5E9; --c3-border:rgba(56,189,248,.22);  --c3-shadow:rgba(14,165,233,.5);
  --c4:#34D399; --c4-dark:#10B981; --c4-border:rgba(52,211,153,.22);  --c4-shadow:rgba(16,185,129,.5);
  --c5:#FBBF24; --c5-dark:#F59E0B; --c5-border:rgba(251,191,36,.22);  --c5-shadow:rgba(245,158,11,.5);
}""",

    "ocean": """
:root {
  --bg-base: #040E1A;
  --blob-a: #0A3060; --blob-b: #062040; --blob-c: #041828;
  --glow-a: rgba(6,182,212,.25); --glow-b: rgba(14,165,233,.18); --glow-c: rgba(99,102,241,.12);
  --dot-color: rgba(255,255,255,.05);
  --accent-grad: linear-gradient(135deg,#0891B2,#38BDF8);
  --icon-glow: rgba(8,145,178,.55);
  --accent-1: #38BDF8;
  --text-primary: #E0F7FF; --text-muted: rgba(224,247,255,.38); --text-footer: rgba(224,247,255,.65);
  --pill-bg: rgba(56,189,248,.08); --pill-border: rgba(56,189,248,.18);
  --badge-bg: rgba(6,182,212,.12); --badge-border: rgba(6,182,212,.3); --badge-text: #67E8F9;
  --grad-1: linear-gradient(90deg,#06B6D4,#38BDF8,#7DD3FC);
  --grad-2: linear-gradient(90deg,#818CF8,#38BDF8);
  --sep-color-a: rgba(6,182,212,.6); --sep-color-b: rgba(56,189,248,.4);
  --card-bg: rgba(6,182,212,.05); --card-border: rgba(56,189,248,.1);
  --card-text-color: rgba(224,247,255,.88);
  --footer-border: rgba(56,189,248,.1);
  --c1:#38BDF8; --c1-dark:#0EA5E9; --c1-border:rgba(56,189,248,.25);  --c1-shadow:rgba(14,165,233,.5);
  --c2:#06B6D4; --c2-dark:#0891B2; --c2-border:rgba(6,182,212,.22);   --c2-shadow:rgba(8,145,178,.5);
  --c3:#818CF8; --c3-dark:#6366F1; --c3-border:rgba(129,140,248,.22); --c3-shadow:rgba(99,102,241,.5);
  --c4:#34D399; --c4-dark:#10B981; --c4-border:rgba(52,211,153,.22);  --c4-shadow:rgba(16,185,129,.5);
  --c5:#7DD3FC; --c5-dark:#38BDF8; --c5-border:rgba(125,211,252,.22); --c5-shadow:rgba(56,189,248,.5);
}""",

    "sunset": """
:root {
  --bg-base: #0F0804;
  --blob-a: #7C1D0A; --blob-b: #4A0E1A; --blob-c: #2A0A08;
  --glow-a: rgba(249,115,22,.25); --glow-b: rgba(239,68,68,.18); --glow-c: rgba(251,191,36,.12);
  --dot-color: rgba(255,255,255,.05);
  --accent-grad: linear-gradient(135deg,#EA580C,#FB923C);
  --icon-glow: rgba(234,88,12,.55);
  --accent-1: #FB923C;
  --text-primary: #FFF7ED; --text-muted: rgba(255,247,237,.38); --text-footer: rgba(255,247,237,.65);
  --pill-bg: rgba(249,115,22,.08); --pill-border: rgba(249,115,22,.18);
  --badge-bg: rgba(239,68,68,.1); --badge-border: rgba(239,68,68,.28); --badge-text: #FCA5A5;
  --grad-1: linear-gradient(90deg,#F97316,#FB923C,#FBBF24);
  --grad-2: linear-gradient(90deg,#EF4444,#F97316);
  --sep-color-a: rgba(249,115,22,.6); --sep-color-b: rgba(251,191,36,.4);
  --card-bg: rgba(249,115,22,.05); --card-border: rgba(249,115,22,.1);
  --card-text-color: rgba(255,247,237,.88);
  --footer-border: rgba(249,115,22,.1);
  --c1:#F97316; --c1-dark:#EA580C; --c1-border:rgba(249,115,22,.25);  --c1-shadow:rgba(234,88,12,.5);
  --c2:#EF4444; --c2-dark:#DC2626; --c2-border:rgba(239,68,68,.22);   --c2-shadow:rgba(220,38,38,.5);
  --c3:#FBBF24; --c3-dark:#F59E0B; --c3-border:rgba(251,191,36,.22);  --c3-shadow:rgba(245,158,11,.5);
  --c4:#FB7185; --c4-dark:#F43F5E; --c4-border:rgba(251,113,133,.22); --c4-shadow:rgba(244,63,94,.5);
  --c5:#FDE68A; --c5-dark:#FCD34D; --c5-border:rgba(253,230,138,.22); --c5-shadow:rgba(252,211,77,.5);
}""",

    "forest": """
:root {
  --bg-base: #050E08;
  --blob-a: #0A3018; --blob-b: #071F10; --blob-c: #061408;
  --glow-a: rgba(16,185,129,.22); --glow-b: rgba(5,150,105,.18); --glow-c: rgba(52,211,153,.1);
  --dot-color: rgba(255,255,255,.05);
  --accent-grad: linear-gradient(135deg,#059669,#34D399);
  --icon-glow: rgba(5,150,105,.55);
  --accent-1: #34D399;
  --text-primary: #ECFDF5; --text-muted: rgba(236,253,245,.38); --text-footer: rgba(236,253,245,.65);
  --pill-bg: rgba(16,185,129,.08); --pill-border: rgba(16,185,129,.18);
  --badge-bg: rgba(5,150,105,.12); --badge-border: rgba(5,150,105,.3); --badge-text: #6EE7B7;
  --grad-1: linear-gradient(90deg,#10B981,#34D399,#6EE7B7);
  --grad-2: linear-gradient(90deg,#059669,#10B981);
  --sep-color-a: rgba(16,185,129,.6); --sep-color-b: rgba(52,211,153,.4);
  --card-bg: rgba(16,185,129,.05); --card-border: rgba(52,211,153,.1);
  --card-text-color: rgba(236,253,245,.88);
  --footer-border: rgba(16,185,129,.1);
  --c1:#34D399; --c1-dark:#10B981; --c1-border:rgba(52,211,153,.25);  --c1-shadow:rgba(16,185,129,.5);
  --c2:#10B981; --c2-dark:#059669; --c2-border:rgba(16,185,129,.22);  --c2-shadow:rgba(5,150,105,.5);
  --c3:#6EE7B7; --c3-dark:#34D399; --c3-border:rgba(110,231,183,.22); --c3-shadow:rgba(52,211,153,.5);
  --c4:#FBBF24; --c4-dark:#F59E0B; --c4-border:rgba(251,191,36,.22);  --c4-shadow:rgba(245,158,11,.5);
  --c5:#38BDF8; --c5-dark:#0EA5E9; --c5-border:rgba(56,189,248,.22);  --c5-shadow:rgba(14,165,233,.5);
}""",

    "midnight": """
:root {
  --bg-base: #080808;
  --blob-a: #1A1A1A; --blob-b: #111111; --blob-c: #0D0D0D;
  --glow-a: rgba(234,179,8,.18); --glow-b: rgba(161,161,170,.12); --glow-c: rgba(234,179,8,.08);
  --dot-color: rgba(255,255,255,.04);
  --accent-grad: linear-gradient(135deg,#A16207,#EAB308);
  --icon-glow: rgba(234,179,8,.45);
  --accent-1: #EAB308;
  --text-primary: #FAFAFA; --text-muted: rgba(250,250,250,.35); --text-footer: rgba(250,250,250,.6);
  --pill-bg: rgba(255,255,255,.06); --pill-border: rgba(255,255,255,.1);
  --badge-bg: rgba(234,179,8,.1); --badge-border: rgba(234,179,8,.25); --badge-text: #FDE047;
  --grad-1: linear-gradient(90deg,#EAB308,#FDE047,#FBBF24);
  --grad-2: linear-gradient(90deg,#D4D4D8,#FAFAFA);
  --sep-color-a: rgba(234,179,8,.5); --sep-color-b: rgba(161,161,170,.3);
  --card-bg: rgba(255,255,255,.04); --card-border: rgba(255,255,255,.07);
  --card-text-color: rgba(250,250,250,.85);
  --footer-border: rgba(255,255,255,.07);
  --c1:#EAB308; --c1-dark:#A16207; --c1-border:rgba(234,179,8,.25);   --c1-shadow:rgba(234,179,8,.5);
  --c2:#D4D4D8; --c2-dark:#A1A1AA; --c2-border:rgba(212,212,216,.2);  --c2-shadow:rgba(161,161,170,.4);
  --c3:#FBBF24; --c3-dark:#F59E0B; --c3-border:rgba(251,191,36,.22);  --c3-shadow:rgba(245,158,11,.5);
  --c4:#F4F4F5; --c4-dark:#D4D4D8; --c4-border:rgba(244,244,245,.15); --c4-shadow:rgba(212,212,216,.4);
  --c5:#FDE047; --c5-dark:#EAB308; --c5-border:rgba(253,224,71,.2);   --c5-shadow:rgba(234,179,8,.45);
}""",
}

# Theme selection by day of week — rotates automatically each day
_THEME_ROTATION = ["purple", "ocean", "sunset", "forest", "midnight", "ocean", "purple"]

# Persian month names
_PERSIAN_MONTHS = [
    "", "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]

# Persian digits
_P = {"0":"۰","1":"۱","2":"۲","3":"۳","4":"۴","5":"۵","6":"۶","7":"۷","8":"۸","9":"۹"}

def _to_persian(n: int) -> str:
    return "".join(_P.get(d, d) for d in str(n))


def _jalali_today() -> str:
    """Returns today's date as a Persian Jalali string, e.g. ۱۱ شهریور ۱۴۰۴"""
    # Simple Gregorian → Jalali conversion (no external lib needed)
    g = dt.date.today()
    gy, gm, gd = g.year, g.month, g.day

    g_days_in_month = [0,31,28,31,30,31,30,31,31,30,31,30,31]
    if (gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0:
        g_days_in_month[2] = 29

    jy = gy - 1600
    gm -= 1
    gd -= 1

    g_day_no = 365 * jy + (jy + 3) // 4 - (jy + 99) // 100 + (jy + 399) // 400
    for i in range(gm):
        g_day_no += g_days_in_month[i + 1]
    g_day_no += gd

    j_day_no = g_day_no - 79

    j_np = j_day_no // 12053
    j_day_no %= 12053

    jy = 979 + 33 * j_np + 4 * (j_day_no // 1461)
    j_day_no %= 1461

    if j_day_no >= 366:
        jy += (j_day_no - 1) // 365
        j_day_no = (j_day_no - 1) % 365

    j_days_in_month = [31,31,31,31,31,31,30,30,30,30,30,29]
    jm = 0
    for i, days in enumerate(j_days_in_month):
        if j_day_no < days:
            jm = i + 1
            jd = j_day_no + 1
            break
        j_day_no -= days
    else:
        jm, jd = 12, 29

    return f"{_to_persian(jd)} {_PERSIAN_MONTHS[jm]} {_to_persian(jy)}"


# Map category key → Persian label for cards
_CATEGORY_LABELS = {
    "model":     "مدل جدید",
    "research":  "پژوهش",
    "tool":      "ابزار توسعه",
    "business":  "کسب‌وکار",
    "safety":    "امنیت و قانون",
    "education": "آموزش",
    "product":   "محصول",
    "data":      "داده",
    "hardware":  "سخت‌افزار",
    "society":   "جامعه",
    "other":     "هوش مصنوعی",
}


def _build_card_html(items: list) -> str:
    """Builds the <div class='card'>…</div> blocks for each digest item."""
    persian_nums = ["۱", "۲", "۳", "۴", "۵", "۶", "۷", "۸", "۹", "۱۰"]
    html_parts = []

    for i, item in enumerate(items):
        summary  = item.get("summary", "").strip()
        num      = persian_nums[i] if i < len(persian_nums) else str(i + 1)

        card = f"""
    <div class="card">
      <div class="card-num">{num}</div>
      <div class="card-body">
        <div class="card-text">{summary}</div>
      </div>
    </div>"""
        html_parts.append(card)

    return "\n".join(html_parts)


def generate_infographic(items: list, template_path: str = None, output_path: str = None, theme: str = None) -> str | None:
    """
    Renders the infographic HTML template with the given digest items,
    takes a 1080×1920 screenshot via Playwright, and returns the path
    to the saved PNG file.

    Args:
        items:         list of digest item dicts (link, summary, category)
        template_path: path to infographic_template.html (auto-detected if None)
        output_path:   where to save the PNG (default: next to main.py)
        theme:         theme name from INFOGRAPHIC_THEMES (random by weekday if None)
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[warn] playwright not installed — skipping infographic generation")
        return None

    # Resolve paths
    if template_path is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(script_dir, "infographic_template.html")

    if output_path is None:
        output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hooshkav_infographic.png")

    if not os.path.exists(template_path):
        print(f"[warn] Infographic template not found at {template_path} — skipping")
        return None

    try:
        with open(template_path, "r", encoding="utf-8") as f:
            html = f.read()
    except Exception as e:
        print(f"[warn] Could not read infographic template: {e}")
        return None

    # Inject data into template
    cards_html = _build_card_html(items)
    date_str   = _jalali_today()

    # Pick theme: explicit > weekday rotation
    if theme is None:
        weekday = dt.date.today().weekday()   # 0=Monday … 6=Sunday
        theme = _THEME_ROTATION[weekday % len(_THEME_ROTATION)]
    theme_css = INFOGRAPHIC_THEMES.get(theme, INFOGRAPHIC_THEMES["purple"])
    print(f"[info] Infographic theme: {theme}")

    html = html.replace("{{THEME_VARS}}", theme_css)
    html = html.replace("{{DATE}}", date_str)
    html = html.replace("{{CARDS}}", cards_html)

    # Render with Playwright
    try:
        print("[info] Rendering infographic with Playwright...")
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
            page = browser.new_page(
                viewport={"width": 1080, "height": 1920},
                device_scale_factor=2,
            )

            # Use data URI so no file:// permission issues on GitHub Actions
            import base64
            encoded = base64.b64encode(html.encode("utf-8")).decode("ascii")
            page.goto(f"data:text/html;base64,{encoded}")

            # Wait for Vazirmatn font to load + JS fit to run
            page.wait_for_load_state("networkidle", timeout=15000)
            page.wait_for_timeout(1200)   # extra buffer for font + JS execution

            page.screenshot(path=output_path, full_page=False, type="png")
            browser.close()

        # Resize 2x render back to target 1080×1920 for crisp output
        try:
            from PIL import Image as _Img
            img = _Img.open(output_path)
            img = img.resize((1080, 1920), _Img.LANCZOS)
            img.save(output_path, "PNG", optimize=True)
        except ImportError:
            pass  # Pillow not available — keep 2x image as-is

        print(f"[info] Infographic saved to {output_path}")
        return output_path

    except Exception as e:
        print(f"[warn] Infographic rendering failed: {e}")
        return None


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
    Cleans up LLM/generated text, strips preambles, balances HTML tags.
    post_type: 'digest' | 'single' | 'edu'
    """
    if not text:
        return text

    # Convert markdown fenced code blocks to Telegram <pre> before stripping fences
    def _fence_to_pre(match):
        code = match.group(2) or ""
        code = code.strip("\n")
        # Escape HTML special chars inside code
        code = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return f"<pre>{code}</pre>"

    text = re.sub(r"```([a-zA-Z0-9_+-]*)\n(.*?)```", _fence_to_pre, text, flags=re.DOTALL)

    # Strip leftover markdown/html fences
    text = re.sub(r"^```html\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^```\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE).strip()

    if post_type == "digest":
        title_match = re.search(r"(<b>\s*مهم‌?ترین.*)", text, flags=re.DOTALL | re.IGNORECASE)
        if title_match:
            text = title_match.group(1)
        else:
            title_match = re.search(r"(مهم‌?ترین.*)", text, flags=re.DOTALL | re.IGNORECASE)
            if title_match:
                text = title_match.group(1)
    elif post_type in ("single", "edu"):
        content_match = re.search(
            r"([🔥🚀🧠📋🛠🔐💸🎬⚡🌐🤖💡🔬📡🏆]|<b>)",
            text
        )
        if content_match:
            text = text[content_match.start():]

    # Convert markdown links [title](url) → <a href="url">title</a>
    text = re.sub(r"\[([^\]]+)\]\((https?://[^\)]+)\)", r'<a href="\2">\1</a>', text)

    # Replace unsupported block tags with newlines (keep pre/code/a/b/i)
    text = re.sub(r"</?(?:p|div|span|ul|ol|li|br|h[1-6])[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    balanced_lines = []
    inside_pre = False
    for line in text.split("\n"):
        if "<pre>" in line.lower():
            inside_pre = True
        if inside_pre:
            balanced_lines.append(line.rstrip())
            if "</pre>" in line.lower():
                inside_pre = False
            continue

        line = line.strip()
        if not line:
            balanced_lines.append("")
            continue

        line = re.sub(r'<a\s+href="[^"]*$', "", line, flags=re.IGNORECASE)

        open_a = len(re.findall(r"<a\b[^>]*>", line))
        close_a = line.count("</a>")
        if open_a > close_a:
            line += "</a>" * (open_a - close_a)
        elif close_a > open_a:
            line = re.sub(r"</a>", "", line, count=close_a - open_a)

        open_b = line.count("<b>")
        close_b = line.count("</b>")
        if open_b > close_b:
            line += "</b>" * (open_b - close_b)
        elif close_b > open_b:
            line = re.sub(r"</b>", "", line, count=close_b - open_b)

        open_i = line.count("<i>")
        close_i = line.count("</i>")
        if open_i > close_i:
            line += "</i>" * (open_i - close_i)
        elif close_i > open_i:
            line = re.sub(r"</i>", "", line, count=close_i - open_i)

        balanced_lines.append(line)

    result = "\n".join(balanced_lines)
    if result.lower().count("<pre>") > result.lower().count("</pre>"):
        result += "</pre>" * (result.lower().count("<pre>") - result.lower().count("</pre>"))

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
    """Sends text or photo post to Telegram, with retry and safe truncation.

    Digest posts are plain text (no parse_mode).
    Single posts use HTML parse_mode.
    """
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is not set.")

    cleaned_text = clean_html_for_telegram(html_text, post_type=post_type)

    # Both digest and single use HTML parse_mode
    use_html = True

    if image_url and post_type == "single":
        caption = safe_truncate_html(cleaned_text, TELEGRAM_CAPTION_LIMIT)
        payload = {
            "chat_id": chat_id,
            "photo": image_url,
            "caption": caption,
        }
        if use_html:
            payload["parse_mode"] = "HTML"
        resp = _telegram_request("sendPhoto", payload)
        if resp is not None and resp.ok:
            print(f"[info] Photo message successfully sent to Telegram: {chat_id}")
            return
        else:
            status = resp.status_code if resp is not None else "timeout"
            print(f"[warn] sendPhoto failed ({status}), falling back to sendMessage")

    # Send as text message
    limit = TELEGRAM_MESSAGE_LIMIT
    text_body = safe_truncate_html(cleaned_text, limit) if use_html else cleaned_text[:limit]

    payload = {
        "chat_id": chat_id,
        "text": text_body,
        "disable_web_page_preview": True,
    }
    if use_html:
        payload["parse_mode"] = "HTML"

    resp = _telegram_request("sendMessage", payload)

    if resp is None or not resp.ok:
        status = resp.status_code if resp is not None else "timeout"
        print(f"[warn] Telegram sendMessage failed ({status}), retrying as plain text")
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

def _parse_mode_command(text: str):
    """
    Parses admin publish-mode commands.
    Returns ('status', None) | ('set', 'both'|'news'|'edu') | None
    """
    t = (text or "").strip().lower()
    t = t.replace("ي", "ی").replace("ك", "ک")

    aliases = {
        "both": "both", "full": "both", "all": "both",
        "خبر و آموزش": "both", "حالت کامل": "both", "کامل": "both",
        "news": "news", "فقط خبر": "news", "فقط اخبار": "news", "خبر": "news",
        "edu": "edu", "education": "edu", "فقط آموزش": "edu", "آموزش": "edu",
    }

    if t in ("/mode", "/mode status", "وضعیت", "حالت"):
        return ("status", None)

    if t.startswith("/mode"):
        parts = t.split(maxsplit=1)
        if len(parts) == 1:
            return ("status", None)
        arg = parts[1].strip()
        if arg in ("status", "وضعیت"):
            return ("status", None)
        mapped = aliases.get(arg)
        if mapped:
            return ("set", mapped)
        return ("status", None)

    if t in aliases and t in ("فقط خبر", "فقط اخبار", "خبر و آموزش", "حالت کامل", "فقط آموزش", "کامل"):
        # Bare Persian phrases only when clearly mode-related (not bare «آموزش» — that triggers edu post)
        if t in ("فقط خبر", "فقط اخبار", "خبر و آموزش", "حالت کامل", "فقط آموزش", "کامل"):
            return ("set", aliases[t])

    return None


def check_and_handle_on_demand_requests():
    """
    Processes Telegram commands from the authorized admin.
    - /mode … : updates publish mode immediately and acknowledges
    - /digest /edu /single : queued as on-demand content jobs
    Returns list of (chat_id, job) where job is digest|edu|single.
    """
    if not TELEGRAM_BOT_TOKEN:
        return []

    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates",
            timeout=15,
        )
        if not resp.ok:
            return []

        updates = resp.json().get("result", [])
        if not updates:
            return []

        on_demand_chats = []
        max_update_id = 0

        content_commands = {
            "/news": "digest", "/digest": "digest", "/latest": "digest",
            "/start": "digest", "اخبار": "digest", "خبر": "digest",
            "/single": "single", "پست": "single",
            "/edu": "edu", "/lesson": "edu", "آموزش": "edu",
        }

        for update in updates:
            update_id = update.get("update_id", 0)
            if update_id > max_update_id:
                max_update_id = update_id

            msg = update.get("message", {})
            sender = msg.get("from", {})
            username = (sender.get("username") or "").strip().lstrip("@")
            chat_id = msg.get("chat", {}).get("id")
            raw_text = (msg.get("text") or "").strip()
            text = raw_text.lower()

            if not chat_id or not text:
                continue

            is_admin = username.lower() == ALLOWED_TELEGRAM_USER.lower()

            mode_cmd = _parse_mode_command(raw_text)
            if mode_cmd:
                if not is_admin:
                    try:
                        send_telegram_post(
                            chat_id,
                            f"⛔️ دسترسی غیرمجاز — فقط @{ALLOWED_TELEGRAM_USER}",
                        )
                    except Exception:
                        pass
                    continue

                action, value = mode_cmd
                if action == "set" and value:
                    save_publish_mode(value)
                    reply = (
                        f"✅ حالت انتشار روی <b>{publish_mode_label(value)}</b> تنظیم شد.\n"
                        f"<code>/mode news</code> — فقط خبر\n"
                        f"<code>/mode both</code> — خبر + آموزش\n"
                        f"<code>/mode edu</code> — فقط آموزش"
                    )
                else:
                    current = load_publish_mode()
                    reply = (
                        f"⚙️ حالت فعلی: <b>{publish_mode_label(current)}</b> (<code>{current}</code>)\n\n"
                        f"<code>/mode news</code> — فقط خبر\n"
                        f"<code>/mode both</code> — خبر + آموزش\n"
                        f"<code>/mode edu</code> — فقط آموزش"
                    )
                try:
                    send_telegram_post(chat_id, reply)
                except Exception as e:
                    print(f"[warn] Could not reply to /mode: {e}")
                continue

            job = content_commands.get(text)
            if not job:
                continue

            if not is_admin:
                try:
                    send_telegram_post(
                        chat_id,
                        f"⛔️ <b>دسترسی غیرمجاز</b>\nاین ربات فقط توسط کاربر @{ALLOWED_TELEGRAM_USER} قابل فراخوانی است.",
                    )
                except Exception:
                    pass
                continue

            print(f"[info] Authorized command '{text}' from @{username} (job: {job})")
            on_demand_chats.append((chat_id, job))

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

def _run_digest(targets, on_demand_requests):
    print("[info] Generating Daily Digest...")
    articles = fetch_recent_articles(lookback_hours=LOOKBACK_HOURS)
    if not articles:
        print(f"[warn] No articles found in the last {LOOKBACK_HOURS} hours.")
        return
    articles = deduplicate_and_score(articles)
    digest_text, _digest_items = generate_daily_digest(articles)
    if not digest_text:
        print("[warn] Empty digest — nothing to send")
        return

    all_targets = list(targets) + [cid for cid, rm in on_demand_requests if rm == "digest"]
    for chat in all_targets:
        send_telegram_post(chat, digest_text, post_type="digest")


def _run_edu(targets, on_demand_requests, slot: int = 0):
    print(f"[info] Generating educational post (slot={slot})...")
    articles = fetch_edu_articles(lookback_hours=LOOKBACK_HOURS_EDU)
    if not articles:
        print("[warn] No educational articles found — retrying with 14-day lookback")
        articles = fetch_edu_articles(lookback_hours=24 * 14)
    if not articles:
        print("[warn] Still no educational articles — skipping edu post")
        return

    selected = select_edu_article(articles, slot=slot)
    if not selected:
        print("[warn] Could not select educational article")
        return

    post_text = generate_educational_post(selected)
    if not post_text:
        print("[warn] Empty educational post")
        return

    all_targets = list(targets) + [cid for cid, rm in on_demand_requests if rm == "edu"]
    for chat in all_targets:
        send_telegram_post(chat, post_text, post_type="edu")


def _run_single(targets, on_demand_requests):
    print("[info] Generating Single Rich News Post...")
    articles = fetch_recent_articles(lookback_hours=LOOKBACK_HOURS_SINGLE)
    if not articles:
        print(f"[warn] No articles found in the last {LOOKBACK_HOURS_SINGLE} hours.")
        return
    articles = deduplicate_and_score(articles)
    post_text, image_url = generate_single_rich_post(articles)
    if not post_text:
        return
    all_targets = list(targets) + [cid for cid, rm in on_demand_requests if rm == "single"]
    for chat in all_targets:
        send_telegram_post(chat, post_text, image_url, post_type="single")


def main():
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "digest"
    slot = 0
    if len(sys.argv) > 2 and sys.argv[2].isdigit():
        slot = int(sys.argv[2])

    print(f"=== Hooshkav Bot (mode={mode}, slot={slot}) ===")

    on_demand_requests = check_and_handle_on_demand_requests()
    publish_mode = load_publish_mode()
    print(f"[info] Publish mode: {publish_mode} ({publish_mode_label(publish_mode)})")

    targets = set()
    if TELEGRAM_CHAT_ID:
        targets.add(TELEGRAM_CHAT_ID)

    # On-demand jobs always run for the requesting admin chat, even if publish mode would skip the channel
    wants_digest = mode == "digest" or any(rm == "digest" for _, rm in on_demand_requests)
    wants_edu = mode == "edu" or any(rm == "edu" for _, rm in on_demand_requests)
    wants_single = mode == "single" or any(rm == "single" for _, rm in on_demand_requests)

    if wants_digest:
        channel_ok = mode_allows_job(publish_mode, "digest")
        digest_targets = set(targets) if (mode == "digest" and channel_ok) else set()
        # If scheduled digest blocked by publish mode, still serve on-demand digests
        if not channel_ok and mode == "digest":
            print(f"[info] Skipping scheduled digest — publish mode is '{publish_mode}'")
        if digest_targets or any(rm == "digest" for _, rm in on_demand_requests):
            _run_digest(digest_targets, on_demand_requests)
        elif mode == "digest":
            pass

    if wants_edu:
        channel_ok = mode_allows_job(publish_mode, "edu")
        edu_targets = set(targets) if (mode == "edu" and channel_ok) else set()
        if not channel_ok and mode == "edu":
            print(f"[info] Skipping scheduled edu — publish mode is '{publish_mode}'")
        if edu_targets or any(rm == "edu" for _, rm in on_demand_requests):
            _run_edu(edu_targets, on_demand_requests, slot=slot)

    if wants_single:
        _run_single(targets if mode == "single" else set(), on_demand_requests)

    print("=== Job Completed Successfully ===")


if __name__ == "__main__":
    main()
