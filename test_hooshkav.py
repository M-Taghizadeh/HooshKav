"""
Hooshkav Test Suite — 10 tests covering all major components.

Run with:
    python -m pytest test_hooshkav.py -v
"""

import json
import re
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

import main


# ---------------------------------------------------------------------------
# Test 1: Feed list has exactly 50 RSS feeds + 6 dynamic feeds
# ---------------------------------------------------------------------------
class TestFeedConfiguration(unittest.TestCase):
    def test_rss_feed_count(self):
        """RSS_FEEDS must contain exactly 50 entries."""
        self.assertEqual(len(main.RSS_FEEDS), 50, 
            f"Expected 50 RSS feeds, got {len(main.RSS_FEEDS)}")

    def test_dynamic_feed_count(self):
        """DYNAMIC_SEARCH_FEEDS must contain exactly 6 entries."""
        self.assertEqual(len(main.DYNAMIC_SEARCH_FEEDS), 6,
            f"Expected 6 dynamic feeds, got {len(main.DYNAMIC_SEARCH_FEEDS)}")

    def test_no_duplicate_feed_urls(self):
        """All feed URLs must be unique."""
        all_urls = [url for _, url in main.RSS_FEEDS + main.DYNAMIC_SEARCH_FEEDS]
        self.assertEqual(len(all_urls), len(set(all_urls)), 
            "Duplicate feed URLs found")

    def test_all_feeds_are_https(self):
        """All feed URLs must use HTTPS."""
        for name, url in main.RSS_FEEDS + main.DYNAMIC_SEARCH_FEEDS:
            self.assertTrue(url.startswith("https://"),
                f"Feed '{name}' does not use HTTPS: {url}")

    def test_target_digest_count(self):
        """TARGET_DIGEST_COUNT must be 10."""
        self.assertEqual(main.TARGET_DIGEST_COUNT, 10)


# ---------------------------------------------------------------------------
# Test 2: fetch_recent_articles deduplicates links
# ---------------------------------------------------------------------------
class TestFetchDeduplication(unittest.TestCase):
    def test_no_duplicate_links_in_output(self):
        """fetch_recent_articles must not return two articles with the same link."""
        # Build two fake feeds that return the same link
        fake_entry = MagicMock()
        fake_entry.link = "https://example.com/article-1"
        fake_entry.title = "Test Article"
        fake_entry.summary = "Summary"
        fake_entry.description = ""
        fake_entry.published_parsed = None
        fake_entry.updated_parsed = None
        fake_entry.media_content = []
        fake_entry.media_thumbnail = []
        fake_entry.links = []

        fake_feed = MagicMock()
        fake_feed.entries = [fake_entry]

        with patch("feedparser.parse", return_value=fake_feed):
            articles = main.fetch_recent_articles()

        links = [a["link"] for a in articles]
        self.assertEqual(len(links), len(set(links)),
            "Duplicate links found in fetch_recent_articles output")


# ---------------------------------------------------------------------------
# Test 3: extract_direct_link — returns original link for non-Google feeds
# ---------------------------------------------------------------------------
class TestExtractDirectLink(unittest.TestCase):
    def test_non_google_feed_returns_entry_link(self):
        """For non-Google feeds, extract_direct_link must return entry.link."""
        entry = MagicMock()
        entry.link = "https://techcrunch.com/2026/08/17/some-article/"
        entry.source = {}
        entry.links = []
        result = main.extract_direct_link(entry, "https://techcrunch.com/feed/")
        self.assertEqual(result, "https://techcrunch.com/2026/08/17/some-article/")

    def test_google_feed_uses_source_href(self):
        """For Google News feeds, extract_direct_link must prefer source.href."""
        entry = MagicMock()
        entry.link = "https://news.google.com/rss/articles/CBMI..."
        entry.source = {"href": "https://venturebeat.com/2026/08/17/real-article/"}
        entry.links = []
        result = main.extract_direct_link(entry, "https://news.google.com/rss/search?q=AI")
        self.assertEqual(result, "https://venturebeat.com/2026/08/17/real-article/")

    def test_google_feed_falls_back_to_google_link(self):
        """If no source href available, falls back to the Google News link itself."""
        entry = MagicMock()
        entry.link = "https://news.google.com/rss/articles/CBMI..."
        entry.source = {}
        entry.links = []
        result = main.extract_direct_link(entry, "https://news.google.com/rss/search?q=AI")
        self.assertEqual(result, "https://news.google.com/rss/articles/CBMI...")


# ---------------------------------------------------------------------------
# Test 4: safe_truncate_html — truncates without breaking tags
# ---------------------------------------------------------------------------
class TestSafeTruncateHtml(unittest.TestCase):
    def test_short_text_unchanged(self):
        """Text shorter than max_chars must be returned unchanged."""
        text = "<b>Hello</b> world"
        self.assertEqual(main.safe_truncate_html(text, 100), text)

    def test_truncation_closes_open_b_tag(self):
        """Truncation must close any unclosed <b> tag."""
        text = "<b>This is a very long bold text that goes on and on"
        result = main.safe_truncate_html(text, 30)
        self.assertLessEqual(len(result), 40)  # some overhead for closing tag
        self.assertIn("</b>", result)

    def test_truncation_closes_open_a_tag(self):
        """Truncation must close any unclosed <a> tag when tag is complete but content is cut."""
        text = 'Read more at <a href="https://example.com">this very long link text that gets cut off here and goes on'
        # limit=60 keeps the full <a href="..."> tag but cuts the inner text
        result = main.safe_truncate_html(text, 60)
        self.assertIn("</a>", result)

    def test_truncation_removes_incomplete_opening_tag(self):
        """A partial tag at the truncation boundary must be removed."""
        # text is longer than limit; truncation lands in the middle of a tag
        text = "Normal text that is long enough <b"
        result = main.safe_truncate_html(text, 33)
        self.assertNotIn("<b", result)


# ---------------------------------------------------------------------------
# Test 5: clean_html_for_telegram — strips markdown, balances tags
# ---------------------------------------------------------------------------
class TestCleanHtmlForTelegram(unittest.TestCase):
    def test_strips_code_fence(self):
        """Markdown ```html fences must be stripped."""
        text = "```html\n<b>مهم‌ترین‌های ۲۴ ساعت</b>\n```"
        result = main.clean_html_for_telegram(text, post_type="digest")
        self.assertNotIn("```", result)

    def test_converts_markdown_links(self):
        """Markdown [title](url) links must be converted to HTML <a> tags."""
        text = "خبر مهم: [OpenAI](https://openai.com) یک مدل جدید معرفی کرد."
        result = main.clean_html_for_telegram(text, post_type="single")
        self.assertIn('<a href="https://openai.com">', result)
        self.assertNotIn("[OpenAI]", result)

    def test_balances_unclosed_b_tag(self):
        """Unclosed <b> tags must be closed."""
        text = "<b>عنوان خبر بدون بسته شدن"
        result = main.clean_html_for_telegram(text, post_type="single")
        self.assertIn("</b>", result)

    def test_removes_unsupported_tags(self):
        """Unsupported HTML tags like <div>, <p>, <span> must be removed."""
        text = "<div><p>محتوای خبر</p></div>"
        result = main.clean_html_for_telegram(text, post_type="single")
        self.assertNotIn("<div>", result)
        self.assertNotIn("<p>", result)
        self.assertIn("محتوای خبر", result)


# ---------------------------------------------------------------------------
# Test 6: select_best_article_for_single_post — LLM fallback behavior
# ---------------------------------------------------------------------------
class TestSelectBestArticle(unittest.TestCase):
    def _make_articles(self, n=5, with_image=True):
        return [
            {
                "source": f"Source {i}",
                "title": f"AI Article {i}",
                "link": f"https://example.com/{i}",
                "summary": f"Summary {i}",
                "image_url": f"https://img.example.com/{i}.jpg" if with_image else None,
                "published": None,
            }
            for i in range(n)
        ]

    def test_llm_valid_index_is_respected(self):
        """When LLM returns a valid index, that article must be selected."""
        articles = self._make_articles(5)
        with patch.object(main, "generate_llm_text", return_value="3"):
            result = main.select_best_article_for_single_post(articles)
        self.assertEqual(result["title"], "AI Article 3")

    def test_fallback_to_first_with_image_when_llm_fails(self):
        """When LLM raises an exception, fallback must be first article with image."""
        articles = self._make_articles(5, with_image=False)
        articles[2]["image_url"] = "https://img.example.com/2.jpg"
        with patch.object(main, "generate_llm_text", side_effect=RuntimeError("LLM down")):
            result = main.select_best_article_for_single_post(articles)
        self.assertEqual(result["title"], "AI Article 2")

    def test_fallback_to_first_when_no_image_and_llm_fails(self):
        """When no article has an image, must return None (no post without image)."""
        articles = self._make_articles(5, with_image=False)
        with patch.object(main, "generate_llm_text", side_effect=RuntimeError("LLM down")):
            result = main.select_best_article_for_single_post(articles)
        self.assertIsNone(result)

    def test_out_of_range_index_triggers_fallback(self):
        """If LLM returns an index >= len(articles), fallback must kick in."""
        articles = self._make_articles(3)
        with patch.object(main, "generate_llm_text", return_value="99"):
            result = main.select_best_article_for_single_post(articles)
        # Should fallback to first article with image
        self.assertIn(result["title"], [a["title"] for a in articles])


# ---------------------------------------------------------------------------
# Test 7: _telegram_request — retries on 429, gives up after max retries
# ---------------------------------------------------------------------------
class TestTelegramRetry(unittest.TestCase):
    def test_retries_on_429_then_succeeds(self):
        """Should retry after 429 and return the successful response."""
        fail_resp = MagicMock()
        fail_resp.ok = False
        fail_resp.status_code = 429
        fail_resp.json.return_value = {"parameters": {"retry_after": 0}}

        ok_resp = MagicMock()
        ok_resp.ok = True
        ok_resp.status_code = 200

        with patch("requests.post", side_effect=[fail_resp, ok_resp]):
            with patch("time.sleep"):  # don't actually sleep in tests
                result = main._telegram_request("sendMessage", {"chat_id": "123", "text": "hi"})

        self.assertTrue(result.ok)

    def test_returns_last_response_after_all_retries_exhausted(self):
        """After all retries are exhausted, the last response must be returned."""
        fail_resp = MagicMock()
        fail_resp.ok = False
        fail_resp.status_code = 429
        fail_resp.json.return_value = {"parameters": {"retry_after": 0}}

        with patch("requests.post", return_value=fail_resp):
            with patch("time.sleep"):
                result = main._telegram_request("sendMessage", {}, retries=3)

        self.assertFalse(result.ok)


# ---------------------------------------------------------------------------
# Test 8: generate_llm_text — fallback chain works correctly
# ---------------------------------------------------------------------------
class TestLLMFallback(unittest.TestCase):
    def test_returns_gemini_result_when_available(self):
        """generate_llm_text must return Gemini result without calling Groq."""
        with patch.object(main, "call_gemini", return_value="gemini output"):
            with patch.object(main, "call_groq") as mock_groq:
                result = main.generate_llm_text("sys", "user")
        self.assertEqual(result, "gemini output")
        mock_groq.assert_not_called()

    def test_falls_back_to_groq_when_gemini_fails(self):
        """When Gemini returns None, must fall back to Groq."""
        with patch.object(main, "call_gemini", return_value=None):
            with patch.object(main, "call_groq", return_value="groq output"):
                result = main.generate_llm_text("sys", "user")
        self.assertEqual(result, "groq output")

    def test_falls_back_to_openrouter_when_gemini_and_groq_fail(self):
        """When Gemini and Groq both return None, must fall back to OpenRouter."""
        with patch.object(main, "call_gemini", return_value=None):
            with patch.object(main, "call_groq", return_value=None):
                with patch.object(main, "call_openrouter", return_value="openrouter output"):
                    result = main.generate_llm_text("sys", "user")
        self.assertEqual(result, "openrouter output")

    def test_raises_when_all_providers_fail(self):
        """Must raise RuntimeError when all three providers return None."""
        with patch.object(main, "call_gemini", return_value=None):
            with patch.object(main, "call_groq", return_value=None):
                with patch.object(main, "call_openrouter", return_value=None):
                    with self.assertRaises(RuntimeError):
                        main.generate_llm_text("sys", "user")


# ---------------------------------------------------------------------------
# Test 9: send_telegram_post — sends photo when image_url provided
# ---------------------------------------------------------------------------
class TestSendTelegramPost(unittest.TestCase):
    def setUp(self):
        # Patch the bot token so the function doesn't raise
        self.token_patcher = patch.object(main, "TELEGRAM_BOT_TOKEN", "fake_token")
        self.token_patcher.start()

    def tearDown(self):
        self.token_patcher.stop()

    def test_uses_sendphoto_when_image_url_given(self):
        """When image_url is provided, sendPhoto must be attempted first."""
        ok_resp = MagicMock()
        ok_resp.ok = True

        with patch.object(main, "_telegram_request", return_value=ok_resp) as mock_req:
            main.send_telegram_post("@test", "<b>خبر</b>", image_url="https://img.example.com/1.jpg", post_type="single")

        first_call_method = mock_req.call_args_list[0][0][0]
        self.assertEqual(first_call_method, "sendPhoto")

    def test_falls_back_to_sendmessage_when_sendphoto_fails(self):
        """When sendPhoto fails, must fall back to sendMessage."""
        fail_resp = MagicMock()
        fail_resp.ok = False
        fail_resp.status_code = 400
        fail_resp.text = "Bad Request"

        ok_resp = MagicMock()
        ok_resp.ok = True

        with patch.object(main, "_telegram_request", side_effect=[fail_resp, ok_resp]) as mock_req:
            main.send_telegram_post("@test", "<b>خبر</b>", image_url="https://img.example.com/1.jpg", post_type="single")

        methods_called = [call[0][0] for call in mock_req.call_args_list]
        self.assertIn("sendPhoto", methods_called)
        self.assertIn("sendMessage", methods_called)

    def test_raises_when_no_token(self):
        """Must raise RuntimeError when TELEGRAM_BOT_TOKEN is not set."""
        with patch.object(main, "TELEGRAM_BOT_TOKEN", None):
            with self.assertRaises(RuntimeError):
                main.send_telegram_post("@test", "خبر")


# ---------------------------------------------------------------------------
# Test 10: check_and_handle_on_demand_requests — authorization check
# ---------------------------------------------------------------------------
class TestOnDemandAuthorization(unittest.TestCase):
    def _make_update(self, username, text, update_id=1, chat_id=12345):
        return {
            "update_id": update_id,
            "message": {
                "from": {"username": username},
                "chat": {"id": chat_id},
                "text": text,
            }
        }

    def _mock_get(self, updates):
        resp = MagicMock()
        resp.ok = True
        resp.json.return_value = {"result": updates}
        return resp

    def test_authorized_user_command_added_to_queue(self):
        """Commands from the authorized user must be added to on_demand_chats."""
        update = self._make_update(main.ALLOWED_TELEGRAM_USER, "/digest")

        with patch("requests.get", return_value=self._mock_get([update])):
            with patch.object(main, "send_telegram_post"):  # suppress deny messages
                result = main.check_and_handle_on_demand_requests()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][1], "digest")

    def test_unauthorized_user_gets_empty_result(self):
        """Commands from unauthorized users must not be added to the queue."""
        update = self._make_update("some_random_user", "/digest")
        deny_calls = []

        with patch("requests.get", return_value=self._mock_get([update])):
            with patch.object(main, "send_telegram_post", side_effect=lambda *a, **kw: deny_calls.append(a)):
                result = main.check_and_handle_on_demand_requests()

        self.assertEqual(result, [])
        # Deny message must have been sent
        self.assertTrue(len(deny_calls) > 0)

    def test_single_mode_detected_correctly(self):
        """/single command must result in mode='single'."""
        update = self._make_update(main.ALLOWED_TELEGRAM_USER, "/single")

        with patch("requests.get", return_value=self._mock_get([update])):
            result = main.check_and_handle_on_demand_requests()

        self.assertEqual(result[0][1], "single")

    def test_empty_updates_returns_empty_list(self):
        """When there are no pending updates, must return an empty list."""
        with patch("requests.get", return_value=self._mock_get([])):
            result = main.check_and_handle_on_demand_requests()
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# Test 11: deduplicate_and_score — groups similar titles, assigns mention_count
# ---------------------------------------------------------------------------
class TestDeduplicateAndScore(unittest.TestCase):
    def _make(self, title, source, image=None, published="2026-08-17T10:00:00+00:00"):
        return {
            "title": title, "source": source, "link": f"https://example.com/{hash(title)}",
            "summary": "", "image_url": image, "published": published,
        }

    def test_identical_titles_collapsed_to_one(self):
        """Two articles with identical titles must be merged into one."""
        arts = [
            self._make("Stripe buys OpenRouter for 7 billion dollars", "TechCrunch"),
            self._make("Stripe buys OpenRouter for 7 billion dollars", "VentureBeat"),
        ]
        result = main.deduplicate_and_score(arts)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["mention_count"], 2)

    def test_very_similar_titles_collapsed(self):
        """Near-duplicate titles with high word overlap must be merged."""
        arts = [
            self._make("Stripe acquires OpenRouter AI gateway startup for over 7 billion", "TechCrunch"),
            self._make("Stripe acquires OpenRouter AI gateway startup for over 7 billion dollars deal", "Reuters"),
        ]
        result = main.deduplicate_and_score(arts)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["mention_count"], 2)

    def test_different_stories_not_collapsed(self):
        """Unrelated articles must remain as separate entries."""
        arts = [
            self._make("Stripe buys OpenRouter for 7 billion dollars", "TechCrunch"),
            self._make("OpenAI disbands its safety preparedness team completely", "The Verge"),
        ]
        result = main.deduplicate_and_score(arts)
        self.assertEqual(len(result), 2)

    def test_mention_count_one_for_unique_story(self):
        """A story covered by only one source must have mention_count=1."""
        arts = [self._make("Some unique AI story nobody else covered", "TechCrunch")]
        result = main.deduplicate_and_score(arts)
        self.assertEqual(result[0]["mention_count"], 1)

    def test_representative_prefers_article_with_image(self):
        """When merging, the representative must be the article that has an image."""
        arts = [
            self._make("Stripe acquires OpenRouter AI gateway startup", "TechCrunch", image=None),
            self._make("Stripe acquires OpenRouter the AI gateway company", "VentureBeat", image="https://img.example.com/1.jpg"),
        ]
        result = main.deduplicate_and_score(arts)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["image_url"], "https://img.example.com/1.jpg")

    def test_also_covered_by_populated(self):
        """also_covered_by must contain sources that were merged away."""
        arts = [
            self._make("Stripe buys OpenRouter for seven billion", "TechCrunch"),
            self._make("Stripe buys OpenRouter for seven billion", "Reuters"),
        ]
        result = main.deduplicate_and_score(arts)
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0]["also_covered_by"]), 1)

    def test_sorted_by_mention_count_descending(self):
        """Output must be sorted so highest mention_count articles come first."""
        arts = [
            self._make("Unique story A only on TechCrunch", "TechCrunch"),
            self._make("Big story covered everywhere version one", "TechCrunch"),
            self._make("Big story covered everywhere version two", "Reuters"),
            self._make("Big story covered everywhere version three", "VentureBeat"),
        ]
        result = main.deduplicate_and_score(arts)
        # The merged "big story" should be first
        self.assertGreaterEqual(result[0]["mention_count"], result[-1]["mention_count"])

    def test_empty_input_returns_empty(self):
        """Empty input must return empty list without error."""
        result = main.deduplicate_and_score([])
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# Test 12: digest helpers — guaranteed links on every item
# ---------------------------------------------------------------------------
class TestDigestHelpers(unittest.TestCase):
    def _make_articles(self, n=5):
        return [
            {
                "title": f"Article {i}",
                "source": f"Source {i}",
                "link": f"https://example.com/{i}",
                "summary": f"Summary {i}",
                "image_url": None,
                "published": "2026-08-17T10:00:00+00:00",
                "mention_count": n - i,
                "also_covered_by": [],
            }
            for i in range(n)
        ]

    def test_inject_link_replaces_highlight_word(self):
        """highlight_word must become a clickable link inside the summary."""
        result = main._inject_link_in_summary(
            "OpenAI یک مدل جدید معرفی کرد",
            "OpenAI",
            "https://example.com/1",
        )
        self.assertIn('<a href="https://example.com/1">OpenAI</a>', result)

    def test_inject_link_appends_when_word_missing(self):
        """When highlight_word is absent, a fallback link must be appended."""
        result = main._inject_link_in_summary(
            "یک خبر مهم درباره هوش مصنوعی",
            "کلمه_ناموجود",
            "https://example.com/2",
        )
        self.assertIn('<a href="https://example.com/2">مطالعه خبر</a>', result)

    def test_build_digest_html_includes_link_on_every_item(self):
        """Every digest item must contain an <a href> tag."""
        items = [
            {"link": "https://example.com/1", "summary": "خبر اول", "highlight_word": "خبر"},
            {"link": "https://example.com/2", "summary": "خبر دوم", "highlight_word": "دوم"},
        ]
        html = main._build_digest_html(items)
        self.assertIn("مهم‌ترین‌های ۲۴ ساعت", html)
        self.assertEqual(html.count("<a href="), 2)

    def test_parse_digest_items_validates_links(self):
        """Parsed items must use links that exist in the input articles."""
        raw = json.dumps({
            "items": [
                {
                    "link": "https://example.com/1",
                    "summary": "خبر معتبر",
                    "highlight_word": "خبر",
                },
                {
                    "link": "https://unknown.com/999",
                    "summary": "خبر نامعتبر",
                    "highlight_word": "خبر",
                },
            ]
        })
        articles = self._make_articles(5)
        items = main._parse_digest_items(raw, articles)
        links = {item["link"] for item in items}
        self.assertIn("https://example.com/1", links)
        self.assertNotIn("https://unknown.com/999", links)

    def test_parse_digest_items_fills_to_target_count(self):
        """Parser must fill up to TARGET_DIGEST_COUNT using top articles."""
        raw = json.dumps({
            "items": [
                {
                    "link": "https://example.com/0",
                    "summary": "تنها خبر معتبر",
                    "highlight_word": "تنها",
                }
            ]
        })
        articles = self._make_articles(main.TARGET_DIGEST_COUNT)
        items = main._parse_digest_items(raw, articles)
        self.assertEqual(len(items), main.TARGET_DIGEST_COUNT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
