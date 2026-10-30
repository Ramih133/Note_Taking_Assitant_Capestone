import os
import re
import secrets
import sqlite3
import uuid
from pathlib import Path
import zipfile
from mutagen import File as AudioFile
from fastapi import FastAPI, Request, HTTPException
from starlette.datastructures import UploadFile
from fastapi.responses import RedirectResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from password_utils import generate_password_hash, check_password_hash

from database import connect, init_db

# Project folders and study tools
project_folder = Path(__file__).resolve().parent
upload_folder = project_folder / "uploads"
upload_folder.mkdir(exist_ok=True)
study_tools = [
    ("record", "Lecture Recording", "Record in your browser or upload lecture audio", "available"),
    ("catchup", "Lecture Catch Up", "Review what you missed during class", "planned"),
    ("gaps", "Missing Notes", "Compare your notes with slides and audio", "planned"),
    ("guides", "Study Guides", "Write and save your own study guides", "available"),
    ("quizzes", "Practice Quizzes", "Create flashcards and test your recall", "available"),
    ("exams", "Exam Preparation", "Use saved cards and study guides to prepare", "available"),
    ("coding", "Coding Support", "Keep programming notes with your lectures", "planned"),
    ("assignments", "Assignment Review", "Compare assignments with course topics", "planned"),
    
]
# Allowed uploads and file limits
allowed_file_types = {
    "recording": {".mp3", ".wav", ".m4a"},
    "slides": {".pdf"},
    "lecture": {".pdf", ".txt", ".docx"},
    "notes": {".pdf", ".txt", ".docx", ".jpg", ".png"},
}
max_recording_size = 500 * 1024 * 1024
max_document_size = 25 * 1024 * 1024
max_recording_seconds = 3 * 60 * 60
# Start the website
app = FastAPI(title="Note Taking Assistant")
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("SECRET_KEY", "local-development-only-change-me"),
                   same_site="lax", https_only=os.environ.get("SECURE_COOKIES") == "1", max_age=8 * 3600)
app.mount("/static", StaticFiles(directory=str(project_folder / "static")), name="static")
templates = Jinja2Templates(directory=str(project_folder / "templates"))
init_db()

# Browser  settings
@app.middleware("http")
async def prevent_private_page_cache(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith(("/login", "/join", "/dashboard", "/my-courses", "/courses", "/library", "/lectures", "/materials", "/logout", "/study")):
        response.headers["Cache-Control"] = "no-store"
    return response

# Form security and page helpers
def token(request: Request):
    if "csrf" not in request.session:
        request.session["csrf"] = secrets.token_urlsafe(24)
    return request.session["csrf"]

def show_message(request: Request, message: str):
    request.session.setdefault("messages", []).append(message)

def show_page(request: Request, page: str, **values):
    csrf = token(request)
    messages = request.session.pop("messages", [])
    return templates.TemplateResponse(request, "index1.html", {
        "page": page, "username": request.session.get("name"), "tools": study_tools,
        "csrf": csrf, "get_flashed_messages": lambda: messages, **values
    })

def redirect(request: Request, name: str, **params):
    return RedirectResponse(request.url_for(name, **params), status_code=303)

async def get_form_data(request: Request):
    form = await request.form()
    supplied = str(form.get("csrf", ""))
    expected = token(request)
    if not secrets.compare_digest(supplied, expected):
        raise HTTPException(400, "Invalid CSRF token")
    return form

# Sign in checks and user access
def get_logged_in_user(request: Request):
    uid = request.session.get("uid")
    if not uid:
        return None
    with connect() as db:
        row = db.execute("SELECT id FROM users WHERE id=?", (uid,)).fetchone()
    if not row:
        request.session.clear()
    return row

def check_login(request: Request):
    if not get_logged_in_user(request):
        return redirect(request, "login")
    return None

def get_user_course(request: Request, cid: int):
    with connect() as db:
        row = db.execute("SELECT * FROM courses WHERE id=? AND user_id=?", (cid, request.session["uid"])).fetchone()
    if row is None:
        raise HTTPException(404)
    return row

def get_user_lecture(request: Request, lid: int):
    with connect() as db:
        row = db.execute("""SELECT l.* FROM lectures l JOIN courses c ON c.id=l.course_id
                            WHERE l.id=? AND c.user_id=?""", (lid, request.session["uid"])).fetchone()
    if row is None:
        raise HTTPException(404)
    return row

# Home page
@app.get("/", name="home")
def home(request: Request):
    return show_page(request, "home")

# Sign up page
@app.get("/join", name="join")
def join_page(request: Request):
    return show_page(request, "signup")

@app.post("/join")
async def join(request: Request):
    form = await get_form_data(request)
    name = str(form.get("name", "")).strip()[:100]
    email = str(form.get("email", "")).strip().lower()
    password = str(form.get("password", ""))
    confirmation = str(form.get("confirm_password", password))
    if confirmation != password:
        show_message(request, "Passwords do not match. Please try again.")
        return redirect(request, "join")
    if not name or len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or len(password) < 8:
        show_message(request, "Enter a name, valid email, and password of at least 8 characters.")
        return redirect(request, "join")
    try:
        with connect() as db:
            uid = db.execute("INSERT INTO users(name,email,password_hash) VALUES(?,?,?)",
                             (name, email, generate_password_hash(password))).lastrowid
    except sqlite3.IntegrityError:
        show_message(request, "An account with this email already exists. Please log in.")
        return redirect(request, "join")
    request.session.clear()
    request.session["uid"] = uid
    request.session["name"] = name
    request.session["csrf"] = secrets.token_urlsafe(24)
    return redirect(request, "dashboard")

# Sign in page
@app.get("/login", name="login")
def login_page(request: Request):
    return show_page(request, "login")

@app.post("/login")
async def login(request: Request):
    form = await get_form_data(request)
    email = str(form.get("email", "")).strip().lower()
    password = str(form.get("password", ""))

    with connect() as db:
        user = db.execute("SELECT * FROM users WHERE lower(email)=?", (email,)).fetchone()

    valid_login = user is not None and check_password_hash(user["password_hash"], password)
    if not valid_login:
        request.session.clear()
        show_message(request, "Invalid email or password. Please try again.")
        return redirect(request, "login")

    request.session.clear()
    request.session["uid"] = user["id"]
    request.session["name"] = user["name"]
    request.session["csrf"] = secrets.token_urlsafe(24)
    return redirect(request, "dashboard")

# Sign out
@app.post("/logout", name="logout")
async def logout(request: Request):
    await get_form_data(request)
    request.session.clear()
    return redirect(request, "login")

# Dashboard
@app.get("/dashboard", name="dashboard")
def dashboard(request: Request):

    login_check = check_login(request)
    if login_check:
        return login_check
    with connect() as db:
        courses = db.execute("""SELECT c.*, COUNT(l.id) lecture_count FROM courses c
            LEFT JOIN lectures l ON l.course_id=c.id WHERE c.user_id=?
            GROUP BY c.id ORDER BY c.id DESC""", (request.session["uid"],)).fetchall()
    with connect() as db:
        recent_files = db.execute("""SELECT m.id, m.original_name, m.kind, l.title AS lecture_title,
            c.id AS course_id, c.name AS course_name FROM materials m
            JOIN lectures l ON l.id=m.lecture_id JOIN courses c ON c.id=l.course_id
            WHERE c.user_id=? ORDER BY m.id DESC LIMIT 8""", (request.session["uid"],)).fetchall()
    with connect() as db:
        counts = db.execute("""SELECT COUNT(DISTINCT l.id) AS lectures, COUNT(DISTINCT m.id) AS files
            FROM courses c LEFT JOIN lectures l ON l.course_id=c.id
            LEFT JOIN materials m ON m.lecture_id=l.id WHERE c.user_id=?""",
            (request.session["uid"],)).fetchone()
    return show_page(request, "dashboard", courses=courses, recent_files=recent_files,
                     total_lectures=counts["lectures"], total_files=counts["files"])

# My Courses page
@app.get("/my-courses", name="my_courses")
def my_courses(request: Request):
    login_check = check_login(request)
    if login_check:
        return login_check
    with connect() as db:
        courses = db.execute("""SELECT c.id, c.name, c.code,
            COUNT(DISTINCT l.id) AS lecture_count,
            COUNT(DISTINCT m.id) AS file_count
            FROM courses c
            LEFT JOIN lectures l ON l.course_id=c.id
            LEFT JOIN materials m ON m.lecture_id=l.id
            WHERE c.user_id=? GROUP BY c.id ORDER BY c.name""",
            (request.session["uid"],)).fetchall()
        files = db.execute("""SELECT m.id, m.original_name, m.kind,
            l.title AS lecture_title, c.id AS course_id
            FROM materials m JOIN lectures l ON l.id=m.lecture_id
            JOIN courses c ON c.id=l.course_id
            WHERE c.user_id=? ORDER BY m.id DESC""",
            (request.session["uid"],)).fetchall()
    recent_by_course = {}
    for file in files:
        recent_by_course.setdefault(file["course_id"], [])
        if len(recent_by_course[file["course_id"]]) < 3:
            recent_by_course[file["course_id"]].append(file)
    return show_page(request, "my_courses", courses=courses, recent_by_course=recent_by_course)

# Saved materials page
@app.get("/library", name="library")
def library(request: Request, cid: int = 0):
    login_check = check_login(request)
    if login_check:
        return login_check
    with connect() as db:
        courses = db.execute("SELECT id,name,code FROM courses WHERE user_id=? ORDER BY name",
                             (request.session["uid"],)).fetchall()
        selected = cid if any(course["id"] == cid for course in courses) else 0
        files = db.execute("""SELECT m.id, m.original_name, m.kind, l.title AS lecture_title,
            c.id AS course_id, c.name AS course_name FROM materials m
            JOIN lectures l ON l.id=m.lecture_id JOIN courses c ON c.id=l.course_id
            WHERE c.user_id=? AND (?=0 OR c.id=?) ORDER BY c.name, m.id DESC""",
            (request.session["uid"], selected, selected)).fetchall()
    return show_page(request, "library", courses=courses, files=files, selected_course=selected)

# Add a course
@app.post("/courses", name="add_course")
async def add_course(request: Request):

    login_check = check_login(request)
    if login_check:
        return login_check

    form = await get_form_data(request)
    course_name = str(form.get("name", "")).strip()[:100]
    course_code = str(form.get("code", "")).strip()[:30]
    if course_name:

        with connect() as db:
            db.execute(
                "INSERT INTO courses (user_id, name, code) VALUES (?, ?, ?)",
                (request.session["uid"], course_name, course_code)
            )
    return redirect(request, "my_courses")

# Course page
@app.get("/courses/{cid}", name="course")
def course(request: Request, cid: int):

    login_check = check_login(request)
    if login_check:
        return login_check
    c = get_user_course(request, cid)
    with connect() as db:
        lectures = db.execute("SELECT * FROM lectures WHERE course_id=? ORDER BY id DESC", (cid,)).fetchall()
    with connect() as db:
        course_files = db.execute("""SELECT m.id, m.original_name, m.kind, l.title AS lecture_title
            FROM materials m JOIN lectures l ON l.id=m.lecture_id
            WHERE l.course_id=? ORDER BY m.id DESC""", (cid,)).fetchall()
        guide = db.execute("SELECT content FROM study_guides WHERE course_id=?", (cid,)).fetchone()
        cards = db.execute("SELECT id,question,answer FROM study_cards WHERE course_id=? ORDER BY id DESC", (cid,)).fetchall()
    return show_page(request, "course", course=c, lectures=lectures, course_files=course_files,
                     guide=guide["content"] if guide else "", cards=cards)

# Edit a course
@app.post("/courses/{cid}/edit", name="edit_course")
async def edit_course(request: Request, cid: int):

    login_check = check_login(request)
    if login_check:
        return login_check
    get_user_course(request, cid)

    form = await get_form_data(request)
    course_name = str(form.get("name", "")).strip()[:100]
    course_code = str(form.get("code", "")).strip()[:30]
    if course_name:
        with connect() as db:
            db.execute(
                "UPDATE courses SET name = ?, code = ? WHERE id = ?",
                (course_name, course_code, cid)
            )
    return redirect(request, "course", cid=cid)

# Delete a course
@app.post("/courses/{cid}/delete", name="delete_course")
async def delete_course(request: Request, cid: int):
    login_check = check_login(request)
    if login_check:
        return login_check
    get_user_course(request, cid)
    await get_form_data(request)
    with connect() as db:
        paths = db.execute("""SELECT m.stored_name FROM materials m JOIN lectures l
                              ON l.id=m.lecture_id WHERE l.course_id=?""", (cid,)).fetchall()
        db.execute("DELETE FROM courses WHERE id=?", (cid,))

    for row in paths:
        saved_file = upload_folder / row["stored_name"]
        saved_file.unlink(missing_ok=True)
    return redirect(request, "dashboard")

# Add a lecture
@app.post("/courses/{cid}/lectures", name="add_lecture")
async def add_lecture(request: Request, cid: int):
    login_check = check_login(request)
    if login_check:
        return login_check
    get_user_course(request, cid)

    form = await get_form_data(request)
    title = str(form.get("title", "")).strip()[:150]
    if title:
        with connect() as db:
            db.execute("INSERT INTO lectures(course_id,title) VALUES(?,?)", (cid, title))
    return redirect(request, "course", cid=cid)

# Upload lecture files
@app.post("/lectures/{lid}/upload", name="upload")
async def upload(request: Request, lid: int):
    login_check = check_login(request)
    if login_check:
        return login_check
    get_user_lecture(request, lid)
    form = await get_form_data(request)
    kind = str(form.get("kind", "lecture"))
    if kind not in allowed_file_types:
        raise HTTPException(400)
    file = form.get("file")
    if not isinstance(file, UploadFile) or not file.filename:
        show_message(request, "Please select a file before uploading.")
        return redirect(request, "lecture", lid=lid)
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_file_types[kind]:
        show_message(request, "Unsupported file type for this material category.")
        return redirect(request, "lecture", lid=lid)
    stored = uuid.uuid4().hex + ext
    path = upload_folder / stored
    total = 0
    try:
        with path.open("wb") as output:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > (max_recording_size if kind == "recording" else max_document_size):
                    raise ValueError("File exceeds the size limit")
                output.write(chunk)
    except ValueError:
        path.unlink(missing_ok=True)
        show_message(request, "Recording limit: 500 MB. Other files: 25 MB.")
        return redirect(request, "lecture", lid=lid)

    with path.open("rb") as source:
        header = source.read(16)
    valid = {
        ".pdf": header.startswith(b"%PDF-"),
        ".png": header.startswith(b"\x89PNG\r\n\x1a\n"),
        ".jpg": header.startswith(b"\xff\xd8\xff"),
        ".wav": header.startswith(b"RIFF") and header[8:12] == b"WAVE",
        ".mp3": header.startswith(b"ID3") or (len(header) >= 2 and header[0] == 255 and header[1] & 224 == 224),
        ".m4a": len(header) >= 8 and header[4:8] == b"ftyp",
        ".txt": True,
    }.get(ext)
    if ext == ".docx":
        try:
            with zipfile.ZipFile(path) as archive:
                valid = "word/document.xml" in archive.namelist()
        except (zipfile.BadZipFile, OSError):
            valid = False
    if not valid or total == 0:
        path.unlink(missing_ok=True)
        show_message(request, "Invalid or empty file. Check the selected format.")
        return redirect(request, "lecture", lid=lid)
    if kind == "recording":
        try:
            audio = AudioFile(str(path))
            duration = float(audio.info.length)
            if not 0 < duration <= max_recording_seconds:
                raise ValueError("Recording must be 3 hours or shorter.")
        except Exception:
            path.unlink(missing_ok=True)
            show_message(request, "Invalid recording or longer than 3 hours.")
            return redirect(request, "lecture", lid=lid)
    with connect() as db:

        db.execute(
            """INSERT INTO materials (lecture_id, kind, original_name, stored_name)
               VALUES (?, ?, ?, ?)""",
            (lid, kind, Path(file.filename).name.replace("/", "_").replace("\\", "_")[:200], stored)
        )
    return redirect(request, "lecture", lid=lid)

# Lecture page
@app.get("/lectures/{lid}", name="lecture")
def lecture(request: Request, lid: int):
    login_check = check_login(request)
    if login_check:
        return login_check
    lec = get_user_lecture(request, lid)
    with connect() as db:
        materials = db.execute("SELECT * FROM materials WHERE lecture_id=? ORDER BY id DESC", (lid,)).fetchall()
        saved_notes = db.execute("SELECT content FROM lecture_notes WHERE lecture_id=?", (lid,)).fetchone()
    return show_page(request, "lecture", lecture=lec, materials=materials,
                     saved_notes=saved_notes["content"] if saved_notes else "")

# Download saved files
@app.get("/materials/{mid}/download", name="download")
def download(request: Request, mid: int):
    login_check = check_login(request)
    if login_check:
        return login_check
    with connect() as db:
        m = db.execute("""SELECT m.* FROM materials m JOIN lectures l ON l.id=m.lecture_id
            JOIN courses c ON c.id=l.course_id WHERE m.id=? AND c.user_id=?""",
            (mid, request.session["uid"])).fetchone()
    if not m:
        raise HTTPException(404)
    return FileResponse(upload_folder / m["stored_name"], filename=m["original_name"])

# Preview saved files
@app.get("/materials/{mid}/view", name="view_material")
def view_material(request: Request, mid: int):
    login_check = check_login(request)
    if login_check:
        return login_check
    with connect() as db:
        m = db.execute("""SELECT m.* FROM materials m JOIN lectures l ON l.id=m.lecture_id
            JOIN courses c ON c.id=l.course_id WHERE m.id=? AND c.user_id=?""",
            (mid, request.session["uid"])).fetchone()
    if not m:
        raise HTTPException(404)
    file_path = upload_folder / m["stored_name"]
    if not file_path.is_file():
        raise HTTPException(404, "File not found")
    ext = Path(m["original_name"]).suffix.lower()
    preview_types = {".pdf": "application/pdf", ".txt": "text/plain; charset=utf-8",
        ".png": "image/png", ".jpg": "image/jpeg", ".mp3": "audio/mpeg",
        ".wav": "audio/wav", ".m4a": "audio/mp4"}
    if ext not in preview_types:
        return redirect(request, "download", mid=mid)
    return FileResponse(file_path, media_type=preview_types[ext],
        headers={"Content-Disposition": "inline", "X-Content-Type-Options": "nosniff"})

# Study Tools page
@app.get("/features", name="features")
def features(request: Request):
    login_check = check_login(request)
    if login_check:
        return login_check
    with connect() as db:
        courses = db.execute("SELECT id, name, code FROM courses WHERE user_id=? ORDER BY name",
            (request.session["uid"],)).fetchall()
    return show_page(request, "features", courses=courses)

# Individual study tool
@app.get("/tools/{tool}", name="tool_page")
def tool_page(request: Request, tool: str, cid: int = 0):
    login_check = check_login(request)
    if login_check:
        return login_check
    selected = next((item for item in study_tools if item[0] == tool), None)
    if selected is None:
        raise HTTPException(404)
    with connect() as db:
        courses = db.execute("SELECT id, name, code FROM courses WHERE user_id=? ORDER BY name",
            (request.session["uid"],)).fetchall()
        chosen = cid if any(c["id"] == cid for c in courses) else 0
        lectures = db.execute("SELECT id, title FROM lectures WHERE course_id=? ORDER BY id DESC",
            (chosen,)).fetchall() if chosen else []
    return show_page(request, "tool", tool_key=tool, tool_title=selected[1],
        tool_description=selected[2], tool_status=selected[3], courses=courses,
        selected_course=chosen, lectures=lectures)

# Save lecture notes
@app.post("/lectures/{lid}/notes", name="save_notes")
async def save_notes(request: Request, lid: int):
    login_check = check_login(request)
    if login_check:
        return login_check
    get_user_lecture(request, lid)
    form = await get_form_data(request)
    notes = str(form.get("notes", ""))[:100000]
    with connect() as db:
        db.execute("""INSERT INTO lecture_notes(lecture_id,content) VALUES(?,?)
                    ON CONFLICT(lecture_id) DO UPDATE SET content=excluded.content,
                    updated_at=CURRENT_TIMESTAMP""", (lid, notes))
    show_message(request, "Your lecture notes were saved.")
    return redirect(request, "lecture", lid=lid)

# Save study guides
@app.post("/courses/{cid}/guide", name="save_guide")
async def save_guide(request: Request, cid: int):
    login_check = check_login(request)
    if login_check:
        return login_check
    get_user_course(request, cid)
    form = await get_form_data(request)
    guide = str(form.get("guide", ""))[:100000]
    with connect() as db:
        db.execute("""INSERT INTO study_guides(course_id,content) VALUES(?,?)
                    ON CONFLICT(course_id) DO UPDATE SET content=excluded.content""", (cid, guide))
    show_message(request, "Study guide saved.")
    return redirect(request, "course", cid=cid)

# Add practice cards
@app.post("/courses/{cid}/cards", name="add_card")
async def add_card(request: Request, cid: int):
    login_check = check_login(request)
    if login_check:
        return login_check
    get_user_course(request, cid)
    form = await get_form_data(request)
    question = str(form.get("question", "")).strip()[:500]
    answer = str(form.get("answer", "")).strip()[:2000]
    if question and answer:
        with connect() as db:
            db.execute("INSERT INTO study_cards(course_id,question,answer) VALUES(?,?,?)",
                       (cid, question, answer))
        show_message(request, "Practice card added.")
    return redirect(request, "course", cid=cid)

# Remove practice cards
@app.post("/courses/{cid}/cards/{card_id}/delete", name="delete_card")
async def delete_card(request: Request, cid: int, card_id: int):
    login_check = check_login(request)
    if login_check:
        return login_check
    get_user_course(request, cid)
    await get_form_data(request)
    with connect() as db:
        db.execute("DELETE FROM study_cards WHERE id=? AND course_id=?", (card_id, cid))
    return redirect(request, "course", cid=cid)
