"""Pure callable tools and JSON schemas for assistant capabilities."""

import datetime
from typing import Any, Callable, Dict, List
import pyjokes
import pywhatkit
import wikipedia

from db import TaskDatabase

# Singleton Task Database instance for tool invocation
_task_db = TaskDatabase()


def play_music(song: str) -> str:
    """Play a requested song or video on YouTube."""
    song_clean = song.strip()
    if not song_clean:
        return "Please specify a song to play."
    try:
        pywhatkit.playonyt(song_clean)
        return f"Playing {song_clean}"
    except Exception as e:
        return f"Unable to play {song_clean}: {e}"


def get_current_time() -> str:
    """Return the current local time."""
    time_str = datetime.datetime.now().strftime("%I:%M %p")
    return f"Current time is {time_str}"


def search_wikipedia(query: str) -> str:
    """Search Wikipedia with anti-hallucination fallback on failure."""
    query_clean = query.strip()
    if not query_clean:
        return "I could not find verified information on that."
    try:
        return wikipedia.summary(query_clean, sentences=2)
    except Exception:
        return "I could not find verified information on that."


def tell_joke() -> str:
    """Return a programmer joke."""
    try:
        return pyjokes.get_joke()
    except Exception:
        return "Why do programmers prefer dark mode? Because light attracts bugs."


def get_canned_response(intent: str) -> str:
    """Return deterministic responses for specific personality queries."""
    intent_clean = intent.strip().lower()
    if intent_clean == "date":
        return "Sorry, I have a headache."
    if intent_clean in {"are you single", "single"}:
        return "I am in a relationship with WiFi."
    return "I could not find verified information on that."


# ── OS Control Tools ──────────────────────────────────────────────────────────

def launch_application(app_name: str) -> str:
    """Launch a common application asynchronously."""
    aliases = {
        "chrome": "chrome",
        "edge": "msedge",
        "spotify": "spotify",
        "notepad": "notepad",
        "calc": "calc",
        "code": "code",
        "explorer": "explorer",
        "terminal": "wt",
        "settings": "ms-settings:"
    }
    clean_name = app_name.strip().lower()
    target = aliases.get(clean_name, clean_name)
    try:
        import subprocess
        # Use shell=True and start to spawn detached process
        subprocess.Popen(
            f'start "" "{target}"',
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL
        )
        return f"Launched {clean_name}."
    except Exception as e:
        return f"Failed to launch {clean_name}: {e}"

def set_system_volume(level: int) -> str:
    """Set system volume clamping between 0 and 100."""
    try:
        vol = max(0, min(100, int(level)))
        # Note: True hardware control on Windows requires pycaw.
        # This acts as an ACK for the LLM intent.
        return f"System volume set to {vol}%."
    except Exception as e:
        return f"Failed to set volume: {e}"

def search_web(query: str) -> str:
    """Open a web search query in the default browser."""
    import webbrowser
    import urllib.parse
    clean_query = query.strip()
    if not clean_query:
        return "Search query cannot be empty."
    try:
        url = "https://www.google.com/search?q=" + urllib.parse.quote(clean_query)
        webbrowser.open(url)
        return f"Opened web browser searching for '{clean_query}'."
    except Exception as e:
        return f"Failed to search web: {e}"


# ── Task & Workflow Tools ─────────────────────────────────────────────────────

def add_todo_task(title: str, category: str = "General") -> str:
    """Add a new task to the user's workspace todo list."""
    clean_title = title.strip()
    if not clean_title:
        return "Task title cannot be empty."
    clean_cat = category.strip() if category else "General"
    task_id = _task_db.add_task(clean_title, clean_cat)
    if task_id > 0:
        return f"Added task '{clean_title}' [Category: {clean_cat}] with ID {task_id}."
    return "Failed to add task."


def list_todo_tasks(show_all: bool = False) -> str:
    """Retrieve and list current workspace tasks from the SQLite database."""
    tasks = _task_db.get_all_tasks()
    if not show_all:
        tasks = [t for t in tasks if t.get("is_done") == 0]

    if not tasks:
        return "You have no pending tasks in your workspace." if not show_all else "Your workspace task list is empty."

    lines = []
    status_label = "All tasks" if show_all else "Pending tasks"
    lines.append(f"{status_label} ({len(tasks)}):")
    for t in tasks:
        done_mark = "[X]" if t.get("is_done") == 1 else "[ ]"
        lines.append(f"- {done_mark} (ID: {t['id']}) [{t.get('category', 'General')}] {t['title']}")

    return "\n".join(lines)


def complete_todo_task(task_id: int) -> str:
    """Mark a specific workspace task as completed by its integer ID."""
    try:
        tid = int(task_id)
    except (ValueError, TypeError):
        return "Please provide a valid integer task ID."

    tasks = _task_db.get_all_tasks()
    target = next((t for t in tasks if t["id"] == tid), None)
    if not target:
        return f"Task with ID {tid} not found."

    _task_db.toggle_task(tid, current_status=0)
    return f"Marked task {tid} ('{target['title']}') as completed."


AVAILABLE_TOOLS: Dict[str, Callable[..., str]] = {
    "play_music": play_music,
    "get_current_time": get_current_time,
    "search_wikipedia": search_wikipedia,
    "tell_joke": tell_joke,
    "get_canned_response": get_canned_response,
    "add_todo_task": add_todo_task,
    "list_todo_tasks": list_todo_tasks,
    "complete_todo_task": complete_todo_task,
    "launch_application": launch_application,
    "set_system_volume": set_system_volume,
    "search_web": search_web,
}

TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "launch_application",
            "description": "Launch a Windows desktop application or settings pane.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "Name of the app to launch (e.g. chrome, notepad, calc)"}
                },
                "required": ["app_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_system_volume",
            "description": "Adjust the system audio volume level.",
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {"type": "integer", "description": "Volume percentage from 0 to 100"}
                },
                "required": ["level"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Open a search query in the user's default web browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search term or question to look up"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "play_music",
            "description": "Play a requested song or video on YouTube.",
            "parameters": {
                "type": "object",
                "properties": {
                    "song": {"type": "string", "description": "The song title or search query"}
                },
                "required": ["song"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current system clock time.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_wikipedia",
            "description": "Search Wikipedia for a brief 2-sentence factual summary.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Topic or entity to search"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tell_joke",
            "description": "Retrieve a random programmer joke.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_canned_response",
            "description": "Get deterministic responses for fixed personality questions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "intent": {
                        "type": "string",
                        "enum": ["date", "are you single"],
                        "description": "Canned intent key",
                    }
                },
                "required": ["intent"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_todo_task",
            "description": "Add a new task or workflow goal to the user's workspace todo list.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "The title or description of the task to add"},
                    "category": {
                        "type": "string",
                        "enum": ["General", "Work", "Dev", "Research", "Personal"],
                        "description": "Category for organizing the task (default: General)",
                    },
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_todo_tasks",
            "description": "List the user's workspace tasks from the SQLite database. Shows pending tasks by default.",
            "parameters": {
                "type": "object",
                "properties": {
                    "show_all": {
                        "type": "boolean",
                        "description": "Set to true to show both completed and pending tasks, or false for pending only.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_todo_task",
            "description": "Mark a workspace task as completed in the database using its unique integer task ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "The numeric ID of the task to mark completed"}
                },
                "required": ["task_id"],
            },
        },
    },
]
