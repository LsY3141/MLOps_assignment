# ✅ EC2 실행 체크리스트

## 🎯 목표
EC2에서 캠퍼스메이트를 성공적으로 실행하기

---

## 📝 사전 준비 체크리스트

### AWS 인프라
- [ ] EC2 인스턴스 생성 완료
- [ ] RDS PostgreSQL 생성 완료 (pgvector 확장 설치됨)
- [ ] S3 버킷 생성 완료 (`ysu-ml-a-13-s3`)
- [ ] EC2 보안 그룹: 포트 8000, 3000 오픈
- [ ] RDS 보안 그룹: EC2에서 접근 가능

### 코드 다운로드
- [ ] `git clone` 완료
- [ ] 프로젝트 디렉토리로 이동 완료

---

## 🚀 실행 단계 체크리스트

### 1단계: 빠른 설치 (권장)
```bash
cd ~/MLOps_assignment
./quick_start.sh
```

- [ ] 스크립트 실행 완료
- [ ] 오류 없이 완료됨

### 2단계: 백엔드 실행
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- [ ] 백엔드 서버 시작됨
- [ ] `http://localhost:8000` 접속 확인
- [ ] 로그에 오류 없음

### 3단계: 프론트엔드 실행 (새 터미널)
```bash
cd frontend
npm start
```

- [ ] 프론트엔드 서버 시작됨
- [ ] `http://localhost:3000` 접속 확인
- [ ] 콘솔에 오류 없음

### 4단계: 초기 데이터 입력
```bash
cd backend
source venv/bin/activate
python init_sample_data.py
```

- [ ] 학교 데이터 추가됨
- [ ] 담당 부서 데이터 추가됨
- [ ] 오류 없이 완료됨

---

## 🧪 테스트 체크리스트

### 백엔드 API 테스트
```bash
# 헬스 체크
curl http://localhost:8000
# 응답: {"status":"ok","message":"Welcome to the CampusMate API!"}

# API 문서
curl http://localhost:8000/docs
```

- [ ] 헬스 체크 성공
- [ ] API 문서 접근 가능

### 프론트엔드 테스트
브라우저에서 `http://YOUR_EC2_IP:3000` 접속

- [ ] 챗봇 화면 로드됨
- [ ] 환영 메시지 표시됨
- [ ] "📄 문서 업로드" 버튼 보임

### 챗봇 기능 테스트
- [ ] 질문 입력 가능
- [ ] 답변 수신 (Fallback 답변이라도 OK)
- [ ] 오류 없음

### 문서 업로드 테스트
- [ ] "📄 문서 업로드" 버튼 클릭
- [ ] 모달 열림
- [ ] PDF 선택 가능
- [ ] 업로드 성공 메시지

---

## 🔧 문제 해결 체크리스트

### 백엔드 오류

**증상: `ModuleNotFoundError`**
```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
```
- [ ] 해결됨

**증상: `Database connection failed`**
1. `.env` 파일의 DB 정보 확인
2. RDS 보안 그룹 확인
3. RDS 엔드포인트 확인
- [ ] 해결됨

**증상: `Port 8000 already in use`**
```bash
lsof -i :8000
kill -9 <PID>
```
- [ ] 해결됨

### 프론트엔드 오류

**증상: `Network Error` (백엔드 연결 실패)**
1. `frontend/.env` 파일 확인
2. 백엔드 실행 중인지 확인
3. EC2 보안 그룹 확인
- [ ] 해결됨

**증상: `npm install` 오류**
```bash
rm -rf node_modules package-lock.json
npm install
```
- [ ] 해결됨

### AWS 연결 오류

**증상: S3 접근 거부**
1. EC2 IAM Role 확인
2. S3 버킷 정책 확인
- [ ] 해결됨

**증상: Bedrock 접근 오류**
1. AWS 리전 확인 (us-west-1)
2. Bedrock 모델 액세스 확인
- [ ] 해결됨

---

## 🎉 최종 확인 체크리스트

### 기본 동작 확인
- [ ] 백엔드 실행 중 (`http://YOUR_EC2_IP:8000`)
- [ ] 프론트엔드 실행 중 (`http://YOUR_EC2_IP:3000`)
- [ ] 챗봇 질문/답변 가능
- [ ] 문서 업로드 가능

### 데이터 확인
```bash
# PostgreSQL 접속
psql -h database-1.cpyomug2w3oq.us-west-1.rds.amazonaws.com -U postgres -d postgres

# 데이터 확인
SELECT * FROM schools;
SELECT * FROM default_contacts;
SELECT COUNT(*) FROM document_chunks;
```

- [ ] 학교 데이터 존재
- [ ] 담당 부서 데이터 존재
- [ ] 문서/청크 데이터 확인

---

## 📊 성능 확인 (선택)

### 응답 시간
- [ ] 백엔드 API 응답 < 1초
- [ ] 챗봇 답변 생성 < 10초
- [ ] 문서 업로드 < 30초

### 리소스 사용량
```bash
# CPU/메모리 확인
top
htop  # 설치: sudo yum install htop -y

# 디스크 사용량
df -h

# 네트워크 확인
netstat -tulpn
```

- [ ] CPU 사용률 < 80%
- [ ] 메모리 여유 충분
- [ ] 디스크 여유 충분

---

## 🎊 완료!

모든 체크리스트를 통과했다면 성공입니다! 🎉

### 다음 단계
1. **Lambda 함수 배포** (S3 자동 벡터화)
2. **RSS 크롤러 설정** (자동 공지사항 수집)
3. **실제 문서 업로드** (학교 공식 문서)
4. **사용자 테스트** (동료/친구에게 공유)

### 유용한 명령어
```bash
# 백엔드 로그 확인
tail -f backend/server.log

# 프론트엔드 로그 확인
tail -f frontend/frontend.log

# 프로세스 확인
ps aux | grep uvicorn
ps aux | grep node

# 서버 재시작
cd backend && source venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000
cd frontend && npm start
```

---

**작성일**: 2025-11-17
**버전**: 1.0.0
