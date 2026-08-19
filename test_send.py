"""
CLI preview test: fetches real articles, calls the LLM, and prints the
generated post directly in the terminal — no Telegram send.

Run with:
    python test_send.py [digest|single]
"""

import sys
import main

mode = sys.argv[1].lower() if len(sys.argv) > 1 else "digest"

print("=" * 60)
print(f"CLI Preview Test  (mode: {mode})")
print("=" * 60)

# Step 1: Fetch articles
print("\n[1/2] Fetching articles from RSS feeds...")
articles = main.fetch_recent_articles()
print(f"      Collected {len(articles)} articles from feeds\n")
if not articles:
    print("FAIL: No articles fetched.")
    sys.exit(1)

# Step 2: Generate and print
print("[2/2] Generating post via LLM...\n")

if mode == "single":
    post_text, image_url = main.generate_single_rich_post(articles)
    cleaned = main.clean_html_for_telegram(post_text or "", post_type="single")
    print("─" * 60)
    print(cleaned)
    print("─" * 60)
    if image_url:
        print(f"\n📷 Image: {image_url}")
else:
    digest_text = main.generate_daily_digest(articles)
    cleaned = main.clean_html_for_telegram(digest_text or "", post_type="digest")
    print("─" * 60)
    print(cleaned)
    print("─" * 60)

print("\nDone.")
