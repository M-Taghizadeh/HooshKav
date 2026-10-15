"""
CLI preview test: fetches real articles, calls the LLM, and prints the
generated post directly in the terminal — no Telegram channel send.

Run with:
    python test_send.py digest
    python test_send.py single
    python test_send.py edu              # today's 2 picks (titles only)
    python test_send.py edu full         # today's 2 picks + full post text
    python test_send.py edu 0            # only slot 0 full post
    python test_send.py edu 1 full       # only slot 1 full post
"""

import sys
import main

args = [a.lower() for a in sys.argv[1:]]
mode = args[0] if args else "digest"

# edu flags
edu_full = "full" in args
edu_slot = None
for a in args[1:]:
    if a.isdigit():
        edu_slot = int(a)

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
    print(f"[2/3] Ranking today's top {main.TARGET_EDU_DAILY} (skipping {len(already)} posted)...")

    # Force / reuse daily ranking (same path as production)
    picks = []
    for slot in range(main.TARGET_EDU_DAILY):
        # When previewing a single slot, still warm the daily cache via slot 0 first if needed
        selected = main.select_edu_article(articles, slot=slot, exclude_links=already)
        if selected:
            picks.append(selected)

    if not picks:
        print("FAIL: No fresh educational articles for today.")
        sys.exit(1)

    print("\n" + "═" * 60)
    print("آموزش‌های انتخاب‌شده برای امروز (قبل از ارسال به کانال)")
    print("═" * 60)
    for i, p in enumerate(picks):
        mark = "← ظهر" if i == 0 else ("← عصر" if i == 1 else "")
        print(f"\n#{i + 1} {mark}")
        print(f"  عنوان : {p.get('title', '')}")
        print(f"  منبع  : {p.get('source', '')}")
        print(f"  لینک  : {p.get('link', '')}")
        if p.get("pick_reason"):
            print(f"  دلیل  : {p['pick_reason']}")

    # Which slots to fully generate
    slots_to_render = []
    if edu_slot is not None:
        if edu_slot < len(picks):
            slots_to_render = [edu_slot]
        else:
            print(f"\nFAIL: slot {edu_slot} out of range (only {len(picks)} picks).")
            sys.exit(1)
    elif edu_full:
        slots_to_render = list(range(len(picks)))

    if not slots_to_render:
        print("\n(فقط عنوان‌ها نمایش داده شد.)")
        print("برای متن کامل هر دو پست:")
        print("  python test_send.py edu full")
        print("برای فقط یکی:")
        print("  python test_send.py edu 0 full")
        print("  python test_send.py edu 1 full")
    else:
        print(f"\n[3/3] Generating full post text for slot(s) {slots_to_render}...\n")
        for slot in slots_to_render:
            selected = picks[slot]
            if not selected.get("image_url"):
                selected["image_url"] = main.fetch_og_image(selected.get("link", ""))

            post_text = main.generate_educational_post(selected)
            cleaned = main.clean_html_for_telegram(post_text or "", post_type="edu")
            print("─" * 60)
            print(f"SLOT {slot} — FULL PREVIEW (not sent to channel)")
            print("─" * 60)
            print(cleaned)
            print("─" * 60)
            if selected.get("image_url"):
                print(f"📷 Image: {selected['image_url']}\n")
            else:
                print("📷 Image: none — link preview would be used\n")

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

print("\nDone. (Nothing was sent to the Telegram channel.)")
