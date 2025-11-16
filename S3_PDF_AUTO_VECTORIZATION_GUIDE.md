# 📚 S3 PDF 자동 벡터화 시스템 구현 가이드

## 🎯 개요

이 문서는 **S3에 업로드된 PDF 파일을 자동으로 벡터화하는 시스템**의 구현 및 설정 방법을 안내합니다.

### 시스템 구조

```
프론트엔드 (React)
    ↓
    ↓ PDF 파일 선택 및 업로드
    ↓
백엔드 API (/api/documents/presigned-url)
    ↓
    ↓ S3 Presigned URL 발급
    ↓
S3 버킷 (ysu-ml-a-13-s3)
    ↓
    ↓ S3 이벤트 트리거 (ObjectCreated:Put)
    ↓
Lambda 함수 (s3_pdf_processor)
    ↓
    ↓ 1. PDF 다운로드
    ↓ 2. 텍스트 추출
    ↓ 3. 텍스트 청킹
    ↓ 4. Bedrock Titan 임베딩 생성
    ↓ 5. RDS에 저장
    ↓
RDS PostgreSQL (pgvector)
```

---

## 📋 목차

1. [S3 버킷 설정](#1-s3-버킷-설정)
2. [Lambda 함수 배포](#2-lambda-함수-배포)
3. [S3 이벤트 트리거 설정](#3-s3-이벤트-트리거-설정)
4. [백엔드 API 설정](#4-백엔드-api-설정)
5. [프론트엔드 설정](#5-프론트엔드-설정)
6. [기존 PDF 일괄 벡터화](#6-기존-pdf-일괄-벡터화)
7. [테스트 방법](#7-테스트-방법)
8. [문제 해결](#8-문제-해결)

---

## 1. S3 버킷 설정

### 1.1 S3 버킷 CORS 설정

프론트엔드에서 S3로 직접 업로드하려면 CORS를 설정해야 합니다.

**AWS Console → S3 → ysu-ml-a-13-s3 → Permissions → CORS**

```json
[
  {
    "AllowedHeaders": ["*"],
    "AllowedMethods": ["PUT", "POST", "GET"],
    "AllowedOrigins": [
      "http://localhost:3000",
      "http://54.153.88.46:3000"
    ],
    "ExposeHeaders": ["ETag"]
  }
]
```

### 1.2 S3 폴더 구조

Lambda가 경로에서 메타데이터를 추출하므로, 다음 구조를 권장합니다:

```
s3://ysu-ml-a-13-s3/
└── documents/
    ├── 1/                    # school_id
    │   ├── academic/         # category
    │   │   ├── 20250116_120000_학사규정.pdf
    │   │   └── 20250116_130000_수강신청안내.pdf
    │   ├── scholarship/
    │   │   └── 20250116_140000_장학금안내.pdf
    │   └── career/
    │       └── 20250116_150000_취업특강.pdf
    └── 2/                    # 다른 학교
        └── ...
```

---

## 2. Lambda 함수 배포

### 2.1 Lambda 함수 패키징

```bash
cd lambda/s3_pdf_processor

# 의존성 설치 (Lambda Layer용)
mkdir -p package
pip install -r requirements.txt -t package/

# Lambda 함수 코드 복사
cp lambda_function.py package/

# ZIP 파일 생성
cd package
zip -r ../s3_pdf_processor.zip .
cd ..
```

### 2.2 Lambda 함수 생성

**AWS Console → Lambda → Create function**

- **함수 이름**: `s3-pdf-vectorizer`
- **런타임**: Python 3.11
- **아키텍처**: x86_64
- **실행 역할**: 새 역할 생성 (기본)

### 2.3 함수 코드 업로드

```bash
# AWS CLI로 업로드
aws lambda update-function-code \
  --function-name s3-pdf-vectorizer \
  --zip-file fileb://s3_pdf_processor.zip \
  --region us-west-1
```

또는 AWS Console에서 ZIP 파일 업로드

### 2.4 환경 변수 설정

**Lambda → Configuration → Environment variables**

| 키 | 값 | 설명 |
|---|---|---|
| `DB_HOST` | `database-1.cpyomug2w3oq.us-west-1.rds.amazonaws.com` | RDS 호스트 |
| `DB_NAME` | `postgres` | 데이터베이스 이름 |
| `DB_USER` | `postgres` | DB 사용자 |
| `DB_PASSWORD` | `12345678aA` | DB 비밀번호 |
| `AWS_REGION` | `us-west-1` | AWS 리전 |
| `DEFAULT_SCHOOL_ID` | `1` | 기본 학교 ID |

### 2.5 Lambda 타임아웃 및 메모리 설정

**Lambda → Configuration → General configuration**

- **타임아웃**: 5분 (300초)
- **메모리**: 1024 MB (임베딩 생성에 필요)

### 2.6 Lambda 권한 추가

**Lambda → Configuration → Permissions → Execution role**

Lambda 실행 역할에 다음 정책 추가:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:GetObjectVersion"
      ],
      "Resource": "arn:aws:s3:::ysu-ml-a-13-s3/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel"
      ],
      "Resource": "arn:aws:bedrock:us-west-1::foundation-model/amazon.titan-embed-text-v1"
    }
  ]
}
```

### 2.7 VPC 설정 (RDS 접근용)

**Lambda → Configuration → VPC**

- RDS와 같은 VPC 선택
- Private 서브넷 선택
- RDS 보안 그룹 선택

---

## 3. S3 이벤트 트리거 설정

### 3.1 S3 이벤트 알림 추가

**S3 → ysu-ml-a-13-s3 → Properties → Event notifications → Create event notification**

#### 설정 값:

- **Event name**: `pdf-upload-trigger`
- **Prefix**: `documents/` (선택적)
- **Suffix**: `.pdf`
- **Event types**:
  - ✅ `s3:ObjectCreated:Put`
  - ✅ `s3:ObjectCreated:Post`
- **Destination**: Lambda function
- **Lambda function**: `s3-pdf-vectorizer`

### 3.2 Lambda 권한 추가 (자동)

S3 이벤트 알림을 설정하면 Lambda에 자동으로 S3 트리거 권한이 추가됩니다.

확인 방법:
```bash
aws lambda get-policy --function-name s3-pdf-vectorizer --region us-west-1
```

---

## 4. 백엔드 API 설정

### 4.1 환경 변수 확인

`backend/.env` 파일에 S3 설정이 있는지 확인:

```env
S3_BUCKET_NAME=ysu-ml-a-13-s3
AWS_REGION=us-west-1
```

### 4.2 Presigned URL API 확인

`backend/app/routers/admin.py`에 다음 엔드포인트가 있는지 확인:

```python
@router.post("/documents/presigned-url")
async def generate_presigned_url(request: PresignedURLRequest):
    # ...
```

### 4.3 백엔드 서버 재시작

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 5. 프론트엔드 설정

### 5.1 환경 변수 설정

`frontend/.env` 파일 생성:

```env
REACT_APP_API_URL=http://54.153.88.46:8000
```

### 5.2 DocumentUpload 컴포넌트 사용

이미 `App.jsx`에 라우팅이 추가되어 있습니다:

```jsx
<Route path="/upload" element={<DocumentUpload />} />
```

### 5.3 프론트엔드 실행

```bash
cd frontend
npm install
npm start
```

### 5.4 접속

브라우저에서 `http://localhost:3000/upload` 접속

---

## 6. 기존 PDF 일괄 벡터화

S3에 이미 업로드된 PDF들을 한 번에 벡터화하려면:

### 6.1 배치 스크립트 실행

```bash
cd backend

# 가상환경 활성화
source venv/bin/activate

# 기존 PDF 벡터화 (Dry Run - 테스트)
python batch_vectorize_s3_pdfs.py \
  --school-id 1 \
  --category academic \
  --prefix documents/1/academic/ \
  --dry-run

# 실제 벡터화 실행
python batch_vectorize_s3_pdfs.py \
  --school-id 1 \
  --category academic \
  --prefix documents/1/academic/
```

### 6.2 옵션 설명

| 옵션 | 설명 | 필수 |
|------|------|------|
| `--school-id` | 학교 ID | ✅ |
| `--category` | 문서 카테고리 (academic, scholarship 등) | ❌ (기본: general) |
| `--department` | 담당 부서 | ❌ |
| `--prefix` | S3 폴더 경로 | ❌ (기본: documents/) |
| `--dry-run` | 테스트 모드 (실제 저장 안함) | ❌ |

### 6.3 배치 작업 예시

```bash
# 학사 관련 문서 모두 처리
python batch_vectorize_s3_pdfs.py \
  --school-id 1 \
  --category academic \
  --department "학사지원팀" \
  --prefix documents/1/academic/

# 장학금 관련 문서 모두 처리
python batch_vectorize_s3_pdfs.py \
  --school-id 1 \
  --category scholarship \
  --department "학생지원팀" \
  --prefix documents/1/scholarship/
```

---

## 7. 테스트 방법

### 7.1 프론트엔드에서 업로드 테스트

1. `http://localhost:3000/upload` 접속
2. PDF 파일 선택
3. 카테고리 선택 (예: 학사)
4. 담당 부서 입력 (예: 학사지원팀)
5. "📤 업로드 및 벡터화" 버튼 클릭

### 7.2 업로드 확인

**S3 콘솔에서 확인:**
```
S3 → ysu-ml-a-13-s3 → documents/1/academic/
```

**Lambda 로그 확인:**
```bash
aws logs tail /aws/lambda/s3-pdf-vectorizer --follow --region us-west-1
```

### 7.3 데이터베이스 확인

```sql
-- 새로 추가된 문서 확인
SELECT * FROM documents ORDER BY created_at DESC LIMIT 5;

-- 청크 수 확인
SELECT document_id, COUNT(*) as chunk_count
FROM document_chunks
GROUP BY document_id
ORDER BY document_id DESC
LIMIT 5;
```

### 7.4 챗봇에서 테스트

1. `http://localhost:3000/` (챗봇 페이지) 접속
2. 업로드한 PDF 내용과 관련된 질문 입력
3. 답변에 업로드한 문서가 출처로 표시되는지 확인

---

## 8. 문제 해결

### 8.1 Lambda가 실행되지 않음

**원인**: S3 이벤트 트리거 설정 오류

**해결**:
```bash
# S3 이벤트 알림 확인
aws s3api get-bucket-notification-configuration \
  --bucket ysu-ml-a-13-s3 \
  --region us-west-1

# Lambda 권한 확인
aws lambda get-policy \
  --function-name s3-pdf-vectorizer \
  --region us-west-1
```

### 8.2 임베딩 생성 실패

**원인**: Bedrock 모델 액세스 권한 없음

**해결**:
1. AWS Console → Bedrock → Model access
2. `amazon.titan-embed-text-v1` 모델 활성화
3. Lambda 실행 역할에 `bedrock:InvokeModel` 권한 추가

### 8.3 RDS 연결 실패

**원인**: Lambda가 VPC 내부에 없음

**해결**:
1. Lambda → Configuration → VPC
2. RDS와 같은 VPC, 서브넷, 보안 그룹 선택
3. RDS 보안 그룹에서 Lambda 보안 그룹 허용

### 8.4 프론트엔드 업로드 CORS 오류

**원인**: S3 CORS 설정 누락

**해결**:
- S3 버킷 CORS 설정 확인 (1.1 참조)
- 프론트엔드 도메인이 AllowedOrigins에 포함되었는지 확인

### 8.5 Presigned URL 만료

**원인**: 15분 내에 업로드하지 않음

**해결**:
- 파일을 다시 선택하고 즉시 업로드
- 필요시 `admin.py`에서 `ExpiresIn` 값 조정

---

## 🎉 완료!

이제 다음과 같은 기능이 작동합니다:

✅ **프론트엔드에서 PDF 업로드**
- `/upload` 페이지에서 파일 선택 및 업로드

✅ **S3 자동 벡터화**
- S3에 PDF 업로드 시 Lambda가 자동 실행
- 텍스트 추출 → 청킹 → 임베딩 → DB 저장

✅ **기존 PDF 일괄 처리**
- 배치 스크립트로 S3의 기존 PDF들 한 번에 벡터화

✅ **챗봇 검색**
- 업로드된 PDF 내용이 즉시 챗봇 검색에 반영

---

## 📚 추가 자료

- [AWS S3 이벤트 알림 공식 문서](https://docs.aws.amazon.com/AmazonS3/latest/userguide/NotificationHowTo.html)
- [AWS Lambda Python 공식 문서](https://docs.aws.amazon.com/lambda/latest/dg/lambda-python.html)
- [AWS Bedrock Titan Embeddings](https://docs.aws.amazon.com/bedrock/latest/userguide/titan-embedding-models.html)
- [pgvector GitHub](https://github.com/pgvector/pgvector)

---

**작성일**: 2025-11-16
**버전**: 1.0.0
