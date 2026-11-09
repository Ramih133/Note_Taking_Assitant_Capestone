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
        """)
