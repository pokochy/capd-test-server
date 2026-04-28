# VulnApp

> 경고: 이 애플리케이션은 보안 취약점을 의도적으로 포함합니다.
> 로컬 또는 격리된 실습 환경에서만 사용하세요.
> 운영 환경이나 외부 공개 네트워크에 배포하면 안 됩니다.

## 개요

`VulnApp`은 보안 교육, 취약점 재현, 스캐너 테스트를 위한 Flask 기반 실습용 웹 애플리케이션입니다.  
여러 OWASP 유형의 취약한 엔드포인트를 한 프로젝트에서 확인할 수 있습니다.

현재 저장소에는 Flask가 참조하는 템플릿 파일이 포함되어 있으며, 기본 홈 화면과 각 취약점 데모 페이지가 모두 렌더링되도록 구성되어 있습니다.

## 프로젝트 구조

```text
server/
├── app.py
├── init_db.py
├── requirements.txt
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── README.md
├── vuln_app.db              # 실행 후 생성될 수 있음
├── uploads/                 # 업로드 파일 저장 경로
└── templates/
    ├── base.html
    ├── index.html
    ├── sqli.html
    ├── xss_reflected.html
    ├── xss_stored.html
    ├── cmdi.html
    ├── file_upload.html
    ├── traversal.html
    ├── ssrf.html
    ├── csrf.html
    ├── csrf_attacker.html
    └── login.html
```

## 설치 및 실행

### 1. Python으로 직접 실행

```bash
cd server
python -m venv venv
```

가상환경 활성화:

```bash
# Windows PowerShell
.\venv\Scripts\Activate.ps1

# Linux / macOS
source venv/bin/activate
```

의존성 설치:

```bash
pip install -r requirements.txt
```

DB 초기화:

```bash
python init_db.py
```

앱 실행:

```bash
python app.py
```

접속 주소:

```text
http://127.0.0.1:5000
```

### 2. Docker로 실행

```bash
docker compose up --build
```

백그라운드 실행:

```bash
docker compose up -d
```

종료:

```bash
docker compose down
```

## 의존성

현재 `requirements.txt`는 앱이 직접 사용하는 런타임 의존성만 고정합니다.

```text
Flask==3.0.3
requests==2.32.3
urllib3==2.2.2
Werkzeug==3.0.3
```

`Jinja2`, `click`, `itsdangerous`, `blinker` 등은 Flask의 전이 의존성으로 함께 설치됩니다.

## 제공 기능

| 기능 | 경로 | 설명 |
|------|------|------|
| Home | `/` | 메인 페이지 |
| SQL Injection | `/sqli` | POST 기반 SQLi 데모 |
| SQL Injection Search | `/sqli/search` | GET 기반 SQLi 검색 데모 |
| Reflected XSS | `/xss/reflected` | 입력값 반사 렌더링 |
| Stored XSS | `/xss/stored` | 댓글 저장 후 렌더링 |
| Command Injection | `/cmdi` | ping 명령 조합 데모 |
| File Upload | `/upload` | 업로드 검증 부재 데모 |
| Directory Traversal | `/traversal` | 파일 경로 입력 데모 |
| SSRF | `/ssrf` | 서버 측 URL 요청 데모 |
| CSRF | `/csrf` | 송금 폼 및 이력 보기 |
| CSRF Attacker | `/csrf/attacker` | 자동 전송 공격 페이지 |
| Login | `/login` | 취약한 로그인 |
| IDOR API | `/api/user/<id>`, `/api/users` | 인증 없는 사용자 조회 |
| Debug Info | `/debug` | 민감 정보 노출 예시 |
| Open Redirect | `/redirect?url=...` | 검증 없는 리다이렉트 |

## 샘플 계정

`init_db.py` 실행 시 아래 테스트 계정이 생성됩니다.

```text
admin / admin123
alice / password1
bob / qwerty
charlie / letmein
```

## 참고 사항

- Flask 디버그 모드로 실행됩니다.
- 첫 실행 시 DB 파일이 없으면 앱이 자동으로 초기화할 수 있습니다.
- `templates/` 디렉터리가 없으면 `/` 포함 대부분의 라우트가 `TemplateNotFound`로 실패합니다.
- `uploads/` 디렉터리는 업로드 기능 사용 시 자동 생성됩니다.

## 안전 주의사항

1. 로컬 또는 격리된 테스트 환경에서만 실행하세요.
2. 공인 IP나 외부 접근 가능한 네트워크에 노출하지 마세요.
3. 일부 기능은 실제 시스템 명령 실행, 서버 측 요청, 파일 읽기/업로드를 포함합니다.
4. 테스트 후 프로세스와 생성 산출물을 정리하세요.

## 참고 링크

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [DVWA](https://github.com/digininja/DVWA)
- [PortSwigger Web Security Academy](https://portswigger.net/web-security)
