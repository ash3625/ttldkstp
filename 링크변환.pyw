import os
import sqlite3
import string
import random
from datetime import datetime
import markdown

from flask import Flask, render_template, request, redirect, url_for, g

# --- 환경 설정 및 데이터베이스 초기화 ---

app = Flask(__name__)
# 데이터베이스 파일 경로
DATABASE = 'database.db'

# 데이터베이스 연결 가져오기
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        # 딕셔너리 형태로 결과를 반환하도록 설정
        db.row_factory = sqlite3.Row
    return db

# 애플리케이션 컨텍스트 종료 시 데이터베이스 연결 닫기
@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# 데이터베이스 테이블 초기화
def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        
        # 'urls' 테이블 생성
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                short_code TEXT UNIQUE NOT NULL,
                original_url TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 'posts' 테이블 생성 (블로그 게시물용)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        db.commit()

# --- 도우미 함수 ---

# 랜덤 단축 코드 생성
def generate_short_code(length=6):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

# --- 웹사이트 라우트 ---

# 홈 페이지 (단축링크)
@app.route('/')
def index():
    db = get_db()
    cursor = db.cursor()
    # 최근 10개의 링크를 생성일 기준 내림차순으로 가져오기
    cursor.execute("SELECT short_code AS short, original_url AS original FROM urls ORDER BY created_at DESC LIMIT 10")
    recent_links = cursor.fetchall()
    return render_template('index.html', recent=recent_links)

# URL 단축 처리
@app.route('/shorten', methods=['POST'])
def shorten():
    original_url = request.form['long_url']
    custom_code = request.form.get('custom_code')

    db = get_db()
    cursor = db.cursor()

    if custom_code:
        # 커스텀 코드가 이미 존재하는지 확인
        cursor.execute("SELECT * FROM urls WHERE short_code = ?", (custom_code,))
        if cursor.fetchone():
            return "이미 사용 중인 커스텀 코드입니다.", 409
        short_code = custom_code
    else:
        # 고유한 랜덤 코드 생성
        while True:
            short_code = generate_short_code()
            cursor.execute("SELECT * FROM urls WHERE short_code = ?", (short_code,))
            if cursor.fetchone() is None:
                break
    
    # 데이터베이스에 저장
    cursor.execute("INSERT INTO urls (short_code, original_url) VALUES (?, ?)", (short_code, original_url))
    db.commit()

    short_url = url_for('redirect_to_long_url', code=short_code, _external=True)
    return render_template('index.html', short_url=short_url)

# 단축 URL 리디렉션
@app.route('/<string:code>')
def redirect_to_long_url(code):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT original_url FROM urls WHERE short_code = ?", (code,))
    result = cursor.fetchone()
    if result:
        return redirect(result['original_url'])
    else:
        return "URL을 찾을 수 없습니다.", 404

# 링크 삭제
@app.route('/delete/<string:code>', methods=['POST'])
def delete(code):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM urls WHERE short_code = ?", (code,))
    db.commit()
    return redirect(url_for('index'))

# 블로그 페이지
@app.route('/blog')
def blog():
    db = get_db()
    cursor = db.cursor()
    # 모든 블로그 게시물 가져오기
    cursor.execute("SELECT id, title, created_at FROM posts ORDER BY created_at DESC")
    posts = cursor.fetchall()
    return render_template('blog.html', posts=posts)

# 개별 블로그 게시물 페이지
@app.route('/blog/<int:post_id>')
def post(post_id):
    db = get_db()
    cursor = db.cursor()
    # 특정 ID의 게시물 가져오기
    cursor.execute("SELECT title, content, created_at FROM posts WHERE id = ?", (post_id,))
    post_data = cursor.fetchone()
    
    if post_data:
        # Markdown 내용을 HTML로 변환
        post_html_content = markdown.markdown(post_data['content'])
        return render_template('post.html', post=post_data, post_html_content=post_html_content)
    else:
        return "게시물을 찾을 수 없습니다.", 404

# 소개 페이지
@app.route('/about')
def about():
    return render_template('about.html')

# --- 애플리케이션 실행 ---

if __name__ == '__main__':
    # 애플리케이션 실행 전에 데이터베이스 초기화
    init_db()
    # 샘플 블로그 게시물 추가 (테스트용)
    with app.app_context():
        db = get_db()
        db.execute("INSERT OR IGNORE INTO posts (id, title, content) VALUES (?, ?, ?)", 
                   (1, "나의 첫 번째 블로그 글", "이것은 **Markdown**으로 작성된 첫 번째 블로그 게시물입니다. `코드`도 포함할 수 있어요. \n\n* 안녕하세요\n* 반갑습니다"))
        db.execute("INSERT OR IGNORE INTO posts (id, title, content) VALUES (?, ?, ?)", 
                   (2, "웹 개발을 시작하며", "Flask를 사용한 웹사이트 개발은 정말 재미있습니다! 이 작은 프로젝트를 통해 많은 것을 배웠습니다."))
        db.commit()
    app.run(debug=True)
