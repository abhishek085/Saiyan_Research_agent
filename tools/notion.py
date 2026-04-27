import os
import re
from typing import Any

from dotenv import load_dotenv
from notion_client import Client

load_dotenv()

NOTION_ID_RE = re.compile(
    r"([0-9a-fA-F]{32}|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
)

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _normalize_notion_id(raw: str | None) -> str:
    if not raw:
        return ""
    hex_only = re.sub(r"[^0-9a-fA-F]", "", raw)
    if len(hex_only) != 32:
        return raw.strip()
    return (
        f"{hex_only[:8]}-{hex_only[8:12]}-{hex_only[12:16]}-"
        f"{hex_only[16:20]}-{hex_only[20:]}"
    )

def _get_notion_client() -> Client:
    load_dotenv(override=False)
    return Client(auth=os.getenv("NOTION_API_KEY"))

def _get_root_page_id() -> str:
    load_dotenv(override=False)
    return _normalize_notion_id(os.getenv("NOTION_PARENT_PAGE_ID"))

def _format_notion_error(error: Exception) -> str:
    message = str(error)
    lowered = message.lower()
    if "api token is invalid" in lowered or "unauthorized" in lowered:
        return "Notion API access is not configured correctly. Update NOTION_API_KEY and restart the agent."
    if "object_not_found" in lowered or "could not find" in lowered or "restricted_resource" in lowered:
        return "This Notion page or database is not accessible to the integration. Check share settings and the ID."
    return f"Error: {message}"

def _rich_text_to_plain(rich_text: list[dict[str, Any]]) -> str:
    return "".join(part.get("plain_text", "") for part in rich_text or [])

def _extract_title_from_page(page: dict[str, Any]) -> str:
    props = page.get("properties", {})
    for prop in props.values():
        if isinstance(prop, dict) and prop.get("type") == "title":
            title = _rich_text_to_plain(prop.get("title", [])).strip()
            if title:
                return title
    if page.get("object") == "database":
        title = _rich_text_to_plain(page.get("title", [])).strip()
        if title:
            return title
    return "Untitled"

def _extract_notion_page_mentions(rich_text: list[dict[str, Any]]) -> list[str]:
    found = []
    seen = set()

    def add(candidate: str | None):
        if not candidate:
            return
        match = NOTION_ID_RE.search(candidate)
        if not match:
            return
        normalized = _normalize_notion_id(match.group(1))
        if normalized and normalized not in seen:
            seen.add(normalized)
            found.append(normalized)

    for item in rich_text or []:
        mention = item.get("mention", {})
        if mention.get("type") == "page":
            add(mention.get("page", {}).get("id"))
        href = item.get("href")
        if isinstance(href, str) and "notion.so" in href:
            add(href)
        text_obj = item.get("text") if isinstance(item.get("text"), dict) else {}
        text_link = text_obj.get("link") or {}
        url = text_link.get("url") if isinstance(text_link, dict) else None
        if isinstance(url, str) and "notion.so" in url:
            add(url)

    return found

def _paginate_block_children(block_id: str) -> list[dict[str, Any]]:
    blocks = []
    cursor = None
    while True:
        kwargs = {"block_id": block_id, "page_size": 100}
        if cursor:
            kwargs["start_cursor"] = cursor
        response = _get_notion_client().blocks.children.list(**kwargs)
        blocks.extend(response.get("results", []))
        if not response.get("has_more"):
            break
        cursor = response.get("next_cursor")
        if not cursor:
            break
    return blocks

def _safe_page_title(page_id: str) -> str:
    try:
        page = _get_notion_client().pages.retrieve(page_id=page_id)
        return _extract_title_from_page(page)
    except Exception:
        return page_id

def _summarize_database(database_id: str, depth: int) -> list[str]:
    indent = "  " * depth
    lines = []
    try:
        results = _get_notion_client().databases.query(database_id=database_id, page_size=5)
        for row in results.get("results", []):
            title = _extract_title_from_page(row)
            lines.append(f"{indent}- Row: {title} → {row['id']}")
    except Exception as e:
        lines.append(f"{indent}- Database read error: {e}")
    return lines

def _read_block_tree(block_id: str, depth: int, max_depth: int, follow_links: bool, visited: set[str]) -> list[str]:
    lines = []
    indent = "  " * depth

    for block in _paginate_block_children(block_id):
        btype = block["type"]

        if btype == "child_page":
            child_id = block["id"]
            title = block["child_page"].get("title", "Untitled")
            lines.append(f"{indent}[Subpage] {title} → {child_id}")
            if depth < max_depth and child_id not in visited:
                visited.add(child_id)
                lines.extend(_read_block_tree(child_id, depth + 1, max_depth, follow_links, visited))
            continue

        if btype == "child_database":
            db_id = block["id"]
            title = block["child_database"].get("title", "Untitled Database")
            lines.append(f"{indent}[Database] {title} → {db_id}")
            if depth < max_depth:
                lines.extend(_summarize_database(db_id, depth + 1))
            continue

        block_data = block.get(btype) if isinstance(block.get(btype), dict) else {}
        rich_text = block_data.get("rich_text", [])
        text = _rich_text_to_plain(rich_text).strip()
        if text:
            lines.append(f"{indent}{text}")

        if follow_links:
            for linked_page_id in _extract_notion_page_mentions(rich_text):
                linked_title = _safe_page_title(linked_page_id)
                lines.append(f"{indent}[Linked page] {linked_title} → {linked_page_id}")
                if depth < max_depth and linked_page_id not in visited:
                    visited.add(linked_page_id)
                    try:
                        lines.extend(_read_block_tree(linked_page_id, depth + 1, max_depth, follow_links, visited))
                    except Exception as e:
                        lines.append(f"{indent}  Link read error: {e}")

    return lines

def _make_blocks(content: str) -> list:
    """Smart block parser — detects bullets, numbered lists, headings, code, quotes, todos"""
    blocks = []
    lines = content.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        if line.startswith("### "):
            blocks.append({"object": "block", "type": "heading_3",
                "heading_3": {"rich_text": [{"type": "text", "text": {"content": line[4:]}}]}})
        elif line.startswith("## "):
            blocks.append({"object": "block", "type": "heading_2",
                "heading_2": {"rich_text": [{"type": "text", "text": {"content": line[3:]}}]}})
        elif line.startswith("# "):
            blocks.append({"object": "block", "type": "heading_1",
                "heading_1": {"rich_text": [{"type": "text", "text": {"content": line[2:]}}]}})
        elif line.startswith("- ") or line.startswith("* "):
            blocks.append({"object": "block", "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": line[2:]}}]}})
        elif len(line) > 2 and line[0].isdigit() and line[1] in ".)" and line[2] == " ":
            blocks.append({"object": "block", "type": "numbered_list_item",
                "numbered_list_item": {"rich_text": [{"type": "text", "text": {"content": line[3:]}}]}})
        elif line.startswith("[ ] ") or line.startswith("[x] ") or line.startswith("[X] "):
            checked = line.startswith("[x]") or line.startswith("[X]")
            blocks.append({"object": "block", "type": "to_do",
                "to_do": {
                    "rich_text": [{"type": "text", "text": {"content": line[4:]}}],
                    "checked": checked
                }})
        elif line in ("---", "___", "***"):
            blocks.append({"object": "block", "type": "divider", "divider": {}})
        elif line.startswith("```"):
            lang = line[3:].strip() or "plain text"
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            blocks.append({"object": "block", "type": "code",
                "code": {
                    "rich_text": [{"type": "text", "text": {"content": "\n".join(code_lines)}}],
                    "language": lang
                }})
        elif line.startswith("> "):
            blocks.append({"object": "block", "type": "quote",
                "quote": {"rich_text": [{"type": "text", "text": {"content": line[2:]}}]}})
        elif line.startswith("! "):
            blocks.append({"object": "block", "type": "callout",
                "callout": {
                    "rich_text": [{"type": "text", "text": {"content": line[2:]}}],
                    "icon": {"type": "emoji", "emoji": "💡"}
                }})
        else:
            blocks.append({"object": "block", "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": line[:2000]}}]}})

        i += 1

    return blocks

# ─── READ (workspace-wide) ────────────────────────────────────────────────────

def search_workspace(query: str = "", page_size: int = 20) -> str:
    try:
        response = _get_notion_client().search(query=query or "", page_size=max(1, min(page_size, 50)))
        output = []
        for result in response.get("results", []):
            if result["object"] == "page":
                title = _extract_title_from_page(result)
                output.append(f"📄 {title} → ID: {result['id']}")
            elif result["object"] == "database":
                title = _extract_title_from_page(result)
                output.append(f"🗄️ {title} → ID: {result['id']}")
        if not output:
            return "No accessible Notion results found. Share relevant pages or databases with the integration first."
        if query:
            return "\n".join(output)
        return "Accessible Notion pages and databases:\n" + "\n".join(output)
    except Exception as e:
        return _format_notion_error(e)

def read_page(page_id: str, max_depth: int = 2, follow_links: bool = True) -> str:
    try:
        normalized_id = _normalize_notion_id(page_id)
        title = _safe_page_title(normalized_id)
        visited = {normalized_id}
        body = _read_block_tree(normalized_id, depth=0, max_depth=max(0, min(max_depth, 5)), follow_links=follow_links, visited=visited)
        header = [f"Page: {title}", f"ID: {normalized_id}"]
        return "\n".join(header + body) if body else f"Page: {title}\nEmpty page."
    except Exception as e:
        return _format_notion_error(e)

def read_root_page() -> str:
    root_page_id = _get_root_page_id()
    if not root_page_id:
        return "NOTION_PARENT_PAGE_ID is not set."
    return read_page(root_page_id, max_depth=2, follow_links=True)

def inspect_workspace(max_depth: int = 2) -> str:
    summary = search_workspace("", page_size=20)
    root_page_id = _get_root_page_id()
    if not root_page_id:
        return "NOTION_PARENT_PAGE_ID is not set.\n\n" + summary
    root_tree = read_page(root_page_id, max_depth=max_depth, follow_links=True)
    return f"{summary}\n\nShared root tree:\n{root_tree}"

def query_database(database_id: str, filter_status: str = "") -> str:
    try:
        kwargs = {"database_id": database_id, "page_size": 10}
        if filter_status:
            kwargs["filter"] = {"property": "Status", "select": {"equals": filter_status}}
        results = _get_notion_client().databases.query(**kwargs)
        rows = []
        for p in results["results"]:
            title = _extract_title_from_page(p)
            status = p.get("properties", {}).get("Status", {}).get("select") or {}
            rows.append(f"{title} [{status.get('name', '—')}] → {p['id']}")
        return "\n".join(rows) or "No rows."
    except Exception as e:
        return _format_notion_error(e)

# ─── WRITE (only inside ROOT_PAGE_ID) ────────────────────────────────────────

def create_subpage(title: str, content: str = "") -> str:
    try:
        root_page_id = _get_root_page_id()
        if not root_page_id:
            return "NOTION_PARENT_PAGE_ID is not set."
        page = _get_notion_client().pages.create(
            parent={"type": "page_id", "page_id": root_page_id},
            properties={"title": [{"type": "text", "text": {"content": title}}]},
            children=_make_blocks(content) if content else []
        )
        return f"✅ Subpage '{title}' created: {page['url']} | ID: {page['id']}"
    except Exception as e:
        return _format_notion_error(e)

def create_database(title: str) -> str:
    try:
        root_page_id = _get_root_page_id()
        if not root_page_id:
            return "NOTION_PARENT_PAGE_ID is not set."
        db = _get_notion_client().databases.create(
            parent={"type": "page_id", "page_id": root_page_id},
            title=[{"type": "text", "text": {"content": title}}],
            properties={
                "Name": {"title": {}},
                "Status": {"select": {"options": [
                    {"name": "Todo", "color": "red"},
                    {"name": "In Progress", "color": "yellow"},
                    {"name": "Done", "color": "green"}
                ]}},
                "Date": {"date": {}},
                "Tags": {"multi_select": {}}
            }
        )
        return f"✅ Database '{title}' created: {db['url']} | ID: {db['id']}"
    except Exception as e:
        return _format_notion_error(e)

def add_to_database(database_id: str, title: str, content: str = "", status: str = "Todo", tags: list = None) -> str:
    try:
        properties = {
            "Name": {"title": [{"text": {"content": title}}]},
            "Status": {"select": {"name": status}},
        }
        if tags:
            properties["Tags"] = {"multi_select": [{"name": t} for t in tags]}
        page = _get_notion_client().pages.create(
            parent={"database_id": database_id},
            properties=properties,
            children=_make_blocks(content) if content else []
        )
        return f"✅ Added '{title}': {page['url']}"
    except Exception as e:
        return _format_notion_error(e)

def append_to_page(page_id: str, content: str) -> str:
    try:
        _get_notion_client().blocks.children.append(
            block_id=page_id,
            children=_make_blocks(content)
        )
        return f"✅ Appended to {page_id}"
    except Exception as e:
        return _format_notion_error(e)

def archive_page(page_id: str) -> str:
    try:
        _get_notion_client().pages.update(page_id=page_id, archived=True)
        return f"✅ Archived {page_id}"
    except Exception as e:
        return _format_notion_error(e)

def archive_database(database_id: str) -> str:
    try:
        _get_notion_client().databases.update(database_id=database_id, archived=True)
        return f"✅ Database {database_id} archived."
    except Exception as e:
        return _format_notion_error(e)

def create_task_list(title: str, tasks: list) -> str:
    try:
        root_page_id = _get_root_page_id()
        if not root_page_id:
            return "NOTION_PARENT_PAGE_ID is not set."
        blocks = [
            {"object": "block", "type": "heading_2",
             "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Tasks"}}]}}
        ]
        for task in tasks:
            blocks.append({
                "object": "block", "type": "to_do",
                "to_do": {
                    "rich_text": [{"type": "text", "text": {"content": task}}],
                    "checked": False
                }
            })
        page = _get_notion_client().pages.create(
            parent={"type": "page_id", "page_id": root_page_id},
            properties={"title": [{"type": "text", "text": {"content": title}}]},
            children=blocks
        )
        return f"✅ Task list '{title}' created: {page['url']} | ID: {page['id']}"
    except Exception as e:
        return _format_notion_error(e)

def add_calendar_entry(database_id: str, title: str, date: str, notes: str = "", status: str = "Todo") -> str:
    try:
        page = _get_notion_client().pages.create(
            parent={"database_id": database_id},
            properties={
                "Name": {"title": [{"text": {"content": title}}]},
                "Date": {"date": {"start": date}},
                "Status": {"select": {"name": status}},
            },
            children=_make_blocks(notes) if notes else []
        )
        return f"✅ Calendar entry '{title}' on {date}: {page['url']}"
    except Exception as e:
        return _format_notion_error(e)