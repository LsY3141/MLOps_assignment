# 🎓 캠퍼스메이트 (CampusMate)

> RAG 기반 대학 행정 AI 챗봇 서비스

## 📋 프로젝트 개요

캠퍼스메이트는 대학생들이 학사 행정 정보를 쉽고 빠르게 찾을 수 있도록 돕는 AI 챗봇 서비스입니다.
RAG(검색 증강 생성) 기술을 활용하여 학교의 최신 공식 문서를 기반으로 정확한 답변을 제공합니다.

### 주요 기능
- ✅ 24/7 자연어 질의응답 (RAG 기반)
- ✅ 정보 부재 시 담당부서 자동 안내 (Fallback)
- ✅ RSS 자동 크롤링 및 최신 정보 업데이트
- ✅ 관리자 문서 업로드 및 관리
- ✅ 멀티테넌트 지원 (학교별 데이터 격리)

### 기술 스택
- **Frontend**: React, JavaScript, Tailwind CSS
- **Backend**: FastAPI, Python 3.11
- **Database**: PostgreSQL (pgvector)
- **Infrastructure**: AWS (EC2, S3, RDS, Lambda, EventBridge, Bedrock)
- **AI/ML**: AWS Bedrock (Claude 3.5 Sonnet, Titan Embeddings)

## 🗂️ 프로젝트 구조

```
campusmate-project/
├── frontend/              # React 프론트엔드
│   ├── src/
│   │   ├── components/   # UI 컴포넌트
│   │   ├── services/     # API 호출 로직
│   │   └── App.jsx
│   ├── package.json
│   └── README.md
│
├── backend/              # FastAPI 백엔드
│   ├── app/
│   │   ├── main.py      # FastAPI 진입점
│   │   ├── routers/     # API 라우터
│   │   ├── services/    # 비즈니스 로직
│   │   ├── database/    # DB 모델
│   │   └── utils/       # 유틸리티
│   ├── requirements.txt
│   └── README.md
│
├── lambda/              # AWS Lambda 함수
│   └── rss_crawler/    # RSS 크롤링 함수
│
├── docs/               # 문서
│   ├── architecture.md
│   ├── api_specification.md
│   └── database_erd.md
│
└── README.md          # 이 파일
```

## 🚀 빠른 시작

### 사전 요구사항
- Python 3.11+
- Node.js 18+
- AWS 계정 (Bedrock, RDS, EC2 등)
- PostgreSQL 15+ (pgvector 확장)

### 백엔드 설치 및 실행
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 프론트엔드 설치 및 실행
```bash
cd frontend
npm install
npm start
```

## 📊 시스템 아키텍처

상세한 아키텍처는 [docs/architecture.md](docs/architecture.md)를 참고하세요.

## 🔧 환경 변수 설정

백엔드 `.env` 파일 예시:
```
AWS_REGION=ap-northeast-2
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
DATABASE_URL=postgresql://user:pass@host:5432/dbname
```

## 📝 API 문서

API 명세는 [docs/api_specification.md](docs/api_specification.md)를 참고하세요.

서버 실행 후 자동 생성되는 Swagger 문서: `http://localhost:8000/docs`

## 🧪 테스트

```bash
# 백엔드 테스트
cd backend
pytest

# 프론트엔드 테스트
cd frontend
npm test
```

## 📦 배포

배포 가이드는 [docs/deployment.md](docs/deployment.md)를 참고하세요.

## 🤝 기여

이슈 및 PR은 언제나 환영합니다!

## 📄 라이선스

MIT License

## 📞 문의

프로젝트 관련 문의사항이 있으시면 이슈를 등록해주세요.
