# 📁 캠퍼스메이트 프로젝트 전체 폴더 구조

```
campusmate-project/
│
├── 📄 README.md                          # 프로젝트 개요 및 소개
├── 📄 GETTING_STARTED.md                 # 프로젝트 시작 가이드
│
├── 📂 backend/                           # FastAPI 백엔드
│   ├── 📄 README.md                      # 백엔드 설치 및 실행 가이드
│   ├── 📄 requirements.txt               # Python 패키지 의존성
│   ├── 📄 .env.example                   # 환경 변수 예시 파일
│   │
│   └── 📂 app/                           # 애플리케이션 코드
│       ├── 📄 __init__.py
│       ├── 📄 main.py                    # FastAPI 진입점
│       │
│       ├── 📂 routers/                   # API 라우터
│       │   ├── 📄 __init__.py
│       │   ├── 📄 chat.py                # 챗봇 API (질의응답, 이력, 피드백)
│       │   └── 📄 admin.py               # 관리자 API (문서 업로드, RSS 관리)
│       │
│       ├── 📂 services/                  # 비즈니스 로직
│       │   ├── 📄 __init__.py
│       │   ├── 📄 rag_service.py         # RAG 파이프라인 (검색 증강 생성)
│       │   ├── 📄 llm_service.py         # AWS Bedrock 연동 (Claude, Titan)
│       │   └── 📄 document_service.py    # 문서 처리 (PDF/DOCX 추출, 청킹)
│       │
│       ├── 📂 database/                  # 데이터베이스
│       │   ├── 📄 __init__.py
│       │   └── 📄 models.py              # SQLAlchemy 모델 (pgvector 포함)
│       │
│       └── 📂 utils/                     # 유틸리티
│           ├── 📄 __init__.py
│           └── 📄 config.py              # 환경 설정 관리
│
├── 📂 frontend/                          # React 프론트엔드
│   ├── 📄 README.md                      # 프론트엔드 설치 및 실행 가이드
│   ├── 📄 package.json                   # NPM 패키지 의존성
│   │
│   └── 📂 src/                           # 소스 코드
│       ├── 📄 App.jsx                    # 메인 앱 컴포넌트 (라우팅)
│       │
│       ├── 📂 components/                # UI 컴포넌트
│       │   ├── 📄 ChatInterface.jsx      # 챗봇 대화 인터페이스
│       │   ├── 📄 MessageBubble.jsx      # 메시지 버블 컴포넌트
│       │   └── 📄 AdminDashboard.jsx     # 관리자 대시보드
│       │
│       └── 📂 services/                  # API 통신
│           └── 📄 api.js                 # Axios API 클라이언트
│
├── 📂 lambda/                            # AWS Lambda 함수
│   └── 📂 rss_crawler/                   # RSS 자동 크롤러
│       └── 📄 lambda_function.py         # RSS 크롤링 Lambda 함수
│
└── 📂 docs/                              # 프로젝트 문서
    ├── 📄 architecture.md                # 시스템 아키텍처 설계
    ├── 📄 api_specification.md           # REST API 명세서
    └── 📄 database_erd.md                # 데이터베이스 ERD 및 스키마
```

## 📊 파일 통계

### 총 개수
- **전체 파일**: 26개
- **Python 파일**: 10개
- **JavaScript/JSX 파일**: 5개
- **문서 파일**: 8개
- **설정 파일**: 3개

### 디렉토리별 파일 수
- `backend/`: 12개
- `frontend/`: 6개
- `lambda/`: 1개
- `docs/`: 3개
- 루트: 2개

## 🔑 주요 파일 설명

### 백엔드 핵심 파일

| 파일명 | 설명 | 상태 |
|--------|------|------|
| `main.py` | FastAPI 앱 진입점, CORS 설정 | ✅ 완료 |
| `routers/chat.py` | 질의응답, 대화 이력, 피드백 API | ✅ 스켈레톤 |
| `routers/admin.py` | 문서 업로드, RSS 관리 API | ✅ 스켈레톤 |
| `services/rag_service.py` | RAG 파이프라인, 벡터 검색 | ⏳ TODO 있음 |
| `services/llm_service.py` | Bedrock Claude/Titan 연동 | ⏳ TODO 있음 |
| `services/document_service.py` | PDF/DOCX 처리, 청킹 | ⏳ TODO 있음 |
| `database/models.py` | 8개 테이블 모델 정의 | ✅ 완료 |
| `utils/config.py` | 환경 변수 관리 | ✅ 완료 |

### 프론트엔드 핵심 파일

| 파일명 | 설명 | 상태 |
|--------|------|------|
| `App.jsx` | 라우팅 설정 (/, /admin) | ✅ 완료 |
| `components/ChatInterface.jsx` | 챗봇 UI, 메시지 전송 | ✅ 완료 |
| `components/MessageBubble.jsx` | 메시지 표시, 메타데이터 | ✅ 완료 |
| `components/AdminDashboard.jsx` | 문서 업로드 폼 | ✅ 완료 |
| `services/api.js` | Axios API 클라이언트 | ✅ 완료 |

### Lambda 함수

| 파일명 | 설명 | 상태 |
|--------|------|------|
| `lambda_function.py` | RSS 자동 크롤링 (매일 06:00) | ✅ 완료 |

### 문서

| 파일명 | 설명 | 페이지 수 |
|--------|------|-----------|
| `architecture.md` | 시스템 아키텍처, AWS 구성 | ~100줄 |
| `api_specification.md` | REST API 명세 | ~250줄 |
| `database_erd.md` | DB 스키마, ERD, 쿼리 예시 | ~350줄 |

## 🎯 구현 상태

### ✅ 완료된 것 (100%)
- [x] 프로젝트 구조 전체
- [x] 백엔드 API 라우터 스켈레톤
- [x] 프론트엔드 UI 컴포넌트
- [x] 데이터베이스 모델 정의
- [x] Lambda 함수
- [x] 전체 문서화

### ⏳ 구현 필요 (TODO 표시됨)
- [ ] AWS Bedrock 실제 API 호출
- [ ] pgvector 검색 쿼리
- [ ] S3 업로드 로직
- [ ] 문서 처리 파이프라인
- [ ] 데이터베이스 마이그레이션

## 📥 다운로드

전체 프로젝트는 다음 링크에서 다운로드할 수 있습니다:

[📦 campusmate-project 전체 다운로드](computer:///mnt/user-data/outputs/campusmate-project)

## 🚀 다음 단계

1. 프로젝트 폴더를 로컬에 다운로드
2. `GETTING_STARTED.md` 파일 참고하여 환경 설정
3. 백엔드 → 프론트엔드 순서로 로컬 실행 테스트
4. TODO 부분부터 구현 시작

---

**생성 일시**: 2025-11-04  
**프로젝트명**: 캠퍼스메이트 (CampusMate)  
**버전**: 1.0.0
