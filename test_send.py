"""
CLI preview test: fetches real articles, calls the LLM, and prints the
generated post directly in the terminal — no Telegram send.

Run with:
    python test_send.py [digest|single|edu]
"""

import sys
import main

mode = sys.argv[1].lower() if len(sys.argv) > 1 else "digest"
slot = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 0

print("=" * 60)
print(f"CLI Preview Test  (mode: {mode})")
print("=" * 60)

if mode == "edu":
    print("\n[1/3] Fetching educational articles...")
    articles = main.fetch_edu_articles()
    print(f"      Collected {len(articles)} edu candidates\n")
    if not articles:
        print("FAIL: No educational articles fetched.")
        sys.exit(1)

    already = set(main.load_edu_posted_links())
    selected = main.select_edu_article(articles, slot=slot, exclude_links=already)
    if not selected:
        print("FAIL: No fresh educational article (all candidates already posted).")
        sys.exit(1)
    print(f"[2/3] Selected: {selected.get('title', '')[:80]}")
    print(f"      Source: {selected.get('source')} | {selected.get('link')}")
    print(f"      History skip list: {len(already)} links")

    if not selected.get("image_url"):
        print("      Fetching og:image...")
        selected["image_url"] = main.fetch_og_image(selected.get("link", ""))

    print("\n[3/3] Generating styled educational post via LLM...\n")
    post_text = main.generate_educational_post(selected)
    cleaned = main.clean_html_for_telegram(post_text or "", post_type="edu")
    print("─" * 60)
    print(cleaned)
    print("─" * 60)
    if selected.get("image_url"):
        print(f"\n📷 Image: {selected['image_url']}")
    else:
        print("\n📷 Image: none — Telegram link preview will be used")
elif mode == "single":
    print("\n[1/2] Fetching articles from RSS feeds...")
    articles = main.fetch_recent_articles()
    print(f"      Collected {len(articles)} articles from feeds\n")
    if not articles:
        print("FAIL: No articles fetched.")
        sys.exit(1)
    print("[2/2] Generating post via LLM...\n")
    post_text, image_url = main.generate_single_rich_post(articles)
    cleaned = main.clean_html_for_telegram(post_text or "", post_type="single")
    print("─" * 60)
    print(cleaned)
    print("─" * 60)
    if image_url:
        print(f"\n📷 Image: {image_url}")
else:
    print("\n[1/2] Fetching articles from RSS feeds...")
    articles = main.fetch_recent_articles()
    print(f"      Collected {len(articles)} articles from feeds\n")
    if not articles:
        print("FAIL: No articles fetched.")
        sys.exit(1)
    print("[2/2] Generating post via LLM...\n")
    digest_text, _items = main.generate_daily_digest(articles)
    cleaned = main.clean_html_for_telegram(digest_text or "", post_type="digest")
    print("─" * 60)
    print(cleaned)
    print("─" * 60)

print("\nDone.")
