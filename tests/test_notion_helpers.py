import os
import unittest
from unittest.mock import patch

from tools import notion


class TestNotionHelpers(unittest.TestCase):
    def test_normalize_32_char_id(self):
        raw = "123456781234123412341234567890ab"
        self.assertEqual(
            notion._normalize_notion_id(raw),
            "12345678-1234-1234-1234-1234567890ab",
        )

    def test_extract_page_mention_object(self):
        rich_text = [
            {
                "type": "mention",
                "plain_text": "Roadmap",
                "mention": {
                    "type": "page",
                    "page": {"id": "12345678-1234-1234-1234-1234567890ab"},
                },
            }
        ]
        self.assertEqual(
            notion._extract_notion_page_mentions(rich_text),
            ["12345678-1234-1234-1234-1234567890ab"],
        )

    def test_extract_page_mention_from_notion_url(self):
        rich_text = [
            {
                "type": "text",
                "plain_text": "Spec",
                "href": "https://www.notion.so/My-Page-123456781234123412341234567890ab",
            }
        ]
        self.assertEqual(
            notion._extract_notion_page_mentions(rich_text),
            ["12345678-1234-1234-1234-1234567890ab"],
        )

    def test_extract_page_mention_ignores_empty_text_link(self):
        rich_text = [
            {
                "type": "text",
                "plain_text": "No link here",
                "text": {"content": "No link here", "link": None},
            }
        ]
        self.assertEqual(notion._extract_notion_page_mentions(rich_text), [])

    def test_read_root_page_uses_current_environment_value(self):
        with patch.dict(os.environ, {"NOTION_PARENT_PAGE_ID": "abc123"}, clear=False):
            with patch.object(notion, "read_page", return_value="ok") as mock_read_page:
                result = notion.read_root_page()

        self.assertEqual(result, "ok")
        mock_read_page.assert_called_once_with("abc123", max_depth=2, follow_links=True)


if __name__ == "__main__":
    unittest.main()
