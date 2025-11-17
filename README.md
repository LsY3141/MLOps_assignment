# 🎓 캠퍼스메이트 (CampusMate)

대학 행정 AI 챗봇 - RAG 기반 질의응답 시스템

---

## 🚀 빠른 시작 (EC2)

### 1. 코드 다운로드
```bash
git clone <YOUR_REPO_URL>
cd MLOps_assignment
```

### 2. 자동 설치 및 설정
```bash
./quick_start.sh
```

### 3. 백엔드 실행
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 4. 프론트엔드 실행 (새 터미널)
```bash
cd frontend
npm start
```

### 5. 접속
- 백엔드: `http://YOUR_EC2_IP:8000/docs`
- 프론트엔드: `http://YOUR_EC2_IP:3000`

**⚠️ EC2 보안 그룹에서 포트 8000, 3000 열어주세요!**

---

## 📦 기술 스택

### 백엔드
- **FastAPI** - Python 웹 프레임워크
- **PostgreSQL + pgvector** - 벡터 데이터베이스
- **AWS Bedrock** - Claude 3.5 Sonnet (LLM) + Titan Embeddings
- **S3** - PDF 문서 저장

### 프론트엔드
- **React** - UI 프레임워크
- **TailwindCSS** - 스타일링

---

## 🎯 주요 기능

1. **AI 챗봇** - 학생 질문에 대한 자동 답변
2. **RAG 시스템** - 업로드된 문서 기반 답변 생성
3. **문서 업로드** - PDF 파일 업로드 및 자동 벡터화
4. **담당 부서 안내** - 카테고리별 담당 부서 자동 연결

---

## 🔧 수동 설정 (quick_start.sh 없이)

### 백엔드 설정

```bash
cd backend

# 1. 가상환경 생성
python3 -m venv venv
source venv/bin/activate

# 2. 패키지 설치
pip install -r requirements.txt

# 3. .env 파일 생성
cat > .env << 'EOF'
AWS_REGION=us-west-1
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DATABASE
DB_HOST=your-rds-endpoint.rds.amazonaws.com
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=your-password
S3_BUCKET_NAME=your-bucket-name
S3_REGION=us-west-1
DEFAULT_SCHOOL_ID=1
EOF

# 4. 데이터베이스 초기화 (처음 실행 시에만)
python init_db.py

# 5. 샘플 데이터 입력 (선택사항)
python init_sample_data.py

# 6. 서버 실행
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 프론트엔드 설정

```bash
cd frontend

# 1. .env 파일 생성
echo "REACT_APP_API_URL=http://localhost:8000" > .env

# 2. 패키지 설치
npm install

# 3. 서버 실행
npm start
```

---

## 📂 프로젝트 구조

```
MLOps_assignment/
├── backend/
│   ├── app/
│   │   ├── routers/          # API 엔드포인트
│   │   ├── services/         # 비즈니스 로직
│   │   ├── database/         # 데이터베이스 모델
│   │   └── main.py           # FastAPI 앱
│   ├── requirements.txt
│   ├── init_db.py            # DB 테이블 생성
│   └── init_sample_data.py   # 샘플 데이터
│
├── frontend/
│   ├── src/
│   │   ├── components/       # React 컴포넌트
│   │   ├── services/         # API 호출
│   │   └── App.jsx
│   └── package.json
│
├── quick_start.sh            # 자동 설치 스크립트
└── README.md
```

---

## ❓ 문제 해결

### 백엔드가 시작되지 않아요
```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
```

### 데이터베이스 연결 오류
1. `.env` 파일의 DB 정보 확인
2. RDS 보안 그룹에서 EC2 접근 허용 확인

### 포트가 이미 사용 중이에요
```bash
# 프로세스 찾기
lsof -i :8000

# 종료
kill -9 <PID>
```

### 프론트엔드가 백엔드에 연결 안돼요
1. `frontend/.env`에서 `REACT_APP_API_URL` 확인
2. 백엔드 실행 여부 확인: `curl http://localhost:8000`
3. EC2 보안 그룹에서 포트 8000 오픈 확인

---

## 📞 지원

문제가 발생하면 다음을 확인해주세요:

1. **로그 확인**
   ```bash
   # 백엔드 로그
   tail -f backend/server.log

   # 프론트엔드 로그
   tail -f frontend/frontend.log
   ```

2. **프로세스 확인**
   ```bash
   ps aux | grep uvicorn
   ps aux | grep node
   ```

3. **데이터베이스 연결 테스트**
   ```bash
   cd backend
   source venv/bin/activate
   python -c "from app.database.database import engine; print('DB 연결 성공!')"
   ```

---

**작성일**: 2025-11-17
**버전**: 2.0.0
