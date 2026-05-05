"""
⚠️  INTENTIONALLY VULNERABLE WEB APPLICATION ⚠️
================================================================
For security research, vulnerability scanner testing, and
educational purposes ONLY.
DO NOT deploy in production or expose to public internet.
================================================================
"""

import json
import os
import re
import sqlite3
import subprocess
import xml.etree.ElementTree as ET
import requests
from flask import (
    Flask, render_template, render_template_string, request, redirect, url_for,
    session, g, jsonify, send_file, make_response
)
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "super_insecure_secret_key_1234"  # 취약: 하드코딩된 시크릿

DATABASE = "vuln_app.db"
UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

LAB_USERS = [
    {
        "id": 1,
        "username": "admin",
        "password": "admin123",
        "email": "admin@vuln-app.local",
        "role": "admin",
        "department": "ops",
    },
    {
        "id": 2,
        "username": "alice",
        "password": "password1",
        "email": "alice@example.com",
        "role": "user",
        "department": "sales",
    },
    {
        "id": 3,
        "username": "bob",
        "password": "qwerty",
        "email": "bob@example.com",
        "role": "user",
        "department": "engineering",
    },
    {
        "id": 4,
        "username": "charlie",
        "password": "letmein",
        "email": "charlie@example.com",
        "role": "user",
        "department": "support",
    },
]

XML_DIRECTORY = """<users>
  <user id="1" username="admin" password="admin123" email="admin@vuln-app.local" role="admin" />
  <user id="2" username="alice" password="password1" email="alice@example.com" role="user" />
  <user id="3" username="bob" password="qwerty" email="bob@example.com" role="user" />
  <user id="4" username="charlie" password="letmein" email="charlie@example.com" role="user" />
</users>"""


def nosql_condition_matches(value, condition):
    if isinstance(condition, dict):
        for operator, expected in condition.items():
            if operator == "$ne":
                if value == expected:
                    return False
            elif operator == "$regex":
                if not re.search(str(expected), str(value)):
                    return False
            elif operator == "$in":
                if not isinstance(expected, list) or value not in expected:
                    return False
            elif operator == "$exists":
                if bool(expected) != (value is not None):
                    return False
            elif operator == "$gt":
                if str(value) <= str(expected):
                    return False
            else:
                return False
        return True

    return value == condition


def ldap_pattern_matches(value, pattern):
    if pattern == "":
        return value == ""
    regex = "^" + re.escape(pattern).replace("\\*", ".*") + "$"
    return re.match(regex, value) is not None


def looks_like_ldap_breakout(value):
    lowered = value.lower()
    breakout_tokens = (")(", "(|", "(&", "*)", "uid=*", "objectclass=*")
    return any(token in lowered for token in breakout_tokens)


def looks_like_xpath_bypass(value):
    compact = re.sub(r"\s+", "", value.lower())
    bypass_tokens = (
        "or'1'='1",
        'or"1"="1',
        "or1=1",
        "ortrue()",
        "or@",
        "//*",
    )
    return any(token in compact for token in bypass_tokens)

# ──────────────────────────────────────────────
# DB 유틸리티
# ──────────────────────────────────────────────

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def init_db():
    """데이터베이스 초기화 및 샘플 데이터 삽입"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # users 테이블
    c.execute("DROP TABLE IF EXISTS users")
    c.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            email TEXT,
            role TEXT DEFAULT 'user'
        )
    """)
    c.executemany("INSERT INTO users (username, password, email, role) VALUES (?,?,?,?)", [
        ("admin",  "admin123",    "admin@vuln-app.local",  "admin"),
        ("alice",  "password1",   "alice@example.com",     "user"),
        ("bob",    "qwerty",      "bob@example.com",       "user"),
        ("charlie","letmein",     "charlie@example.com",   "user"),
    ])

    # products 테이블
    c.execute("DROP TABLE IF EXISTS products")
    c.execute("""
        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            description TEXT
        )
    """)
    c.executemany("INSERT INTO products (name, price, description) VALUES (?,?,?)", [
        ("Laptop Pro",   1299.99, "High-performance laptop"),
        ("Wireless Mouse", 29.99, "Ergonomic wireless mouse"),
        ("USB-C Hub",      49.99, "7-in-1 USB-C hub"),
        ("Mechanical Keyboard", 89.99, "RGB mechanical keyboard"),
    ])

    # comments 테이블 (Stored XSS)
    c.execute("DROP TABLE IF EXISTS comments")
    c.execute("""
        CREATE TABLE comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            author TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.executemany("INSERT INTO comments (author, content) VALUES (?,?)", [
        ("admin",  "Welcome to the vulnerable comment board!"),
        ("alice",  "This is a test comment."),
    ])

    # csrf_transfers 테이블
    c.execute("DROP TABLE IF EXISTS csrf_transfers")
    c.execute("""
        CREATE TABLE csrf_transfers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user TEXT NOT NULL,
            to_user TEXT NOT NULL,
            amount REAL NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    print("[+] Database initialized with sample data.")


# ──────────────────────────────────────────────
# INDEX
# ──────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


# ──────────────────────────────────────────────
# 1. SQL INJECTION
# ──────────────────────────────────────────────

@app.route("/sqli", methods=["GET", "POST"])
def sqli():
    result = None
    query_used = None
    error = None

    if request.method == "POST":
        username = request.form.get("username", "")
        # ⚠️ 취약: 직접 문자열 포맷팅으로 SQL 구성
        query_used = f"SELECT * FROM users WHERE username = '{username}'"
        try:
            db = get_db()
            rows = db.execute(query_used).fetchall()
            result = [dict(row) for row in rows]
        except Exception as e:
            error = str(e)

    return render_template("sqli.html", result=result, query=query_used, error=error)


@app.route("/sqli/search", methods=["GET"])
def sqli_search():
    """GET 파라미터 기반 SQLi (스캐너 탐지 용이)"""
    q = request.args.get("q", "")
    result = None
    query_used = None
    error = None

    if q:
        # ⚠️ 취약
        query_used = f"SELECT * FROM products WHERE name LIKE '%{q}%'"
        try:
            db = get_db()
            rows = db.execute(query_used).fetchall()
            result = [dict(row) for row in rows]
        except Exception as e:
            error = str(e)

    return render_template("sqli.html",
                           result=result, query=query_used,
                           error=error, mode="search", q=q)


# ──────────────────────────────────────────────
# 2. REFLECTED XSS
# ──────────────────────────────────────────────

@app.route("/xss/reflected", methods=["GET", "POST"])
def xss_reflected():
    user_input = ""
    if request.method == "POST":
        user_input = request.form.get("search", "")
    elif request.method == "GET":
        user_input = request.args.get("q", "")

    # ⚠️ 취약: Jinja2 의 |safe 필터로 이스케이프 우회
    return render_template("xss_reflected.html", user_input=user_input)


# ──────────────────────────────────────────────
# 3. STORED XSS
# ──────────────────────────────────────────────

@app.route("/xss/stored", methods=["GET", "POST"])
def xss_stored():
    error = None
    if request.method == "POST":
        author  = request.form.get("author", "Anonymous")
        content = request.form.get("content", "")
        if content.strip():
            # ⚠️ 취약: 입력값 그대로 DB 저장
            db = get_db()
            db.execute("INSERT INTO comments (author, content) VALUES (?, ?)",
                       (author, content))
            db.commit()
        else:
            error = "Content cannot be empty."

    db = get_db()
    comments = db.execute(
        "SELECT * FROM comments ORDER BY created_at DESC"
    ).fetchall()
    comments = [dict(c) for c in comments]
    return render_template("xss_stored.html", comments=comments, error=error)


@app.route("/xss/stored/delete/<int:comment_id>")
def delete_comment(comment_id):
    db = get_db()
    db.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
    db.commit()
    return redirect(url_for("xss_stored"))


# ──────────────────────────────────────────────
# 4. COMMAND INJECTION
# ──────────────────────────────────────────────

@app.route("/cmdi", methods=["GET", "POST"])
def cmdi():
    output = None
    cmd_used = None
    error = None

    if request.method == "POST":
        target = request.form.get("target", "")
        # ⚠️ 취약: 셸 인젝션 가능
        cmd_used = f"ping -c 2 {target}"
        try:
            output = subprocess.check_output(
                cmd_used, shell=True,          # ⚠️ shell=True
                stderr=subprocess.STDOUT,
                timeout=10,
                text=True
            )
        except subprocess.CalledProcessError as e:
            output = e.output
        except Exception as e:
            error = str(e)

    elif request.method == "GET":
        target = request.args.get("host", "")
        if target:
            cmd_used = f"ping -c 2 {target}"
            try:
                output = subprocess.check_output(
                    cmd_used, shell=True,
                    stderr=subprocess.STDOUT,
                    timeout=10, text=True
                )
            except subprocess.CalledProcessError as e:
                output = e.output
            except Exception as e:
                error = str(e)

    return render_template("cmdi.html", output=output, cmd=cmd_used, error=error)


# ──────────────────────────────────────────────
# 5. FILE UPLOAD
# ──────────────────────────────────────────────

@app.route("/upload", methods=["GET", "POST"])
def file_upload():
    uploaded_files = []
    success = None
    error = None

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    if request.method == "POST":
        file = request.files.get("file")
        if file and file.filename:
            # ⚠️ 취약: 파일 타입/확장자 검증 없음
            filename = file.filename  # secure_filename() 미사용
            save_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(save_path)
            success = f"File '{filename}' uploaded successfully!"
        else:
            error = "No file selected."

    # 업로드된 파일 목록
    if os.path.exists(UPLOAD_FOLDER):
        uploaded_files = os.listdir(UPLOAD_FOLDER)

    return render_template("file_upload.html",
                           uploaded_files=uploaded_files,
                           success=success, error=error)


@app.route("/uploads/<path:filename>")
def serve_upload(filename):
    # ⚠️ 취약: 업로드된 파일을 직접 서빙 (PHP/HTML 실행 가능 환경이면 위험)
    upload_dir = os.path.abspath(UPLOAD_FOLDER)
    file_path = os.path.join(upload_dir, filename)
    return send_file(file_path)


# ──────────────────────────────────────────────
# 6. DIRECTORY TRAVERSAL
# ──────────────────────────────────────────────

@app.route("/traversal", methods=["GET"])
def dir_traversal():
    filename = request.args.get("file", "")
    content = None
    error = None
    file_used = None

    if filename:
        # ⚠️ 취약: 경로 검증 없이 파일 읽기
        file_used = filename
        try:
            with open(filename, "r", errors="replace") as f:
                content = f.read(4096)  # 최대 4KB
        except FileNotFoundError:
            error = f"File not found: {filename}"
        except PermissionError:
            error = f"Permission denied: {filename}"
        except Exception as e:
            error = str(e)

    return render_template("traversal.html",
                           content=content, filename=file_used, error=error)


# ──────────────────────────────────────────────
# 7. SSRF
# ──────────────────────────────────────────────

@app.route("/ssrf", methods=["GET", "POST"])
def ssrf():
    response_content = None
    url_used = None
    status_code = None
    error = None

    if request.method == "POST":
        url = request.form.get("url", "").strip()
    else:
        url = request.args.get("url", "").strip()

    if url:
        url_used = url
        # ⚠️ 취약: URL 검증 없이 서버에서 요청 발송
        try:
            resp = requests.get(url, timeout=5,
                                allow_redirects=True,
                                verify=False)
            status_code = resp.status_code
            response_content = resp.text[:3000]
        except requests.exceptions.ConnectionError as e:
            error = f"Connection error: {e}"
        except requests.exceptions.Timeout:
            error = "Request timed out (5s)"
        except Exception as e:
            error = f"Error: {e}"

    return render_template("ssrf.html",
                           response=response_content,
                           url=url_used,
                           status=status_code,
                           error=error)


# ──────────────────────────────────────────────
# 8. CSRF
# ──────────────────────────────────────────────

@app.route("/ssti", methods=["GET", "POST"])
def ssti():
    template_source = request.values.get("template", "")
    name = request.values.get("name", "guest")
    rendered = None
    error = None

    if request.method == "POST" or request.args:
        if template_source:
            try:
                # Intentionally vulnerable: user input is executed as a Jinja template.
                rendered = render_template_string(
                    template_source,
                    name=name,
                    users=LAB_USERS,
                    request=request,
                    config=app.config,
                )
            except Exception as e:
                error = str(e)

    return render_template(
        "ssti.html",
        template_source=template_source,
        name=name,
        rendered=rendered,
        error=error,
    )


@app.route("/nosqli", methods=["GET", "POST"])
def nosqli():
    default_query = '{\n  "username": "admin",\n  "password": "admin123"\n}'
    query_text = request.values.get("query", default_query)
    parsed_query = None
    result = None
    error = None

    if request.method == "POST" or request.args:
        try:
            parsed_query = json.loads(query_text)
            if not isinstance(parsed_query, dict):
                raise ValueError("Top-level query must be a JSON object.")

            result = [
                user for user in LAB_USERS
                if all(
                    nosql_condition_matches(user.get(field), condition)
                    for field, condition in parsed_query.items()
                )
            ]
        except Exception as e:
            error = str(e)

    return render_template(
        "nosqli.html",
        query_text=query_text,
        parsed_query=parsed_query,
        result=result,
        error=error,
    )


@app.route("/ldap", methods=["GET", "POST"])
def ldap_injection():
    username = request.values.get("username", "")
    password = request.values.get("password", "")
    ldap_filter = None
    result = None

    if request.method == "POST" or request.args:
        ldap_filter = f"(&(uid={username})(userPassword={password}))"
        combined = f"{username}{password}"

        if looks_like_ldap_breakout(combined):
            result = LAB_USERS
        else:
            result = [
                user for user in LAB_USERS
                if ldap_pattern_matches(user["username"], username)
                and ldap_pattern_matches(user["password"], password)
            ]

    return render_template(
        "ldap.html",
        username=username,
        password=password,
        ldap_filter=ldap_filter,
        result=result,
    )


@app.route("/xpath", methods=["GET", "POST"])
def xpath_injection():
    username = request.values.get("username", "")
    password = request.values.get("password", "")
    xpath_query = None
    result = None
    error = None

    if request.method == "POST" or request.args:
        xpath_query = (
            "/users/user[@username='"
            f"{username}' and @password='{password}']"
        )
        try:
            ET.fromstring(XML_DIRECTORY)
            if looks_like_xpath_bypass(username) or looks_like_xpath_bypass(password):
                result = LAB_USERS
            else:
                result = [
                    user for user in LAB_USERS
                    if user["username"] == username and user["password"] == password
                ]
        except Exception as e:
            error = str(e)

    return render_template(
        "xpath.html",
        username=username,
        password=password,
        xpath_query=xpath_query,
        xml_source=XML_DIRECTORY,
        result=result,
        error=error,
    )


@app.route("/crlf", methods=["GET", "POST"])
@app.route("/headers", methods=["GET", "POST"])
def header_injection():
    header_name = request.values.get("name", "X-Lab-User")
    header_value = request.values.get("value", "")
    body = request.values.get("body", "header injection lab")
    submitted = request.method == "POST" or bool(request.args)
    header_error = None

    if submitted:
        try:
            response = make_response(
                render_template(
                    "header_injection.html",
                    header_name=header_name,
                    header_value=header_value,
                    body=body,
                    header_error=None,
                    header_applied=True,
                )
            )
            response.headers[header_name] = header_value
            return response
        except Exception as e:
            header_error = str(e)

    return render_template(
        "header_injection.html",
        header_name=header_name,
        header_value=header_value,
        body=body,
        header_error=header_error,
        header_applied=False,
    )


@app.route("/csrf", methods=["GET"])
def csrf_page():
    db = get_db()
    transfers = db.execute(
        "SELECT * FROM csrf_transfers ORDER BY created_at DESC LIMIT 20"
    ).fetchall()
    transfers = [dict(t) for t in transfers]
    # 기본 로그인 세션 설정 (데모용)
    if "csrf_user" not in session:
        session["csrf_user"] = "alice"
    return render_template("csrf.html",
                           transfers=transfers,
                           current_user=session.get("csrf_user"))


@app.route("/csrf/transfer", methods=["POST"])
def csrf_transfer():
    # ⚠️ 취약: CSRF 토큰 검증 없음
    to_user = request.form.get("to_user", "")
    amount  = request.form.get("amount", "0")
    from_user = session.get("csrf_user", "alice")

    try:
        amount = float(amount)
    except ValueError:
        amount = 0.0

    if to_user and amount > 0:
        db = get_db()
        db.execute(
            "INSERT INTO csrf_transfers (from_user, to_user, amount) VALUES (?, ?, ?)",
            (from_user, to_user, amount)
        )
        db.commit()

    return redirect(url_for("csrf_page"))


@app.route("/csrf/attacker")
def csrf_attacker():
    """공격자 페이지 시뮬레이션 - CSRF 포지 요청 예시"""
    # 현재 서버 주소를 동적으로 가져옴
    target_url = request.host_url + "csrf/transfer"
    return render_template("csrf_attacker.html", target_url=target_url)


@app.route("/csrf/set-user/<username>")
def csrf_set_user(username):
    session["csrf_user"] = username
    return redirect(url_for("csrf_page"))


# ──────────────────────────────────────────────
# BONUS: 취약한 API 엔드포인트 (IDOR)
# ──────────────────────────────────────────────

@app.route("/api/user/<int:user_id>")
def api_user(user_id):
    # ⚠️ 취약: 인증 없이 모든 유저 정보 노출 (IDOR)
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if row:
        return jsonify(dict(row))
    return jsonify({"error": "User not found"}), 404


@app.route("/api/users")
def api_users():
    # ⚠️ 취약: 인증 없이 전체 유저 목록 노출
    db = get_db()
    rows = db.execute("SELECT * FROM users").fetchall()
    return jsonify([dict(r) for r in rows])


# ──────────────────────────────────────────────
# BONUS: 취약한 인증 (Broken Auth)
# ──────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        # ⚠️ 취약: SQLi + 평문 패스워드 비교
        query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
        try:
            db = get_db()
            row = db.execute(query).fetchone()
            if row:
                session["logged_in"] = True
                session["username"] = dict(row)["username"]
                session["role"] = dict(row)["role"]
                return redirect(url_for("index"))
            else:
                error = "Invalid credentials."
        except Exception as e:
            error = str(e)

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ──────────────────────────────────────────────
# BONUS: 민감 정보 노출 (Sensitive Data Exposure)
# ──────────────────────────────────────────────

@app.route("/debug")
def debug_info():
    # ⚠️ 취약: 서버 환경 정보 노출
    info = {
        "python_path": os.sys.executable,
        "cwd": os.getcwd(),
        "env": dict(os.environ),          # 환경변수 전체 노출
        "secret_key": app.secret_key,     # 시크릿 키 노출
        "database": DATABASE,
    }
    return jsonify(info)


@app.route("/robots.txt")
def robots():
    # ⚠️ 취약: 민감 경로가 robots.txt에 노출
    content = """User-agent: *
Disallow: /admin
Disallow: /debug
Disallow: /api/
Disallow: /uploads/
Disallow: /.env
"""
    return content, 200, {"Content-Type": "text/plain"}


# ──────────────────────────────────────────────
# BONUS: 헤더 인젝션 (Response Splitting)
# ──────────────────────────────────────────────

@app.route("/redirect")
def open_redirect():
    # ⚠️ 취약: 검증 없는 오픈 리다이렉트
    url = request.args.get("url", "/")
    return redirect(url)


# ──────────────────────────────────────────────
# 앱 실행
# ──────────────────────────────────────────────

if __name__ == "__main__":
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    if not os.path.exists(DATABASE):
        print("[*] Initializing database...")
        init_db()
    else:
        print("[*] Database already exists. Skipping init.")
        print("[*] Run 'python init_db.py' to reinitialize.")
    print("[!] WARNING: This app is intentionally vulnerable!")
    print("[!] Do NOT run in production or expose to the internet.")
    app.run(host="0.0.0.0", port=5000, debug=True)
