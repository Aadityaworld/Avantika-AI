"""SQLite-backed Task and Workflow Database Manager."""

from contextlib import contextmanager
import os
import sqlite3
from typing import Any, Dict, Generator, List, Optional


class TaskDatabase:
    """Thread-safe SQLite database helper for managing workspace tasks."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        if db_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.db_path = os.path.join(base_dir, "workspace_tasks.db")
        else:
            self.db_path = db_path

        self._init_db()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Create, yield, commit, and cleanly close a SQLite connection."""
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Create table schema if it does not already exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    category TEXT DEFAULT 'General',
                    is_done INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """Retrieve all tasks sorted by pending status then newest first."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, title, category, is_done, created_at
                FROM tasks
                ORDER BY is_done ASC, id DESC
                """
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def add_task(self, title: str, category: str = "General") -> int:
        """Add a new task record and return the inserted task ID."""
        clean_title = title.strip()
        if not clean_title:
            return -1

        clean_cat = category.strip() if category else "General"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO tasks (title, category, is_done)
                VALUES (?, ?, 0)
                """,
                (clean_title, clean_cat),
            )
            return cursor.lastrowid or -1

    def toggle_task(self, task_id: int, current_status: Optional[int] = None) -> None:
        """Toggle task completion state."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if current_status is None:
                cursor.execute(
                    """
                    UPDATE tasks
                    SET is_done = CASE WHEN is_done = 1 THEN 0 ELSE 1 END
                    WHERE id = ?
                    """,
                    (task_id,),
                )
            else:
                new_status = 0 if current_status == 1 else 1
                cursor.execute(
                    """
                    UPDATE tasks
                    SET is_done = ?
                    WHERE id = ?
                    """,
                    (new_status, task_id),
                )

    def delete_task(self, task_id: int) -> None:
        """Delete a task by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM tasks
                WHERE id = ?
                """,
                (task_id,),
            )

    def add_message(self, role: str, content: str) -> int:
        """Add a new chat message to the history."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO chat_messages (role, content)
                VALUES (?, ?)
                """,
                (role.strip(), content.strip()),
            )
            return cursor.lastrowid or -1

    def get_recent_messages(self, limit: int = 50) -> List[Dict[str, str]]:
        """Retrieve recent chat messages in chronological order."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Fetch latest messages descending, then reverse in Python to get chronological order
            cursor.execute(
                """
                SELECT role, content
                FROM chat_messages
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            messages = [{"role": row["role"], "content": row["content"]} for row in rows]
            messages.reverse()
            return messages

    def clear_chat_history(self) -> None:
        """Clear all messages from the chat history."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM chat_messages")

