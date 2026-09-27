"""Local LLM reasoning engine with dynamic tool calling, zero-credit lock, and self-healing guardrails."""

import json
import logging
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    ollama = None  # type: ignore
    OLLAMA_AVAILABLE = False

from tools import AVAILABLE_TOOLS, TOOL_SCHEMAS
from db import TaskDatabase

logger = logging.getLogger(__name__)

# HARD ZERO-CREDIT LOCK: Pinned exclusively to local host
LOCAL_OLLAMA_HOST = "http://127.0.0.1:11434"

SYSTEM_PROMPT = (
    "You are Avantika, an intelligent, poised, and privacy-first local desktop companion running natively on Windows. "
    "Rooted in the scholarly and astronomical heritage of ancient Avanti, you assist with operating system automation, task management, "
    "research, and technical inquiries with clarity, precision, and a calm, dignified tone. "
    "Whenever a user asks for time, music, jokes, workspace tasks/todos, or factual information, YOU MUST use the provided tools. "
    "You can manage the user's workspace tasks using the provided tools. "
    "You can also launch applications, adjust system volume, and search the web using the provided tools. "
    "If a tool returns no data or fails, state: 'I could not find verified information on that.' "
    "Do NOT invent facts, tasks, or parameters."
)


class AgentEngine:
    """Intelligent local reasoning engine locked to zero-credit local Ollama instance."""

    def __init__(
        self,
        model_name: str = "llama3.2",
        status_notifier: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.model_name = model_name
        self.status_notifier = status_notifier
        self.ollama_online = True
        self._consecutive_tool_errors = 0
        self.db = TaskDatabase()

        # Enforce zero cloud credit by pinning Ollama client to localhost
        if OLLAMA_AVAILABLE:
            self.client = ollama.Client(host=LOCAL_OLLAMA_HOST)
        else:
            self.client = None
            self.ollama_online = False

        self.history: List[Dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        self._load_persisted_context()

    def _load_persisted_context(self) -> None:
        """Hydrate recent conversation context from SQLite to maintain memory across restarts."""
        try:
            recent = self.db.get_recent_messages(limit=10)
            for msg in recent:
                # We skip system messages to avoid polluting memory
                if msg["role"] in ("user", "assistant"):
                    self.history.append({"role": msg["role"], "content": msg["content"]})
        except Exception as e:
            logger.warning("Failed to hydrate persistent context: %s", e)

    def clear_history(self) -> None:
        """Reset conversation history to the initial system prompt only."""
        self.history = [{"role": "system", "content": SYSTEM_PROMPT}]
        self._consecutive_tool_errors = 0
        logger.info("AgentEngine conversation history cleared.")

    def _notify_status(self, status: str) -> None:
        if self.status_notifier:
            self.status_notifier(status)

    def _deterministic_fallback(self, query: str) -> str:
        """Pattern matching fallback when Ollama is unavailable or errors."""
        clean_cmd = query.strip().lower()

        # Task management fallback patterns
        if any(kw in clean_cmd for kw in ["add task", "create task", "add todo"]):
            task_title = (
                clean_cmd.replace("add task", "")
                .replace("create task", "")
                .replace("add todo", "")
                .strip()
            )
            return AVAILABLE_TOOLS["add_todo_task"](title=task_title)

        if any(kw in clean_cmd for kw in ["list task", "show task", "my task", "pending task", "what are my task", "get task", "view task"]):
            show_all = "all" in clean_cmd
            return AVAILABLE_TOOLS["list_todo_tasks"](show_all=show_all)

        if any(kw in clean_cmd for kw in ["complete task", "finish task", "done task"]):
            m = re.search(r"\d+", clean_cmd)
            if m:
                return AVAILABLE_TOOLS["complete_todo_task"](task_id=int(m.group(0)))
            return "Please specify the task ID number to complete (e.g., 'complete task 1')."

        # OS Control patterns
        if any(kw in clean_cmd for kw in ["open ", "launch "]):
            app = clean_cmd.replace("open ", "").replace("launch ", "").strip()
            return AVAILABLE_TOOLS["launch_application"](app_name=app)
            
        if "volume to" in clean_cmd or "volume" in clean_cmd:
            m = re.search(r"\d+", clean_cmd)
            if m:
                return AVAILABLE_TOOLS["set_system_volume"](level=int(m.group(0)))
            elif "mute" in clean_cmd:
                return AVAILABLE_TOOLS["set_system_volume"](level=0)
            elif "max" in clean_cmd or "full" in clean_cmd:
                return AVAILABLE_TOOLS["set_system_volume"](level=100)

        if "mute" in clean_cmd and "volume" not in clean_cmd:
            return AVAILABLE_TOOLS["set_system_volume"](level=0)

        if any(kw in clean_cmd for kw in ["search for ", "search ", "google "]):
            query = clean_cmd.replace("search for ", "").replace("search ", "").replace("google ", "").strip()
            return AVAILABLE_TOOLS["search_web"](query=query)

        # General intent patterns
        if "play" in clean_cmd:
            song = clean_cmd.replace("play", "").strip()
            return AVAILABLE_TOOLS["play_music"](song)
        if "time" in clean_cmd:
            return AVAILABLE_TOOLS["get_current_time"]()
        if "who is" in clean_cmd or "who the heck is" in clean_cmd:
            subject = (
                clean_cmd.replace("who the heck is", "")
                .replace("who is", "")
                .strip()
            )
            return AVAILABLE_TOOLS["search_wikipedia"](subject)
        if "date" in clean_cmd:
            return AVAILABLE_TOOLS["get_canned_response"]("date")
        if "are you single" in clean_cmd or "single" in clean_cmd:
            return AVAILABLE_TOOLS["get_canned_response"]("are you single")
        if "joke" in clean_cmd:
            return AVAILABLE_TOOLS["tell_joke"]()

        return "I could not find verified information on that."

    def _execute_tool_call(self, tool_call: Any) -> Tuple[str, str]:
        """Execute a parsed tool call with a cap on consecutive failures."""
        if self._consecutive_tool_errors >= 2:
            logger.warning("Consecutive tool errors reached limit of 2. Returning safe fallback.")
            return "", "I could not find verified information on that."

        func = getattr(tool_call, "function", None)
        if func:
            name = getattr(func, "name", "")
            args = getattr(func, "arguments", {})
        elif isinstance(tool_call, dict):
            func_dict = tool_call.get("function", {})
            name = func_dict.get("name", "")
            args = func_dict.get("arguments", {})
        else:
            self._consecutive_tool_errors += 1
            return "", "I could not find verified information on that."

        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                args = {}

        if name in AVAILABLE_TOOLS:
            try:
                result = AVAILABLE_TOOLS[name](**args)
                if result == "I could not find verified information on that.":
                    self._consecutive_tool_errors += 1
                else:
                    self._consecutive_tool_errors = 0
                return name, str(result)
            except Exception as e:
                self._consecutive_tool_errors += 1
                logger.error("Error executing tool %s (attempt error #%d): %s", name, self._consecutive_tool_errors, e)
                return name, "I could not find verified information on that."

        self._consecutive_tool_errors += 1
        return name, "I could not find verified information on that."

    def process_query(self, query: str) -> str:
        """Process input via zero-credit local LLM tool calling with self-healing fallback."""
        clean_query = query.strip()
        if not clean_query:
            return "Please provide a valid command."

        # 1. Deterministic first-pass bypass (0ms latency for known commands)
        det_res = self._deterministic_fallback(clean_query)
        if det_res != "I could not find verified information on that.":
            # Fast-path resolution
            self.history.append({"role": "user", "content": clean_query})
            self._notify_status("STREAM_START")
            for word in det_res.split():
                self._notify_status(f"STREAM_CHUNK:{word} ")
            self._notify_status("STREAM_END")
            self.history.append({"role": "assistant", "content": det_res})
            return det_res

        if not OLLAMA_AVAILABLE or not self.client:
            if self.ollama_online:
                self.ollama_online = False
                self._notify_status("Deterministic Mode (Ollama Offline)")
            return det_res

        # 2. Cap context history to last 6 turns
        if len(self.history) > 7:
            self.history = [self.history[0]] + self.history[-6:]

        self.history.append({"role": "user", "content": clean_query})

        options = {
            "num_ctx": 2048,
            "keep_alive": "30m",
            "temperature": 0.3,
            "num_predict": 256
        }

        try:
            response = self.client.chat(
                model=self.model_name,
                messages=self.history,
                tools=TOOL_SCHEMAS,
                options=options,
                stream=True
            )

            if not self.ollama_online:
                self.ollama_online = True
                self._notify_status("Idle (Local LLM Active)")

            tool_calls = []
            final_content = ""
            has_started_stream = False
            first_message = None

            for chunk in response:
                msg = chunk.message
                if first_message is None:
                    first_message = msg

                if getattr(msg, "tool_calls", None):
                    tool_calls.extend(msg.tool_calls)
                
                content = getattr(msg, "content", "")
                if content:
                    if not has_started_stream and not tool_calls:
                        self._notify_status("STREAM_START")
                        has_started_stream = True
                    final_content += content
                    if has_started_stream:
                        self._notify_status(f"STREAM_CHUNK:{content}")

            if tool_calls:
                self.history.append(first_message)
                tool_results: List[str] = []

                for tc in tool_calls:
                    tool_name, tool_result = self._execute_tool_call(tc)
                    tool_results.append(tool_result)
                    self.history.append({
                        "role": "tool",
                        "content": tool_result,
                        "name": tool_name,
                    })

                follow_up = self.client.chat(
                    model=self.model_name,
                    messages=self.history,
                    options=options,
                    stream=True
                )
                
                if not has_started_stream:
                    self._notify_status("STREAM_START")
                    has_started_stream = True

                final_content = ""
                for chunk in follow_up:
                    content = getattr(chunk.message, "content", "")
                    if content:
                        final_content += content
                        self._notify_status(f"STREAM_CHUNK:{content}")

                if not final_content and tool_results:
                    final_content = " ".join(tool_results)
                    self._notify_status(f"STREAM_CHUNK:{final_content}")

            if has_started_stream:
                self._notify_status("STREAM_END")

            self.history.append({"role": "assistant", "content": final_content})
            return final_content

        except Exception as e:
            logger.warning("Local Ollama connection failed (%s). Switching to deterministic mode.", e)
            if self.ollama_online:
                self.ollama_online = False
                self._notify_status("Deterministic Mode (Ollama Offline)")

            if self.history and self.history[-1].get("role") == "user":
                self.history.pop()

            return self._deterministic_fallback(clean_query)
