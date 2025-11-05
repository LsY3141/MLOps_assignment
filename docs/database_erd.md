# 데이터베이스 ERD

## 개요
캠퍼스메이트는 PostgreSQL 15+ (pgvector 확장 포함)을 사용합니다.
멀티테넌트 구조로 설계되어 여러 대학의 데이터를 독립적으로 관리합니다.

## ERD 다이어그램

```
┌─────────────────┐
│    schools      │
├─────────────────┤
│ id (PK)         │
│ name            │
│ domain          │
│ created_at      │
│ updated_at      │
└────────┬────────┘
         │
         │ 1:N
         │
    ┌────┴──────────────────────┬─────────────────────┬─────────────────────┐
    │                           │                     │                     │
┌───▼──────────────┐   ┌────────▼────────────┐  ┌───▼──────────────┐  ┌──▼──────────────┐
│   documents      │   │ default_contacts    │  │   rss_feeds      │  │ chat_sessions   │
├──────────────────┤   ├─────────────────────┤  ├──────────────────┤  ├─────────────────┤
│ id (PK)          │   │ id (PK)             │  │ id (PK)          │  │ id (PK)         │
│ school_id (FK)   │   │ school_id (FK)      │  │ school_id (FK)   │  │ school_id (FK)  │
│ title            │   │ category            │  │ feed_url         │  │ user_id         │
│ category         │   │ department          │  │ category         │  │ created_at      │
│ department       │   │ contact_person      │  │ department       │  │ last_activity   │
│ contact          │   │ phone               │  │ contact          │  └────────┬────────┘
│ source_type      │   │ email               │  │ is_active        │           │
│ source_url       │   │ location            │  │ last_crawled_at  │           │ 1:N
│ created_at       │   │ created_at          │  │ created_at       │           │
│ updated_at       │   │ updated_at          │  │ updated_at       │      ┌────▼─────────────┐
└────────┬─────────┘   └─────────────────────┘  └──────────────────┘      │ chat_messages    │
         │                                                                 ├──────────────────┤
         │ 1:N                                                             │ id (PK)          │
         │                                                                 │ session_id (FK)  │
    ┌────▼──────────────────┐                                             │ school_id (FK)   │
    │  document_chunks      │                                             │ role             │
    ├───────────────────────┤                                             │ content          │
    │ id (PK)               │                                             │ response_type    │
    │ document_id (FK)      │                                             │ source_documents │
    │ school_id (FK)        │                                             │ rating           │
    │ chunk_index           │                                             │ feedback_comment │
    │ content               │                                             │ created_at       │
    │ embedding (vector)    │                                             └──────────────────┘
    │ created_at            │
    └───────────────────────┘
```

## 테이블 상세

### 1. schools (학교 정보)
학교의 기본 정보를 저장합니다.

| 컬럼명 | 타입 | 제약조건 | 설명 |
|-------|------|---------|------|
| id | VARCHAR(50) | PK | 학교 고유 ID |
| name | VARCHAR(200) | NOT NULL | 학교명 |
| domain | VARCHAR(100) | UNIQUE | 학교 도메인 |
| created_at | TIMESTAMP | DEFAULT now() | 생성일시 |
| updated_at | TIMESTAMP | DEFAULT now() | 수정일시 |

### 2. documents (문서 메타데이터)
업로드된 문서의 메타정보를 저장합니다.

| 컬럼명 | 타입 | 제약조건 | 설명 |
|-------|------|---------|------|
| id | VARCHAR(50) | PK | 문서 고유 ID |
| school_id | VARCHAR(50) | FK, INDEX | 학교 ID |
| title | VARCHAR(500) | NOT NULL | 문서 제목 |
| category | VARCHAR(50) | NOT NULL, INDEX | 카테고리 |
| department | VARCHAR(100) | NOT NULL | 담당 부서 |
| contact | VARCHAR(100) | | 연락처 |
| source_type | VARCHAR(20) | NOT NULL | 'upload' 또는 'rss' |
| source_url | VARCHAR(500) | | RSS 링크 또는 S3 키 |
| created_at | TIMESTAMP | DEFAULT now() | 생성일시 |
| updated_at | TIMESTAMP | DEFAULT now() | 수정일시 |

### 3. document_chunks (문서 청크 및 벡터)
분할된 문서 조각과 벡터 임베딩을 저장합니다.

| 컬럼명 | 타입 | 제약조건 | 설명 |
|-------|------|---------|------|
| id | INTEGER | PK, AUTO_INCREMENT | 청크 고유 ID |
| document_id | VARCHAR(50) | FK, INDEX | 문서 ID |
| school_id | VARCHAR(50) | FK, INDEX | 학교 ID |
| chunk_index | INTEGER | NOT NULL | 청크 순서 |
| content | TEXT | NOT NULL | 청크 내용 |
| embedding | VECTOR(1536) | NOT NULL | 임베딩 벡터 |
| created_at | TIMESTAMP | DEFAULT now() | 생성일시 |

**인덱스**:
```sql
CREATE INDEX idx_chunks_embedding ON document_chunks 
USING ivfflat (embedding vector_cosine_ops);
```

### 4. default_contacts (기본 담당 부서)
카테고리별 기본 담당 부서 정보를 저장합니다 (Fallback용).

| 컬럼명 | 타입 | 제약조건 | 설명 |
|-------|------|---------|------|
| id | INTEGER | PK, AUTO_INCREMENT | 고유 ID |
| school_id | VARCHAR(50) | FK, INDEX | 학교 ID |
| category | VARCHAR(50) | NOT NULL, INDEX | 카테고리 |
| department | VARCHAR(100) | NOT NULL | 부서명 |
| contact_person | VARCHAR(100) | | 담당자 이름 |
| phone | VARCHAR(50) | | 전화번호 |
| email | VARCHAR(100) | | 이메일 |
| location | VARCHAR(200) | | 위치 |
| created_at | TIMESTAMP | DEFAULT now() | 생성일시 |
| updated_at | TIMESTAMP | DEFAULT now() | 수정일시 |

### 5. rss_feeds (RSS 피드)
자동 크롤링할 RSS 피드 목록을 저장합니다.

| 컬럼명 | 타입 | 제약조건 | 설명 |
|-------|------|---------|------|
| id | INTEGER | PK, AUTO_INCREMENT | 고유 ID |
| school_id | VARCHAR(50) | FK, INDEX | 학교 ID |
| feed_url | VARCHAR(500) | NOT NULL | RSS 피드 URL |
| category | VARCHAR(50) | NOT NULL | 카테고리 |
| department | VARCHAR(100) | NOT NULL | 담당 부서 |
| contact | VARCHAR(100) | | 연락처 |
| is_active | INTEGER | DEFAULT 1 | 활성화 상태 |
| last_crawled_at | TIMESTAMP | | 마지막 크롤링 시간 |
| created_at | TIMESTAMP | DEFAULT now() | 생성일시 |
| updated_at | TIMESTAMP | DEFAULT now() | 수정일시 |

### 6. chat_sessions (채팅 세션)
사용자의 채팅 세션 정보를 저장합니다.

| 컬럼명 | 타입 | 제약조건 | 설명 |
|-------|------|---------|------|
| id | VARCHAR(50) | PK | 세션 고유 ID |
| school_id | VARCHAR(50) | FK, INDEX | 학교 ID |
| user_id | VARCHAR(50) | | 사용자 ID (선택) |
| created_at | TIMESTAMP | DEFAULT now() | 생성일시 |
| last_activity_at | TIMESTAMP | DEFAULT now() | 마지막 활동 시간 |

### 7. chat_messages (채팅 메시지)
채팅 메시지 로그 및 피드백을 저장합니다.

| 컬럼명 | 타입 | 제약조건 | 설명 |
|-------|------|---------|------|
| id | INTEGER | PK, AUTO_INCREMENT | 메시지 고유 ID |
| session_id | VARCHAR(50) | FK, INDEX | 세션 ID |
| school_id | VARCHAR(50) | FK, INDEX | 학교 ID |
| role | VARCHAR(20) | NOT NULL | 'user' 또는 'assistant' |
| content | TEXT | NOT NULL | 메시지 내용 |
| response_type | VARCHAR(20) | | 'rag' 또는 'fallback' |
| source_documents | VARCHAR[] | | 참조 문서 ID 배열 |
| rating | INTEGER | | 사용자 평점 (1-5) |
| feedback_comment | TEXT | | 피드백 코멘트 |
| created_at | TIMESTAMP | DEFAULT now() | 생성일시 |

## 주요 쿼리 예시

### 1. 벡터 유사도 검색
```sql
SELECT 
    dc.id,
    dc.content,
    d.title,
    d.department,
    d.contact,
    1 - (dc.embedding <=> :query_embedding) AS similarity
FROM document_chunks dc
JOIN documents d ON dc.document_id = d.id
WHERE dc.school_id = :school_id
ORDER BY dc.embedding <=> :query_embedding
LIMIT 3;
```

### 2. 카테고리별 기본 담당 부서 조회
```sql
SELECT 
    department,
    contact_person,
    phone,
    location
FROM default_contacts
WHERE school_id = :school_id
  AND category = :category
LIMIT 1;
```

### 3. 활성 RSS 피드 목록
```sql
SELECT 
    id,
    school_id,
    feed_url,
    category,
    department,
    contact
FROM rss_feeds
WHERE is_active = 1
ORDER BY school_id, category;
```

## 초기 데이터 설정

### 학교 등록
```sql
INSERT INTO schools (id, name, domain)
VALUES ('demo_school', '데모대학교', 'demo.ac.kr');
```

### 기본 담당 부서 등록
```sql
INSERT INTO default_contacts (school_id, category, department, phone, location)
VALUES 
    ('demo_school', '학사', '학사지원팀', '031-123-4567', '본관 2층'),
    ('demo_school', '장학', '장학복지팀', '031-123-5678', '본관 3층'),
    ('demo_school', '시설', '시설관리팀', '031-123-6789', '별관 1층');
```

## pgvector 설정

### 확장 설치
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### 인덱스 생성
```sql
-- IVFFlat 인덱스 (빠른 검색용)
CREATE INDEX idx_chunks_embedding ON document_chunks 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

## 데이터 격리 (멀티테넌트)

모든 쿼리는 반드시 `school_id`로 필터링하여 학교 간 데이터가 섞이지 않도록 합니다.

```sql
-- 올바른 쿼리 (school_id 필터링)
SELECT * FROM documents WHERE school_id = :school_id;

-- 잘못된 쿼리 (school_id 없음)
SELECT * FROM documents; -- ❌ 절대 사용 금지
```
