import os
import sqlite3
from pathlib import Path
DB = Path(os.environ.get('NOTES_DB_PATH', Path(__file__).resolve().parent / 'assistant.db'))

class ClosingConnection(sqlite3.Connection):

    def __exit__(self, error_type, error_value, traceback):
        try:
            return super().__exit__(error_type, error_value, traceback)
        finally:
            self.close()

# Connect to SQLite
def connect():
    db = sqlite3.connect(DB, factory=ClosingConnection)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db

# Create database tables
def init_db():
    with connect() as connection:
        connection.executescript("\n        CREATE TABLE IF NOT EXISTS users (\n          id INTEGER PRIMARY KEY, name TEXT NOT NULL,\n          email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL);\n        CREATE TABLE IF NOT EXISTS courses (\n          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL,\n          name TEXT NOT NULL, code TEXT DEFAULT '',\n          FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);\n        CREATE TABLE IF NOT EXISTS lectures (\n          id INTEGER PRIMARY KEY, course_id INTEGER NOT NULL,\n          title TEXT NOT NULL,\n          FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE);\n        CREATE TABLE IF NOT EXISTS materials (\n          id INTEGER PRIMARY KEY, lecture_id INTEGER NOT NULL,\n          kind TEXT NOT NULL, original_name TEXT NOT NULL,\n          stored_name TEXT NOT NULL, extracted_text TEXT DEFAULT '',\n          FOREIGN KEY(lecture_id) REFERENCES lectures(id) ON DELETE CASCADE);\n        CREATE TABLE IF NOT EXISTS lecture_notes (\n          lecture_id INTEGER PRIMARY KEY, content TEXT NOT NULL DEFAULT '',\n          updated_at TEXT DEFAULT CURRENT_TIMESTAMP,\n          FOREIGN KEY(lecture_id) REFERENCES lectures(id) ON DELETE CASCADE);\n        CREATE TABLE IF NOT EXISTS study_cards (\n          id INTEGER PRIMARY KEY, course_id INTEGER NOT NULL,\n          question TEXT NOT NULL, answer TEXT NOT NULL,\n          FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE);\n        CREATE TABLE IF NOT EXISTS study_guides (\n          course_id INTEGER PRIMARY KEY, content TEXT NOT NULL DEFAULT '',\n          FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE);\n        ")

def init_studley_tables():
    with connect() as db:
        db.executescript("\n        CREATE TABLE IF NOT EXISTS notebook_notes (\n          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, course_id INTEGER NOT NULL,\n          title TEXT NOT NULL, body TEXT NOT NULL DEFAULT '',\n          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,\n          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,\n          FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,\n          FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE);\n        CREATE INDEX IF NOT EXISTS idx_notebook_owner_course ON notebook_notes(user_id,course_id);\n        CREATE TABLE IF NOT EXISTS study_attempts (\n          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, course_id INTEGER NOT NULL,\n          card_id INTEGER NOT NULL, correct INTEGER NOT NULL,\n          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,\n          FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,\n          FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE,\n          FOREIGN KEY(card_id) REFERENCES study_cards(id) ON DELETE CASCADE);\n        ")
