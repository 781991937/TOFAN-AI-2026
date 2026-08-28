import json
import sqlite3
from pathlib import Path
from typing import Any


class Database:
    """Persistent database with PostgreSQL in production and SQLite locally."""

    def __init__(self, path_or_url: str | Path):
        value = str(path_or_url)
        self.database_url = value if value.startswith(("postgres://", "postgresql://")) else ""
        self.path = Path(value) if not self.database_url else None
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self):
        if self.database_url:
            import psycopg
            return psycopg.connect(self.database_url)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _execute(self, conn, sql: str, params=()):
        if self.database_url:
            sql = sql.replace("?", "%s")
        return conn.execute(sql, params)

    def _init_schema(self) -> None:
        if self.database_url:
            with self._connect() as conn:
                conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id BIGINT PRIMARY KEY, first_name TEXT,
                    question_count INTEGER NOT NULL DEFAULT 10,
                    difficulty TEXT NOT NULL DEFAULT 'medium',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS lessons (
                    id BIGSERIAL PRIMARY KEY,
                    telegram_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
                    file_name TEXT NOT NULL, file_type TEXT NOT NULL, file_path TEXT NOT NULL,
                    file_id TEXT, extracted_text TEXT NOT NULL, summary TEXT, concepts TEXT, key_points TEXT,
                    category TEXT NOT NULL DEFAULT '📂 مواد أخرى',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS quizzes (
                    id BIGSERIAL PRIMARY KEY,
                    lesson_id BIGINT NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
                    questions_json TEXT NOT NULL, question_count INTEGER NOT NULL DEFAULT 0,
                    difficulty TEXT NOT NULL DEFAULT 'medium',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS quiz_results (
                    id BIGSERIAL PRIMARY KEY,
                    telegram_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
                    quiz_id BIGINT NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
                    score INTEGER NOT NULL, total INTEGER NOT NULL, percentage DOUBLE PRECISION NOT NULL,
                    answers_json TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """)
                try:
                    conn.execute("ALTER TABLE lessons ADD COLUMN IF NOT EXISTS category TEXT NOT NULL DEFAULT '📂 مواد أخرى'")
                except Exception:
                    pass
                try:
                    conn.execute("ALTER TABLE lessons ADD COLUMN IF NOT EXISTS file_id TEXT")
                except Exception:
                    pass
            return

        with self._connect() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY, first_name TEXT,
                question_count INTEGER NOT NULL DEFAULT 10,
                difficulty TEXT NOT NULL DEFAULT 'medium', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER NOT NULL,
                file_name TEXT NOT NULL, file_type TEXT NOT NULL, file_path TEXT NOT NULL,
                file_id TEXT, extracted_text TEXT NOT NULL, summary TEXT, concepts TEXT, key_points TEXT,
                category TEXT NOT NULL DEFAULT '📂 مواد أخرى', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS quizzes (
                id INTEGER PRIMARY KEY AUTOINCREMENT, lesson_id INTEGER NOT NULL,
                questions_json TEXT NOT NULL, question_count INTEGER NOT NULL DEFAULT 0,
                difficulty TEXT NOT NULL DEFAULT 'medium', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lesson_id) REFERENCES lessons(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS quiz_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER NOT NULL,
                quiz_id INTEGER NOT NULL, score INTEGER NOT NULL, total INTEGER NOT NULL,
                percentage REAL NOT NULL, answers_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE,
                FOREIGN KEY (quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE
            );
            """)
            try:
                conn.execute("ALTER TABLE lessons ADD COLUMN category TEXT NOT NULL DEFAULT '📂 مواد أخرى'")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE lessons ADD COLUMN file_id TEXT")
            except sqlite3.OperationalError:
                pass

    def _rows(self, cur):
        if self.database_url:
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        return cur.fetchall()

    def _row(self, cur):
        rows = self._rows(cur)
        return rows[0] if rows else None

    def ensure_user(self, telegram_id: int, first_name: str = "") -> None:
        with self._connect() as conn:
            if self.database_url:
                self._execute(conn, "INSERT INTO users(telegram_id,first_name) VALUES(?,?) ON CONFLICT(telegram_id) DO UPDATE SET first_name=EXCLUDED.first_name", (telegram_id, first_name))
            else:
                self._execute(conn, "INSERT INTO users(telegram_id, first_name) VALUES (?, ?) ON CONFLICT(telegram_id) DO UPDATE SET first_name=excluded.first_name", (telegram_id, first_name))

    def get_user(self, telegram_id: int):
        with self._connect() as conn:
            return self._row(self._execute(conn, "SELECT * FROM users WHERE telegram_id=?", (telegram_id,)))

    def update_settings(self, telegram_id: int, question_count: int, difficulty: str) -> None:
        with self._connect() as conn:
            self._execute(conn, "UPDATE users SET question_count=?, difficulty=? WHERE telegram_id=?", (question_count, difficulty, telegram_id))

    def create_lesson(self, telegram_id: int, file_name: str, file_type: str, file_path: str, text: str, category: str = "📂 مواد أخرى", file_id: str = "") -> int:
        text = (text or "").replace("\x00", "")
        with self._connect() as conn:
            if self.database_url:
                cur = self._execute(conn, "INSERT INTO lessons(telegram_id,file_name,file_type,file_path,file_id,extracted_text,category) VALUES(?,?,?,?,?,?,?) RETURNING id", (telegram_id,file_name,file_type,file_path,file_id,text,category))
                return int(cur.fetchone()[0])
            cur = self._execute(conn, "INSERT INTO lessons(telegram_id,file_name,file_type,file_path,file_id,extracted_text,category) VALUES(?,?,?,?,?,?,?)", (telegram_id,file_name,file_type,file_path,file_id,text,category))
            return int(cur.lastrowid)

    def update_lesson_analysis(self, lesson_id: int, summary: str, concepts: str, key_points: str = "") -> None:
        with self._connect() as conn:
            self._execute(conn, "UPDATE lessons SET summary=?, concepts=?, key_points=? WHERE id=?", (summary, concepts, key_points, lesson_id))

    def update_lesson_text_and_name(self, lesson_id: int, file_name: str, extracted_text: str, category: str | None = None) -> None:
        """Rewrite a legacy lesson row after discovering multiple lessons in one upload."""
        extracted_text = (extracted_text or "").replace("\x00", "")
        with self._connect() as conn:
            if category is None:
                self._execute(conn, "UPDATE lessons SET file_name=?, extracted_text=? WHERE id=?", (file_name, extracted_text, lesson_id))
            else:
                self._execute(conn, "UPDATE lessons SET file_name=?, extracted_text=?, category=? WHERE id=?", (file_name, extracted_text, category, lesson_id))

    def update_lesson_category(self, lesson_id: int, category: str) -> None:
        with self._connect() as conn:
            self._execute(conn, "UPDATE lessons SET category=? WHERE id=?", (category, lesson_id))

    def get_lessons(self, telegram_id: int, limit: int = 100):
        with self._connect() as conn:
            return self._rows(self._execute(conn, "SELECT * FROM lessons WHERE telegram_id=? ORDER BY id ASC LIMIT ?", (telegram_id, limit)))

    def get_lessons_by_category(self, telegram_id: int, category: str):
        with self._connect() as conn:
            return self._rows(self._execute(conn, "SELECT * FROM lessons WHERE telegram_id=? AND category=? ORDER BY id ASC", (telegram_id, category)))

    def get_categories(self, telegram_id: int):
        with self._connect() as conn:
            return self._rows(self._execute(conn, "SELECT category, COUNT(*) AS lesson_count FROM lessons WHERE telegram_id=? GROUP BY category ORDER BY MIN(id) ASC", (telegram_id,)))

    def get_lesson(self, lesson_id: int, telegram_id: int | None = None):
        with self._connect() as conn:
            if telegram_id is None:
                return self._row(self._execute(conn, "SELECT * FROM lessons WHERE id=?", (lesson_id,)))
            return self._row(self._execute(conn, "SELECT * FROM lessons WHERE id=? AND telegram_id=?", (lesson_id, telegram_id)))

    def delete_lesson(self, lesson_id: int, telegram_id: int) -> bool:
        with self._connect() as conn:
            cur = self._execute(conn, "DELETE FROM lessons WHERE id=? AND telegram_id=?", (lesson_id, telegram_id))
            return cur.rowcount > 0

    def create_quiz(self, lesson_id: int, questions_json: str, question_count: int = 0, difficulty: str = "medium") -> int:
        with self._connect() as conn:
            if self.database_url:
                cur = self._execute(conn, "INSERT INTO quizzes(lesson_id,questions_json,question_count,difficulty) VALUES(?,?,?,?) RETURNING id", (lesson_id,questions_json,question_count,difficulty))
                return int(cur.fetchone()[0])
            cur = self._execute(conn, "INSERT INTO quizzes(lesson_id,questions_json,question_count,difficulty) VALUES(?,?,?,?)", (lesson_id,questions_json,question_count,difficulty))
            return int(cur.lastrowid)

    def get_cached_quiz(self, lesson_id: int, question_count: int, difficulty: str, group_only: bool = False):
        with self._connect() as conn:
            rows = self._rows(self._execute(conn, "SELECT * FROM quizzes WHERE lesson_id=? AND question_count=? AND difficulty=? ORDER BY id DESC LIMIT 20", (lesson_id,question_count,difficulty)))
            for row in rows:
                try:
                    questions = json.loads(row["questions_json"])
                except Exception:
                    continue
                if group_only and any(q.get("type") == "short" for q in questions):
                    continue
                return row
            return None

    def get_quiz(self, quiz_id: int):
        with self._connect() as conn:
            return self._row(self._execute(conn, "SELECT * FROM quizzes WHERE id=?", (quiz_id,)))

    def save_result(self, telegram_id: int, quiz_id: int, score: int, total: int, percentage: float, answers_json: str) -> int:
        with self._connect() as conn:
            if self.database_url:
                cur = self._execute(conn, "INSERT INTO quiz_results(telegram_id,quiz_id,score,total,percentage,answers_json) VALUES(?,?,?,?,?,?) RETURNING id", (telegram_id,quiz_id,score,total,percentage,answers_json))
                return int(cur.fetchone()[0])
            cur = self._execute(conn, "INSERT INTO quiz_results(telegram_id,quiz_id,score,total,percentage,answers_json) VALUES(?,?,?,?,?,?)", (telegram_id,quiz_id,score,total,percentage,answers_json))
            return int(cur.lastrowid)

    def get_quiz_leaderboard(self, quiz_id: int, limit: int = 10):
        with self._connect() as conn:
            return self._rows(self._execute(conn, "SELECT r.telegram_id,u.first_name,r.score,r.total,r.percentage FROM quiz_results r JOIN users u ON u.telegram_id=r.telegram_id WHERE r.quiz_id=? ORDER BY r.percentage DESC,r.score DESC,r.id ASC LIMIT ?", (quiz_id,limit)))

    def get_stats(self, telegram_id: int) -> dict[str, Any]:
        with self._connect() as conn:
            lessons = self._execute(conn, "SELECT COUNT(*) FROM lessons WHERE telegram_id=?", (telegram_id,)).fetchone()[0]
            quizzes = self._execute(conn, "SELECT COUNT(*) FROM quiz_results WHERE telegram_id=?", (telegram_id,)).fetchone()[0]
            avg = self._execute(conn, "SELECT AVG(percentage) FROM quiz_results WHERE telegram_id=?", (telegram_id,)).fetchone()[0]
            return {"lessons": lessons, "quizzes": quizzes, "average": round(avg or 0, 1)}
