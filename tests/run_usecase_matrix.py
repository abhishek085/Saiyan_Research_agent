import json
from datetime import datetime

import agent
from tools.memory import add_message, clear_history, get_summary
from tools.notion import create_subpage


def is_fail_text(text: str) -> bool:
    low = (text or "").lower()
    fail_markers = [
        "error",
        "blocked",
        "not set",
        "not configured",
        "not accessible",
        "unknown tool",
        "reached max tool rounds",
        "bot not ready",
        "could not",
        "traceback",
        "exception",
    ]
    return any(marker in low for marker in fail_markers)


def run_matrix() -> dict:
    results = []
    user_id = "copilot-test-user"
    channel_id = "1234567890"

    cases = [
        (1, "search SLM benchmarks 2026"),
        (2, "what's new with Ollama this month?"),
        (3, "https://github.com/vllm-project/vllm"),
        (4, "https://x.com/kimi_moonshot/status/2046249571882500354?s=12"),
        (5, "read https://8thlight.com/insights/mcp-servers-and-the-model-context-protocol"),
        (6, "write LinkedIn post about local LLMs vs cloud"),
        (7, "write substack note on Gemma 2 performance"),
        (8, "write substack post about running agents on mini PCs"),
        (9, "write short note summarizing Ollama vs LM Studio"),
        (10, "search workspace for research"),
        (11, "read root page"),
        (12, "inspect workspace"),
        (13, "create subpage 'Test Page' with content 'Hello world'"),
        (14, "create database 'Test Tasks'"),
        (15, "create task list 'Daily Tasks' with tasks ['Review SLMs', 'Test agent', 'Write post']"),
        (16, "add to database [DB_ID] title 'Test task' status In Progress tags SLM,test"),
        (17, "query database [DB_ID] filter_status Todo"),
        (18, "add calendar entry [DB_ID] title 'Agent demo' date 2026-04-25 notes 'Show Nokast team'"),
        (22, "list drive files query AI"),
        (23, "send discord message #general 'Agent test successful'"),
        (24, "find SLM repos on GitHub, write LinkedIn post about top 3, save to Notion"),
        (25, "search notion for O1A, read that page, create task list from key points"),
        (26, "read my Drive doc 'clawcamp_judging_summary', summarize in 5 bullets, save as Notion subpage"),
    ]

    clear_history(user_id)

    for case_id, prompt in cases:
        try:
            response = agent.agent_loop_sync(user_id, prompt, channel_id)
            status = "FAIL" if is_fail_text(response) else "PASS"
            results.append(
                {
                    "id": case_id,
                    "prompt": prompt,
                    "status": status,
                    "response": (response or "")[:500],
                }
            )
        except Exception as exc:
            results.append(
                {
                    "id": case_id,
                    "prompt": prompt,
                    "status": "FAIL",
                    "response": f"Exception: {exc}",
                }
            )

    # 19) !history (after 3+ messages)
    try:
        summary_before = get_summary(user_id)
        status = "PASS" if summary_before and "No conversation history" not in summary_before else "FAIL"
        results.append(
            {
                "id": 19,
                "prompt": "!history",
                "status": status,
                "response": (summary_before or "")[:500],
            }
        )
    except Exception as exc:
        results.append({"id": 19, "prompt": "!history", "status": "FAIL", "response": f"Exception: {exc}"})

    # 20) !clear then !history
    try:
        clear_history(user_id)
        summary_after = get_summary(user_id)
        status = "PASS" if "No conversation history" in summary_after else "FAIL"
        results.append(
            {
                "id": 20,
                "prompt": "!clear then !history",
                "status": status,
                "response": (summary_after or "")[:500],
            }
        )
    except Exception as exc:
        results.append(
            {"id": 20, "prompt": "!clear then !history", "status": "FAIL", "response": f"Exception: {exc}"}
        )

    # 21) !save command path equivalent
    try:
        add_message(user_id, "user", "test save")
        add_message(user_id, "assistant", "test reply")
        summary = get_summary(user_id)
        save_result = create_subpage(
            title=f"Chat Log Test {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            content=summary,
        )
        status = "FAIL" if is_fail_text(save_result) else "PASS"
        results.append({"id": 21, "prompt": "!save", "status": status, "response": save_result[:500]})
    except Exception as exc:
        results.append({"id": 21, "prompt": "!save", "status": "FAIL", "response": f"Exception: {exc}"})

    results.sort(key=lambda r: r["id"])

    categories = {
        "Web Search & URL Handling": [1, 2, 3, 4, 5],
        "Content Generation": [6, 7, 8, 9],
        "Notion Operations": [10, 11, 12, 13, 14, 15],
        "Database & Calendar": [16, 17, 18],
        "Memory & Commands": [19, 20, 21],
        "Drive & Discord": [22, 23],
        "Complex Workflows": [24, 25, 26],
    }

    category_summary = {}
    for name, ids in categories.items():
        subset = [r for r in results if r["id"] in ids]
        passed = sum(1 for r in subset if r["status"] == "PASS")
        failed = sum(1 for r in subset if r["status"] == "FAIL")
        category_summary[name] = {
            "status": "PASS" if failed == 0 else "FAIL",
            "pass": passed,
            "fail": failed,
        }

    return {"categories": category_summary, "results": results}


if __name__ == "__main__":
    print(json.dumps(run_matrix(), indent=2))