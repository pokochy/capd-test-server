# ⚠️ INTENTIONALLY VULNERABLE — FOR TESTING ONLY
FROM python:3.11-slim

WORKDIR /app

# 필요 패키지 (ping 명령어 포함)
RUN apt-get update && apt-get install -y iputils-ping && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# uploads 디렉토리 생성
RUN mkdir -p uploads

# DB 초기화
RUN python init_db.py

EXPOSE 5000

# ⚠️ 운영 환경에서 절대 사용 금지
CMD ["python", "app.py"]
