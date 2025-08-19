from flask import Flask, request, redirect, render_template_string, url_for, abort
import sqlite3
import string
import random
from urllib.parse import urlparse
import os
import webbrowser

DB_PATH = "urls.db"

app = Flask(__name__)

# ----------------------- DB Helpers -----------------------

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS urls (
            short TEXT PRIMARY KEY,
            original TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


# ----------------------- Utils ----------------------------

ALPHABET = string.ascii_letters + string.digits


def generate_code(length: int = 6) -> str:
    return "".join(random.choice(ALPHABET) for _ in range(length))


def looks_like_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


# ----------------------- HTML (Minimal) -------------------

PAGE = """
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>나만의 단축링크</title>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; margin: 40px auto; max-width: 720px; line-height: 1.6; }
    .card { border: 1px solid #e5e7eb; border-radius: 16px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,.04); }
    input[type=text] { width: 100%; padding: 10px 12px; border: 1px solid #d1d5db; border-radius: 10px; }
    .row { display: grid; gap: 12px; }
    .btn { display: inline-block; padding: 10px 14px; border-radius: 10px; border: 0; background: #111827; color: white; cursor: pointer; }
    .muted { color: #6b7280; font-size: 14px; }
    .list { margin-top: 24px; }
    .item { padding: 10px 0; border-bottom: 1px dashed #e5e7eb; }
    code { background: #f3f4f6; padding: 3px 6px; border-radius: 6px; }
  </style>
</head>
<body>
  <h1>🔗 나만의 단축링크</h1>
  <div class="card">
    <form method="post" action="{{ url_for('shorten') }}">
      <div class="row">
        <label>원본 URL</label>
        <input type="text" name="long_url" placeholder="https://example.com/article/123" required />
        <label>커스텀 코드 (선택)</label>
        <input type="text" name="custom_code" placeholder="예: hello, promo2025" />
        <button class="btn" type="submit">단축하기</button>
        <div class="muted">결과 예: {{ request.host_url }}<code>abc123</code> 또는 {{ request.host_url }}<code>hello</code></div>
      </div>
    </form>
  </div>

  {% if short_url %}
  <div class="card" style="margin-top:20px;">
    <h3>✅ 단축 완료</h3>
    <p><a href="{{ short_url }}" target="_blank">{{ short_url }}</a></p>
    <button class="btn" onclick="navigator.clipboard.writeText('{{ short_url }}'); this.innerText='복사됨!';">주소 복사</button>
  </div>
  {% endif %}

  <div class="list">
    <h3>최근 생성된 링크</h3>
    {% if recent %}
      {% for row in recent %}
      <div class="item">
        <div><strong>{{ request.host_url }}{{ row['short'] }}</strong></div>
        <div class="muted">→ <a href="{{ row['original'] }}" target="_blank">{{ row['original'] }}</a></div>
        <form method="post" action="{{ url_for('delete', code=row['short']) }}" style="display:inline;">
            <button type="submit" class="btn" style="background:red;">삭제</button>
        </form>
      </div>
      {% endfor %}
    {% else %}
      <div class="muted">아직 생성된 링크가 없습니다.</div>
    {% endif %}
  </div>
</body>
</html>
"""


# ----------------------- Routes --------------------------

@app.route("/", methods=["GET"])
def index():
    conn = get_db_connection()
    recent = conn.execute(
        "SELECT short, original FROM urls ORDER BY created_at DESC LIMIT 10"
    ).fetchall()
    conn.close()
    return render_template_string(PAGE, recent=recent, short_url=None)


@app.route("/shorten", methods=["POST"])
def shorten():
    long_url = (request.form.get("long_url") or "").strip()
    custom_code = (request.form.get("custom_code") or "").strip()

    if not looks_like_url(long_url):
        return ("유효한 http(s):// URL을 입력하세요.", 400)

    conn = get_db_connection()
    cur = conn.cursor()

    def exists(code: str) -> bool:
        row = cur.execute("SELECT 1 FROM urls WHERE short = ?", (code,)).fetchone()
        return row is not None

    if custom_code:
        allowed = set(string.ascii_letters + string.digits + "-_")
        if not set(custom_code) <= allowed:
            conn.close()
            return ("커스텀 코드는 영문/숫자, -, _ 만 사용할 수 있습니다.", 400)
        code = custom_code
        if exists(code):
            conn.close()
            return ("이미 사용 중인 코드입니다. 다른 코드를 입력하세요.", 409)
    else:
        code = generate_code(6)
        while exists(code):
            code = generate_code(6)

    cur.execute("INSERT INTO urls (short, original) VALUES (?, ?)", (code, long_url))
    conn.commit()
    conn.close()

    short_url = request.host_url + code

    conn2 = get_db_connection()
    recent = conn2.execute(
        "SELECT short, original FROM urls ORDER BY created_at DESC LIMIT 10"
    ).fetchall()
    conn2.close()

    return render_template_string(PAGE, recent=recent, short_url=short_url)


@app.route("/<code>")
def follow(code: str):
    conn = get_db_connection()
    row = conn.execute("SELECT original FROM urls WHERE short = ?", (code,)).fetchone()
    conn.close()
    if not row:
        abort(404, description="존재하지 않는 단축 URL입니다.")
    return redirect(row["original"], code=302)


# ----------------------- Main ----------------------------

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        init_db()
    else:
        init_db()

    # 웹브라우저 자동 오픈 부분은 Render에서 불필요하므로 주석 처리
    # webbrowser.open("http://127.0.0.1:5000")

    # Render와 같은 클라우드 환경에 맞게 서버를 0.0.0.0에 바인딩
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

# ----------------------- 삭제 기능 추가 --------------------------

@app.route("/delete/<code>", methods=["POST"])
def delete(code: str):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM urls WHERE short = ?", (code,))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))    # 웹브라우저 자동 오픈 부분은 Render에서 불필요하므로 주석 처리
    # webbrowser.open("http://127.0.0.1:5000")

    # Render와 같은 클라우드 환경에 맞게 서버를 0.0.0.0에 바인딩
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

