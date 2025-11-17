# 🚀 EC2에서 캠퍼스메이트 실행하기

## 📋 목차
1. [시스템 요구사항 확인](#1-시스템-요구사항-확인)
2. [백엔드 설정 및 실행](#2-백엔드-설정-및-실행)
3. [프론트엔드 설정 및 실행](#3-프론트엔드-설정-및-실행)
4. [데이터베이스 초기화](#4-데이터베이스-초기화)
5. [접속 확인](#5-접속-확인)
6. [문제 해결](#6-문제-해결)

---

## 1. 시스템 요구사항 확인

### 1.1 Python 버전 확인
```bash
python3 --version
# 필요: Python 3.11+
```

**Python이 없거나 버전이 낮은 경우:**
```bash
# Amazon Linux 2023
sudo dnf install python3.11 -y

# Ubuntu
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip -y
```

### 1.2 Node.js 버전 확인
```bash
node --version
npm --version
# 필요: Node.js 18+
```

**Node.js가 없는 경우:**
```bash
# Node.js 18 LTS 설치
curl -fsSL https://rpm.nodesource.com/setup_18.x | sudo bash -
sudo yum install -y nodejs

# 또는 Ubuntu
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs
```

### 1.3 Git 확인 (이미 clone했다면 OK)
```bash
git --version
```

---

## 2. 백엔드 설정 및 실행

### 2.1 백엔드 디렉토리로 이동
```bash
cd ~/MLOps_assignment/backend
```

### 2.2 Python 가상환경 생성
```bash
python3 -m venv venv
source venv/bin/activate  # 가상환경 활성화
```

**가상환경 활성화 확인:**
```bash
which python
# 결과: /home/ec2-user/MLOps_assignment/backend/venv/bin/python
```

### 2.3 패키지 설치
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**설치 중 오류 발생 시:**
```bash
# psycopg2 설치 오류 해결
sudo yum install postgresql-devel python3-devel gcc -y

# 또는 Ubuntu
sudo apt-get install libpq-dev python3-dev gcc -y

# 다시 설치
pip install -r requirements.txt
```

### 2.4 환경 변수 설정

**`.env` 파일 생성:**
```bash
nano .env
```

**다음 내용 입력:**
```env
# AWS 설정
AWS_REGION=us-west-1

# PostgreSQL 데이터베이스 설정
DATABASE_URL=postgresql://postgres:12345678aA@database-1.cpyomug2w3oq.us-west-1.rds.amazonaws.com:5432/postgres
DB_HOST=database-1.cpyomug2w3oq.us-west-1.rds.amazonaws.com
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=12345678aA

# S3 설정
S3_BUCKET_NAME=ysu-ml-a-13-s3
S3_REGION=us-west-1

# 기본 설정
DEFAULT_SCHOOL_ID=1
```

**저장:** `Ctrl+O` → Enter → `Ctrl+X`

### 2.5 데이터베이스 테이블 생성
```bash
python init_db.py
```

**성공 메시지:**
```
Database engine created. Creating tables...
Tables created successfully!
Database initialization complete.
```

### 2.6 백엔드 서버 실행

**개발 모드 (포트 8000):**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**프로덕션 모드 (백그라운드 실행):**
```bash
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 > server.log 2>&1 &
```

**실행 확인:**
```bash
curl http://localhost:8000
# 응답: {"status":"ok","message":"Welcome to the CampusMate API!"}
```

**로그 확인:**
```bash
tail -f server.log
```

---

## 3. 프론트엔드 설정 및 실행

### 3.1 새 터미널 열기 (또는 tmux 사용)
```bash
# 백엔드는 계속 실행되어야 하므로 새 터미널 필요
# tmux 사용 권장
sudo yum install tmux -y
tmux new -s backend  # 백엔드용 세션
# Ctrl+B, D로 나가기

tmux new -s frontend  # 프론트엔드용 세션
```

### 3.2 프론트엔드 디렉토리로 이동
```bash
cd ~/MLOps_assignment/frontend
```

### 3.3 환경 변수 설정

**`.env` 파일 생성:**
```bash
nano .env
```

**다음 내용 입력:**
```env
REACT_APP_API_URL=http://localhost:8000
```

**EC2 퍼블릭 IP로 외부 접속을 원하는 경우:**
```env
REACT_APP_API_URL=http://YOUR_EC2_PUBLIC_IP:8000
```

### 3.4 패키지 설치
```bash
npm install
```

**설치 시간:** 약 2-5분 소요

### 3.5 프론트엔드 실행

**개발 모드 (포트 3000):**
```bash
npm start
```

**프로덕션 빌드:**
```bash
npm run build
# build 폴더 생성됨

# 간단한 서버로 실행
npm install -g serve
serve -s build -l 3000
```

**백그라운드 실행:**
```bash
nohup npm start > frontend.log 2>&1 &
```

---

## 4. 데이터베이스 초기화

### 4.1 초기 데이터 스크립트 생성

**파일 생성:**
```bash
cd ~/MLOps_assignment/backend
nano init_sample_data.py
```

**다음 내용 입력:**
```python
#!/usr/bin/env python3
"""
초기 샘플 데이터 입력 스크립트
"""
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.database.database import SessionLocal
from app.database import models

def init_sample_data():
    db = SessionLocal()

    try:
        print("=" * 60)
        print("초기 데이터 입력 시작")
        print("=" * 60)

        # 1. 학교 추가
        print("\n1. 학교 추가...")
        school = db.query(models.School).filter(models.School.name == "연성대학교").first()
        if not school:
            school = models.School(name="연성대학교")
            db.add(school)
            db.commit()
            db.refresh(school)
            print(f"✅ 학교 추가 완료: {school.name} (ID: {school.id})")
        else:
            print(f"ℹ️  학교 이미 존재: {school.name} (ID: {school.id})")

        # 2. 담당 부서 추가
        print("\n2. 담당 부서 추가...")
        contacts_data = [
            {
                "category": "academic",
                "department": "학사지원팀",
                "contact_info": "031-123-4567"
            },
            {
                "category": "scholarship",
                "department": "학생지원팀",
                "contact_info": "031-123-5678"
            },
            {
                "category": "facilities",
                "department": "시설관리팀",
                "contact_info": "031-123-6789"
            },
            {
                "category": "career",
                "department": "학생취업처",
                "contact_info": "031-123-7890"
            }
        ]

        for contact_data in contacts_data:
            existing = db.query(models.DefaultContact).filter(
                models.DefaultContact.school_id == school.id,
                models.DefaultContact.category == contact_data["category"]
            ).first()

            if not existing:
                contact = models.DefaultContact(
                    school_id=school.id,
                    **contact_data
                )
                db.add(contact)
                print(f"✅ 추가: {contact_data['category']} - {contact_data['department']}")
            else:
                print(f"ℹ️  이미 존재: {contact_data['category']}")

        db.commit()

        # 3. RSS 피드 추가 (예시)
        print("\n3. RSS 피드 추가...")
        rss_url = "https://www.yeonsung.ac.kr/korean/board/notice/rss"
        existing_rss = db.query(models.RssFeed).filter(
            models.RssFeed.school_id == school.id,
            models.RssFeed.url == rss_url
        ).first()

        if not existing_rss:
            rss_feed = models.RssFeed(
                school_id=school.id,
                url=rss_url
            )
            db.add(rss_feed)
            db.commit()
            print(f"✅ RSS 피드 추가: {rss_url}")
        else:
            print(f"ℹ️  RSS 피드 이미 존재")

        print("\n" + "=" * 60)
        print("✅ 초기 데이터 입력 완료!")
        print("=" * 60)

        # 4. 데이터 확인
        print("\n📊 현재 데이터 현황:")
        print(f"  학교 수: {db.query(models.School).count()}")
        print(f"  담당 부서 수: {db.query(models.DefaultContact).count()}")
        print(f"  RSS 피드 수: {db.query(models.RssFeed).count()}")
        print(f"  문서 수: {db.query(models.Document).count()}")
        print(f"  청크 수: {db.query(models.DocumentChunk).count()}")

    except Exception as e:
        db.rollback()
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    init_sample_data()
```

### 4.2 스크립트 실행
```bash
# 가상환경 활성화 확인
source venv/bin/activate

# 스크립트 실행
python init_sample_data.py
```

**성공 메시지:**
```
============================================================
초기 데이터 입력 시작
============================================================

1. 학교 추가...
✅ 학교 추가 완료: 연성대학교 (ID: 1)

2. 담당 부서 추가...
✅ 추가: academic - 학사지원팀
✅ 추가: scholarship - 학생지원팀
✅ 추가: facilities - 시설관리팀
✅ 추가: career - 학생취업처

3. RSS 피드 추가...
✅ RSS 피드 추가: https://www.yeonsung.ac.kr/korean/board/notice/rss

============================================================
✅ 초기 데이터 입력 완료!
============================================================
```

---

## 5. 접속 확인

### 5.1 백엔드 API 확인
```bash
# 헬스 체크
curl http://localhost:8000

# API 문서 확인
curl http://localhost:8000/docs
```

브라우저에서: `http://YOUR_EC2_IP:8000/docs`

### 5.2 프론트엔드 확인

브라우저에서: `http://YOUR_EC2_IP:3000`

### 5.3 EC2 보안 그룹 설정

**AWS 콘솔 → EC2 → 보안 그룹**

다음 포트 열기:
- **포트 8000**: 백엔드 API (TCP)
- **포트 3000**: 프론트엔드 (TCP)
- **소스**: `0.0.0.0/0` (테스트용) 또는 본인 IP만

---

## 6. 문제 해결

### 6.1 백엔드가 시작되지 않음

**증상:** `ModuleNotFoundError: No module named 'boto3'`

**해결:**
```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
```

### 6.2 데이터베이스 연결 오류

**증상:** `could not connect to server`

**원인:** RDS 보안 그룹이 EC2를 허용하지 않음

**해결:**
1. RDS 보안 그룹에서 EC2 보안 그룹 허용
2. 또는 EC2의 프라이빗 IP 허용

### 6.3 포트가 이미 사용 중

**증상:** `Address already in use`

**해결:**
```bash
# 사용 중인 프로세스 찾기
lsof -i :8000
# 또는
netstat -tulpn | grep 8000

# 프로세스 종료
kill -9 <PID>
```

### 6.4 프론트엔드가 백엔드에 연결 안됨

**증상:** `Network Error` 또는 CORS 오류

**해결:**
1. `frontend/.env`에서 `REACT_APP_API_URL` 확인
2. 백엔드가 실행 중인지 확인: `curl http://localhost:8000`
3. EC2 보안 그룹에서 포트 8000 열려있는지 확인

---

## 🎉 실행 완료!

모든 단계가 성공적으로 완료되었다면:

✅ **백엔드**: `http://YOUR_EC2_IP:8000`
✅ **프론트엔드**: `http://YOUR_EC2_IP:3000`
✅ **챗봇**: 질문 입력하여 테스트
✅ **문서 업로드**: "📄 문서 업로드" 버튼으로 PDF 업로드

---

## 🔄 서버 재시작 방법

### 백엔드 재시작
```bash
# 프로세스 찾기
ps aux | grep uvicorn

# 종료
kill -9 <PID>

# 재시작
cd ~/MLOps_assignment/backend
source venv/bin/activate
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &
```

### 프론트엔드 재시작
```bash
# 프로세스 찾기
ps aux | grep node

# 종료
kill -9 <PID>

# 재시작
cd ~/MLOps_assignment/frontend
nohup npm start > frontend.log 2>&1 &
```

---

**작성일**: 2025-11-17
**버전**: 1.0.0
