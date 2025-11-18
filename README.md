🎯 멀티 스쿨 챗봇 시스템 개발 현황 보고서
📊 프로젝트 개요 연성대학교와 연세대학교를 위한 완전 분리형 AI 챗봇 시스템을 구축 중입니다.
🏗️ 시스템 아키텍처
인프라
* DB: PostgreSQL (a-13-rds.cpyomug2w3oq.us-west-1.rds.amazonaws.com)
* S3: ysu-ml-a-13-s3 버킷
* AI: Amazon Bedrock (Nova Lite v1:0 모델)
* 임베딩: Cohere Embed v4:0
* Streamlit: 멀티탭 웹 인터페이스
핵심 테이블 구조
sql

```sql
- schools (id, name, code)
- documents (school_id, file_name, source_url, category, processed, chunks_count, created_at)
- document_chunks (document_id, chunk_text, embedding)
- rss_feeds (school_id, url, title, status, last_processed, processed_count, created_at)
- departments (school_id, name, description, main_phone)
- business_keywords (department_id, keyword, weight)  
- staff_members (department_id, name, position, phone, email, responsibilities, is_head)
```

✅ 완성된 5개 탭 기능
1. 💬 챗봇 탭
   * 학교별 검색: school_id 기반 완전 분리
   * AI 응답: Bedrock Nova Lite 모델
   * 3단계 검색 시스템:
      * 고품질 결과 (관련성 60%+) → RAG 기반 답변
      * 저품질 결과 → 부서 검색 fallback
      * 결과 없음 → 일반 문의 안내
   * 관련성 점수: 키워드(70%) + 카테고리(20%) + 문맥(10%)
2. 📄 PDF 업로드 탭
   * 학교별 S3 경로: `documents/YSU/YYYY/MM/DD/` 구조
   * 자동 처리: Lambda 함수가 S3 이벤트로 벡터화
   * UI 개선: 동적 키 시스템으로 업로드 후 완전 초기화
3. 📡 S3 PDF 관리 탭
   * 페이지네이션: 5개씩 표시로 성능 최적화
   * 수동 처리: S3 키 직접 입력하여 처리 가능
   * 삭제 기능: S3 파일 + DB 메타데이터 동시 삭제
   * 확인 시스템: 삭제 전 2단계 확인
4. 🔗 RSS 피드 탭
   * RSS 관리: feedparser로 추가/삭제/미리보기
   * 중복 방지: 제목/링크 기반 스마트 중복 검사
   * 실시간 미리보기: 최신 5개 항목 표시
   * 자동 벡터화: RSS → 청크 변환 후 DB 저장
5. 📊 파일 관리 탭
   * 학교별 통계: 총 문서/처리완료/청크 수
   * 카테고리별 분석: PDF vs RSS 분류 통계
   * 실시간 현황: 선택된 학교만 필터링
🔧 주요 해결된 기술 문제들
고급 검색 엔진
* ✅ 자연어 처리: 불용어 제거 + 핵심 키워드 추출
* ✅ 관련성 계산: 하이브리드 스코어링 시스템
* ✅ 부서 매칭: 키워드 가중치 기반 스마트 라우팅
* ✅ 카테고리 분류: 교원관리/학사관리/학생지원 등
Lambda 최적화
* ✅ 의존성 해결: tiktoken → CharacterTextSplitter
* ✅ 멀티스쿨 지원: S3 경로 기반 school_id 자동 할당
* ✅ 에러 처리: 실패시 재시도 + 로깅
Streamlit UX
* ✅ 세션 관리: 학교별 독립적 상태
* ✅ 키 충돌 방지: 네임스페이스 분리 (rss_, page_, pdf_)
* ✅ 동적 UI: 실시간 업데이트 + 자동 새로고침
데이터베이스 설계
* ✅ 완전 분리: 모든 테이블 school_id 기반
* ✅ 조직도 시스템: 부서/직원/업무키워드 연동
* ✅ 이력 관리: created_at, last_processed 추가
📁 핵심 파일
* 메인 앱: 2259줄 Streamlit 코드
* Lambda: PDF 자동처리 함수 (배포완료)
🎯 현재 상태
✅ 완전 작동:
* 멀티스쿨 완전분리 + 고급검색 + AI답변 + 부서안내
* RSS 중복방지 + 페이지네이션 + 실시간 통계
⚡ 성능 최적화:
* 학교별 독립 세션 + 효율적 DB 쿼리 + UI 렉 방지.
