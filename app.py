from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = "sprint1"
TOOLS = [("record", "Record Lectures"), ("analyze", "Analyze Notes"), ("catchup", "Lecture Catch Up"), ("guides", "Study Guides")]

def context(**kwargs):
    return dict(username=session.get("username"), tools=TOOLS, subjects=session.get("subjects", []), **kwargs)

@app.route("/")
def home():
    return render_template("index1.html", page="home", **context())

@app.route("/join", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        name = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if name and password:
            session["username"] = name
            session.setdefault("subjects", [])
            return redirect(url_for("dashboard"))
    return render_template("index1.html", page="login", **context())

@app.route("/dashboard")
def dashboard():
    if not session.get("username"):
        return redirect(url_for("login"))
    return render_template("index1.html", page="dashboard", **context())

@app.route("/subjects", methods=["POST"])
def add_subject():
    if not session.get("username"):
        return redirect(url_for("login"))
    subject = request.form.get("subject", "").strip()[:70]
    if subject:
        subjects = session.get("subjects", [])
        if subject not in subjects:
            session["subjects"] = subjects + [subject]
    return redirect(url_for("dashboard"))

@app.route("/tools/<tool>")
def tool_page(tool):
    tool_names = dict(TOOLS)
    if tool not in tool_names:
        return redirect(url_for("dashboard"))
    if not session.get("username"):
        return redirect(url_for("login"))
    return render_template("index1.html", page="tool", tool_title=tool_names[tool], **context())

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(debug=True)
