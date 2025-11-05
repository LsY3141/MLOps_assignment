# 시스템 아키텍처

## 개요

캠퍼스메이트는 AWS 클라우드 기반의 마이크로서비스 아키텍처로 구성되어 있습니다.
RAG(검색 증강 생성) 기술을 핵심으로 하여, 대학생들에게 정확한 행정 정보를 제공합니다.

## 아키텍처 다이어그램

```
[사용자 (웹 브라우저)]
         ↓
[S3 정적 웹사이트 (React 앱)]
         ↓
[EC2 - FastAPI 백엔드]
    ↙    ↓    ↘
[RDS]  [Bedrock]  [S3]
         ↓
[사용자가 원하는 답변]

[자동화 (AWS Lambda + EventBridge)]
매일 오전 6시에 RSS 크롤링
    ↓
[S3에 저장 후 DB까지 업데이트]
```

## 주요 컴포넌트

### 1. Frontend (React)
- **호스팅**: AWS S3 정적 웹사이트
- **역할**: 사용자 인터페이스 제공
- **주요 기능**:
  - 챗봇 대화 인터페이스
  - 관리자 문서 업로드 페이지
  - 실시간 메시지 표시

### 2. Backend (FastAPI)
- **호스팅**: AWS EC2
- **역할**: API 서버 및 비즈니스 로직 처리
- **주요 API**:
  - `/api/chat/query`: 질의응답
  - `/api/admin/document`: 문서 관리
  - `/api/admin/rss`: RSS 피드 관리

### 3. Database (PostgreSQL + pgvector)
- **호스팅**: AWS RDS
- **역할**: 데이터 저장 및 벡터 검색
- **주요 테이블**:
  - `schools`: 학교 정보
  - `documents`: 문서 메타데이터
  - `document_chunks`: 문서 청크 및 벡터 임베딩
  - `default_contacts`: 카테고리별 담당 부서
  - `rss_feeds`: RSS 피드 정보

### 4. AI/ML (AWS Bedrock)
- **Claude 3.5 Sonnet**: 답변 생성, 의도 분석
- **Titan Embeddings**: 텍스트 벡터화 (1536차원)

### 5. 스토리지 (AWS S3)
- **용도**:
  - 프론트엔드 정적 파일 호스팅
  - 업로드된 문서 원본 저장
  - RSS 콘텐츠 백업

### 6. 자동화 (Lambda + EventBridge)
- **RSS Crawler Lambda**: 매일 오전 6시 자동 실행
- **EventBridge**: 크론 스케줄러 역할

## 데이터 흐름

### 1. 사용자 질문 처리
```
1. 사용자가 React 앱에서 질문 입력
2. FastAPI /api/chat/query 호출
3. Bedrock Titan으로 질문 벡터화
4. RDS pgvector에서 유사 문서 검색
5. Bedrock Claude로 답변 생성
6. 구조화된 답변 반환
```

### 2. 문서 업로드
```
1. 관리자가 PDF/DOCX 업로드
2. 원본 파일 → S3 저장
3. 텍스트 추출 및 청킹
4. Bedrock Titan으로 임베딩
5. RDS에 벡터 및 메타데이터 저장
```

### 3. RSS 자동 크롤링
```
1. EventBridge가 Lambda 트리거 (매일 06:00)
2. Lambda가 RDS에서 RSS 피드 목록 조회
3. feedparser로 신규 공지사항 파싱
4. 신규 항목 → S3 백업
5. EC2 API 호출하여 문서 처리
6. RDS에 벡터 저장
```

## 보안 고려사항

### 데이터 격리
- 모든 쿼리에 `school_id` 필터 적용
- 학교별 데이터 완전 분리

### 인증 및 권한
- 관리자 페이지 접근 제어 (향후 구현)
- API 키 기반 인증 (향후 구현)

### 데이터 암호화
- RDS 암호화 활성화
- S3 버킷 암호화 활성화

## 확장성

### 수평 확장
- EC2 Auto Scaling Group 구성 가능
- RDS Read Replica 추가 가능

### 멀티테넌트
- 하나의 시스템으로 여러 대학 지원
- 학교별 독립적 데이터 관리

## 모니터링

### CloudWatch
- Lambda 실행 로그
- EC2 리소스 사용률
- RDS 성능 메트릭

### 에러 추적
- FastAPI 에러 로깅
- Lambda 실패 알림

## 비용 최적화

- S3 Intelligent-Tiering 사용
- RDS 인스턴스 크기 최적화
- Lambda 메모리 최적 설정
- Bedrock On-Demand 요금제
