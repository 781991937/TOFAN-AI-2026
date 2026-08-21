import sqlite3
from pathlib import Path
from typing import Any


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                first_name TEXT,
                question_count INTEGER NOT NULL DEFAULT 10,
                difficulty TEXT NOT NULL DEFAULT 'medium',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                file_name TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_path TEXT NOT NULL,
                extracted_text TEXT NOT NULL,
                summary TEXT,
                concepts TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS quizzes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lesson_id INTEGER NOT NULL,
                questions_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lesson_id) REFERENCES lessons(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS quiz_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                quiz_id INTEGER NOT NULL,
                score INTEGER NOT NULL,
                total INTEGER NOT NULL,
                percentage REAL NOT NULL,
                answers_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE,
                FOREIGN KEY (quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE
            );
            """)

    def ensure_user(self, telegram_id: int, first_name: str = "") -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO users(telegram_id, first_name) VALUES (?, ?) "
                "ON CONFLICT(telegram_id) DO UPDATE SET first_name=excluded.first_name",
                (telegram_id, first_name),
            )

    def get_user(self, telegram_id: int) -> sqlite3.Row | None:
        with self._connect() as conn:
            return conn.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,)).fetchone()

    def update_settings(self, telegram_id: int, question_count: int, difficulty: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE users SET question_count=?, difficulty=? WHERE telegram_id=?", (question_count, difficulty, telegram_id))

    def create_lesson(self, telegram_id: int, file_name: str, file_type: str, file_path: str, text: str) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO lessons(telegram_id,file_name,file_type,file_path,extracted_text) VALUES(?,?,?,?,?)",
                (telegram_id, file_name, file_type, file_path, text),
            )
            return int(cur.lastrowid)

    def update_lesson_analysis(self, lesson_id: int, summary: str, concepts: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE lessons SET summary=?, concepts=? WHERE id=?", (summary, concepts, lesson_id))

    def get_lessons(self, telegram_id: int, limit: int = 20) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute("SELECT * FROM lessons WHERE telegram_id=? ORDER BY id DESC LIMIT ?", (telegram_id, limit)).fetchall()

    def get_lesson(self, lesson_id: int, telegram_id: int | None = None) -> sqlite3.Row | None:
        with self._connect() as conn:
            if telegram_id is None:
                return conn.execute("SELECT * FROM lessons WHERE id=?", (lesson_id,)).fetchone()
            return conn.execute("SELECT * FROM lessons WHERE id=? AND telegram_id=?", (lesson_id, telegram_id)).fetchone()

    def create_quiz(self, lesson_id: int, questions_json: str) -> int:
        with self._connect() as conn:
            cur = conn.execute("INSERT INTO quizzes(lesson_id,questions_json) VALUES(?,?)", (lesson_id, questions_json))
            return int(cur.lastrowid)

    def get_quiz(self, quiz_id: int) -> sqlite3.Row | None:
        with self._connect() as conn:
            return conn.execute("SELECT * FROM quizzes WHERE id=?", (quiz_id,)).fetchone()

    def save_result(self, telegram_id: int, quiz_id: int, score: int, total: int, percentage: float, answers_json: str) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO quiz_results(telegram_id,quiz_id,score,total,percentage,answers_json) VALUES(?,?,?,?,?,?)",
                (telegram_id, quiz_id, score, total, percentage, answers_json),
            )
            return int(cur.lastrowid)

    def get_stats(self, telegram_id: int) -> dict[str, Any]:
        with self._connect() as conn:
            lessons = conn.execute("SELECT COUNT(*) FROM lessons WHERE telegram_id=?", (telegram_id,)).fetchone()[0]
            quizzes = conn.execute("SELECT COUNT(*) FROM quiz_results WHERE telegram_id=?", (telegram_id,)).fetchone()[0]
            avg = conn.execute("SELECT AVG(percentage) FROM quiz_results WHERE telegram_id=?", (telegram_id,)).fetchone()[0]
            return {"lessons": lessons, "quizzes": quizzes, "average": round(avg or 0, 1)}
