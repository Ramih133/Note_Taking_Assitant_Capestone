import os
import sqlite3
from pathlib import Path

DB = Path(os.environ.get("NOTES_DB_PATH", Path(__file__).resolve().parent / "data.db"))

# Close database connections safely
class ClosingConnection(sqlite3.Connection):

    def __exit__(self, error_type, error_value, traceback):
        try:
            return super().__exit__(error_type, error_value, traceback)
        finally:
            self.close()

# Connect to saved data
def connect():

    connection = sqlite3.connect(DB, factory=ClosingConnection)
    connection.row_factory = sqlite3.Row

    connection.execute("PRAGMA foreign_keys=ON")
    return connection

# Create database tables
def init_db():

    with connect() as connection:
        connection.executescript("""
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY, name TEXT NOT NULL,
          email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS courses (
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL,
          name TEXT NOT NULL, code TEXT DEFAULT '',
          FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS lectures (
          id INTEGER PRIMARY KEY, course_id INTEGER NOT NULL,
          title TEXT NOT NULL,
          FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS materials (
          id INTEGER PRIMARY KEY, lecture_id INTEGER NOT NULL,
          kind TEXT NOT NULL, original_name TEXT NOT NULL,
          stored_name TEXT NOT NULL, extracted_text TEXT DEFAULT '',
          FOREIGN KEY(lecture_id) REFERENCES lectures(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS lecture_notes (
          lecture_id INTEGER PRIMARY KEY, content TEXT NOT NULL DEFAULT '',
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(lecture_id) REFERENCES lectures(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS study_cards (
          id INTEGER PRIMARY KEY, course_id INTEGER NOT NULL,
          question TEXT NOT NULL, answer TEXT NOT NULL,
          FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS study_guides (
          course_id INTEGER PRIMARY KEY, content TEXT NOT NULL DEFAULT '',
          FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS lecture_analyses (
          lecture_id INTEGER PRIMARY KEY, missing TEXT NOT NULL DEFAULT '[]',
          created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(lecture_id) REFERENCES lectures(id) ON DELETE CASCADE);
        """)
        add_missing_columns(connection, "study_cards", {
            "lecture_id": "INTEGER REFERENCES lectures(id) ON DELETE SET NULL",
            "source": "TEXT NOT NULL DEFAULT 'manual'",
            "times_seen": "INTEGER NOT NULL DEFAULT 0",
            "times_correct": "INTEGER NOT NULL DEFAULT 0",
            # AI-written questions store their own options; rule-based cards leave these empty
            "options": "TEXT NOT NULL DEFAULT ''",
            "correct": "INTEGER",
            # extra detail on how it was made: the AI model name, or "fallback" if the AI's output was unusable
            "method": "TEXT NOT NULL DEFAULT ''",
        })

# CREATE TABLE IF NOT EXISTS won't add new columns to a data.db that already exists,
# so add any that are missing
def add_missing_columns(connection, table, columns):
    existing = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
    for name, definition in columns.items():
        if name not in existing:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


# Studio workspace tables (partner)
def init_studley_tables():
    with connect() as db:
        db.executescript("\n        CREATE TABLE IF NOT EXISTS notebook_notes (\n          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, course_id INTEGER NOT NULL,\n          title TEXT NOT NULL, body TEXT NOT NULL DEFAULT '',\n          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,\n          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,\n          FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,\n          FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE);\n        CREATE INDEX IF NOT EXISTS idx_notebook_owner_course ON notebook_notes(user_id,course_id);\n        CREATE TABLE IF NOT EXISTS study_attempts (\n          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, course_id INTEGER NOT NULL,\n          card_id INTEGER NOT NULL, correct INTEGER NOT NULL,\n          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,\n          FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,\n          FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE,\n          FOREIGN KEY(card_id) REFERENCES study_cards(id) ON DELETE CASCADE);\n        ")
        # live lecture transcript saved with each notebook note (JSON list of {stamp, text})
        add_missing_columns(db, "notebook_notes", {"transcript": "TEXT NOT NULL DEFAULT ''"})