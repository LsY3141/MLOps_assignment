# API 명세서

## 베이스 URL
```
개발: http://localhost:8000
프로덕션: https://api.campusmate.com (예정)
```

## 인증
현재 버전에서는 인증이 구현되지 않았습니다. (향후 구현 예정)

---

## 챗봇 API

### 1. 질문 전송
사용자의 질문에 대한 AI 답변을 생성합니다.

**Endpoint**: `POST /api/chat/query`

**Request Body**:
```json
{
  "school_id": "demo_school",
  "query": "휴학 신청은 어떻게 하나요?",
  "session_id": "session_1234567890"
}
```

**Response** (200 OK):
```json
{
  "answer": "휴학 신청은 다음과 같이 진행됩니다...",
  "source_documents": [
    {
      "title": "2025학년도 휴학 안내",
      "content": "...",
      "department": "학사지원팀",
      "contact": "031-123-4567"
    }
  ],
  "metadata": {
    "department": "학사지원팀",
    "contact": "031-123-4567"
  },
  "response_type": "rag"
}
```

**Response Type**:
- `rag`: 문서 기반 답변
- `fallback`: 담당 부서 안내

---

### 2. 대화 이력 조회
특정 세션의 대화 이력을 조회합니다.

**Endpoint**: `GET /api/chat/history/{session_id}`

**Response** (200 OK):
```json
{
  "session_id": "session_1234567890",
  "messages": [
    {
      "id": "msg_1",
      "role": "user",
      "content": "휴학 신청 방법",
      "timestamp": "2025-01-15T10:30:00"
    },
    {
      "id": "msg_2",
      "role": "assistant",
      "content": "휴학 신청은...",
      "timestamp": "2025-01-15T10:30:05"
    }
  ]
}
```

---

### 3. 피드백 제출
사용자가 답변에 대한 피드백을 제출합니다.

**Endpoint**: `POST /api/chat/feedback`

**Request Body**:
```json
{
  "session_id": "session_1234567890",
  "message_id": "msg_2",
  "rating": 5,
  "comment": "정확한 답변 감사합니다!"
}
```

**Response** (200 OK):
```json
{
  "status": "success",
  "message": "피드백이 제출되었습니다."
}
```

---

## 관리자 API

### 1. 문서 업로드
PDF 또는 DOCX 파일을 업로드하고 챗봇 지식베이스에 추가합니다.

**Endpoint**: `POST /api/admin/document`

**Request** (multipart/form-data):
```
file: [파일]
title: "2025학년도 휴학 안내"
category: "학사"
department: "학사지원팀"
contact: "031-123-4567"
school_id: "demo_school"
```

**Response** (200 OK):
```json
{
  "document_id": "doc_abc123",
  "title": "2025학년도 휴학 안내",
  "category": "학사",
  "department": "학사지원팀",
  "contact": "031-123-4567",
  "upload_date": "2025-01-15T10:00:00",
  "status": "processing"
}
```

---

### 2. 문서 목록 조회
업로드된 문서 목록을 조회합니다.

**Endpoint**: `GET /api/admin/documents`

**Query Parameters**:
- `school_id` (필수): 학교 ID
- `category` (선택): 카테고리 필터
- `skip` (선택): 건너뛸 문서 수 (기본값: 0)
- `limit` (선택): 반환할 최대 문서 수 (기본값: 20)

**Response** (200 OK):
```json
[
  {
    "document_id": "doc_abc123",
    "title": "2025학년도 휴학 안내",
    "category": "학사",
    "department": "학사지원팀",
    "contact": "031-123-4567",
    "upload_date": "2025-01-15T10:00:00",
    "status": "active"
  }
]
```

---

### 3. 문서 삭제
특정 문서를 삭제합니다.

**Endpoint**: `DELETE /api/admin/document/{document_id}`

**Query Parameters**:
- `school_id` (필수): 학교 ID

**Response** (200 OK):
```json
{
  "status": "success",
  "message": "문서 doc_abc123가 삭제되었습니다."
}
```

---

### 4. RSS 피드 추가
자동 크롤링할 RSS 피드를 추가합니다.

**Endpoint**: `POST /api/admin/rss`

**Request** (multipart/form-data):
```
school_id: "demo_school"
feed_url: "https://example.com/rss"
category: "학사"
department: "학사지원팀"
contact: "031-123-4567"
```

**Response** (200 OK):
```json
{
  "status": "success",
  "message": "RSS 피드가 등록되었습니다.",
  "feed_url": "https://example.com/rss"
}
```

---

### 5. RSS 피드 목록 조회
등록된 RSS 피드 목록을 조회합니다.

**Endpoint**: `GET /api/admin/rss`

**Query Parameters**:
- `school_id` (필수): 학교 ID

**Response** (200 OK):
```json
[
  {
    "id": 1,
    "school_id": "demo_school",
    "feed_url": "https://example.com/rss",
    "category": "학사",
    "department": "학사지원팀",
    "contact": "031-123-4567",
    "is_active": true,
    "last_crawled_at": "2025-01-15T06:00:00"
  }
]
```

---

## 에러 응답

모든 API는 에러 발생 시 다음 형식으로 응답합니다:

**400 Bad Request**:
```json
{
  "detail": "필수 파라미터가 누락되었습니다."
}
```

**404 Not Found**:
```json
{
  "detail": "요청한 리소스를 찾을 수 없습니다."
}
```

**500 Internal Server Error**:
```json
{
  "detail": "서버 내부 오류가 발생했습니다."
}
```

---

## Swagger 문서

서버 실행 후 다음 URL에서 자동 생성된 API 문서를 확인할 수 있습니다:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
