# 🚀 캠퍼스메이트 프로젝트 시작 가이드

축하합니다! 프로젝트 구조가 모두 생성되었습니다.

## 📦 생성된 내용

### ✅ 백엔드 (FastAPI)
- ✓ 프로젝트 구조 완성
- ✓ API 라우터 (chat, admin)
- ✓ 서비스 로직 (RAG, LLM, Document)
- ✓ 데이터베이스 모델 (SQLAlchemy + pgvector)
- ✓ 설정 파일 및 환경 변수

### ✅ 프론트엔드 (React)
- ✓ 컴포넌트 (ChatInterface, MessageBubble, AdminDashboard)
- ✓ API 통신 서비스
- ✓ 라우팅 설정
- ✓ Tailwind CSS 스타일링

### ✅ Lambda 함수
- ✓ RSS 자동 크롤링 함수

### ✅ 문서
- ✓ 시스템 아키텍처
- ✓ API 명세서
- ✓ 데이터베이스 ERD
- ✓ README 파일들

## 🎯 다음 단계

### 1단계: 백엔드 설정 및 실행

```bash
cd backend

# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 패키지 설치
pip install -r requirements.txt

# 환경 변수 설정
cp .env.example .env
# .env 파일을 열어서 실제 값으로 수정하세요

# 서버 실행
uvicorn app.main:app --reload
```

### 2단계: 프론트엔드 설정 및 실행

```bash
cd frontend

# 패키지 설치
npm install

# 환경 변수 설정
echo "REACT_APP_API_URL=http://localhost:8000" > .env

# 개발 서버 실행
npm start
```

### 3단계: 데이터베이스 설정

PostgreSQL에 pgvector 확장을 설치하고 데이터베이스를 생성합니다.

```sql
CREATE DATABASE campusmate;
\c campusmate
CREATE EXTENSION vector;

-- 테이블 생성 (models.py 기반)
-- TODO: Alembic 마이그레이션 스크립트 작성 필요
```

### 4단계: AWS 서비스 설정

#### RDS (PostgreSQL)
1. RDS 인스턴스 생성 (PostgreSQL 15+)
2. pgvector 확장 설치
3. 보안 그룹 설정 (EC2에서 접근 가능하도록)

#### S3
1. 버킷 생성: `campusmate-documents`
2. CORS 설정
3. 정적 웹사이트 호스팅 활성화 (프론트엔드용)

#### Bedrock
1. AWS 콘솔에서 Bedrock 활성화
2. Claude 3.5 Sonnet 모델 액세스 요청
3. Titan Embeddings 모델 액세스 요청

#### EC2
1. Ubuntu 22.04 인스턴스 생성
2. Python 3.11 설치
3. 백엔드 코드 배포
4. nginx 리버스 프록시 설정

#### Lambda + EventBridge
1. Lambda 함수 생성
2. `lambda/rss_crawler/lambda_function.py` 코드 배포
3. 환경 변수 설정 (DB 정보, API 엔드포인트)
4. EventBridge 규칙 생성 (cron: 0 6 * * ? *)

## 🔧 현재 상태 및 TODO

### ✅ 완료된 것
- [x] 프로젝트 구조 생성
- [x] 백엔드 API 스켈레톤 코드
- [x] 프론트엔드 UI 컴포넌트
- [x] Lambda 함수
- [x] 문서 작성

### ⏳ 구현 필요 (TODO로 표시됨)
- [ ] AWS Bedrock API 실제 연동
- [ ] pgvector 검색 쿼리 구현
- [ ] 문서 처리 파이프라인 완성
- [ ] S3 업로드 로직 구현
- [ ] 데이터베이스 마이그레이션 스크립트
- [ ] 인증/권한 시스템
- [ ] 테스트 코드 작성
- [ ] Docker 설정
- [ ] CI/CD 파이프라인

## 📝 개발 순서 추천

1. **로컬 환경 구축**
   - PostgreSQL + pgvector 설치
   - 백엔드 실행
   - 프론트엔드 실행

2. **AWS Bedrock 연동**
   - `llm_service.py`의 TODO 부분 구현
   - 임베딩 및 답변 생성 테스트

3. **RAG 파이프라인 구현**
   - `rag_service.py`의 벡터 검색 구현
   - 문서 청킹 및 임베딩

4. **문서 업로드 기능 완성**
   - S3 업로드
   - 텍스트 추출
   - DB 저장

5. **RSS 크롤링 테스트**
   - Lambda 함수 로컬 테스트
   - 실제 RSS 피드 연동

6. **통합 테스트**
   - 전체 플로우 테스트
   - 버그 수정

7. **AWS 배포**
   - EC2 배포
   - S3 정적 호스팅
   - Lambda 배포

## 💡 유용한 명령어

### 백엔드 개발
```bash
# 코드 포맷팅
black app/

# 린터 실행
flake8 app/

# 타입 체크
mypy app/

# 테스트
pytest
```

### 프론트엔드 개발
```bash
# 프로덕션 빌드
npm run build

# 테스트
npm test
```

## 📚 참고 문서

- [FastAPI 공식 문서](https://fastapi.tiangolo.com/)
- [React 공식 문서](https://react.dev/)
- [AWS Bedrock 문서](https://docs.aws.amazon.com/bedrock/)
- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [LangChain 문서](https://python.langchain.com/)

## 🆘 도움이 필요하면

1. `docs/` 디렉토리의 문서들 참고
2. 각 디렉토리의 README.md 확인
3. API 문서: http://localhost:8000/docs

## 🎉 프로젝트 성공을 기원합니다!

계획서대로 체계적으로 구현하시면 멋진 AI 챗봇 서비스가 완성될 것입니다.
화이팅! 💪
