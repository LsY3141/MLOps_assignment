from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from typing import List, Optional, Dict, Any, Tuple
import hashlib
import json
import logging
from datetime import datetime, timedelta
from app.services.llm_service import llm_service
from app.database import models

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 검색 성능 설정
SIMILARITY_THRESHOLDS = {
    "high": 0.85,      # 매우 유사
    "medium": 0.75,    # 일반적으로 유사 
    "low": 0.65        # 최소 유사도
}

DISTANCE_THRESHOLDS = {
    "high": 0.3,       # 매우 가까움
    "medium": 0.6,     # 일반적으로 가까움
    "low": 0.9         # 최소 거리
}

# 캐시 설정
CACHE_TTL_MINUTES = 30
MAX_CACHE_SIZE = 1000

class SearchCache:
    """메모리 기반 간단한 검색 캐시"""
    
    def __init__(self):
        self.cache = {}
        self.timestamps = {}
        
    def _generate_key(self, question: str, school_id: int) -> str:
        """캐시 키 생성"""
        content = f"{question}:{school_id}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def get(self, question: str, school_id: int) -> Optional[Dict]:
        """캐시에서 검색 결과 가져오기"""
        key = self._generate_key(question, school_id)
        
        if key in self.cache:
            timestamp = self.timestamps.get(key)
            if timestamp and datetime.now() - timestamp < timedelta(minutes=CACHE_TTL_MINUTES):
                logger.info(f"🚀 Cache hit for question: {question[:30]}...")
                return self.cache[key]
            else:
                # 만료된 캐시 제거
                self._remove(key)
        
        return None
    
    def set(self, question: str, school_id: int, result: Dict):
        """검색 결과 캐시에 저장"""
        key = self._generate_key(question, school_id)
        
        # 캐시 크기 제한
        if len(self.cache) >= MAX_CACHE_SIZE:
            self._cleanup_old_entries()
        
        self.cache[key] = result
        self.timestamps[key] = datetime.now()
        logger.info(f"💾 Cached result for question: {question[:30]}...")
    
    def _remove(self, key: str):
        """특정 캐시 엔트리 제거"""
        self.cache.pop(key, None)
        self.timestamps.pop(key, None)
    
    def _cleanup_old_entries(self):
        """오래된 캐시 엔트리 정리"""
        current_time = datetime.now()
        expired_keys = []
        
        for key, timestamp in self.timestamps.items():
            if current_time - timestamp > timedelta(minutes=CACHE_TTL_MINUTES):
                expired_keys.append(key)
        
        for key in expired_keys:
            self._remove(key)
        
        logger.info(f"🧹 Cleaned up {len(expired_keys)} expired cache entries")

class RagResponse(BaseModel):
    """RAG 응답 모델"""
    answer: str
    source_documents: List[Dict[str, Any]]
    confidence_score: Optional[float] = None
    search_strategy: Optional[str] = None
    fallback_used: bool = False
    category: Optional[str] = None
    cache_hit: bool = False

class HybridRAGService:
    """
    완전한 하이브리드 RAG 서비스
    - 키워드 필터링 + 기존 임베딩 재활용
    - 캐싱, 검색 전략, 재랭킹 포함
    """
    
    def __init__(self):
        self.llm = llm_service
        self.cache = SearchCache()
        self.search_stats = {
            "total_queries": 0,
            "cache_hits": 0,
            "keyword_searches": 0,
            "vector_searches": 0,
            "hybrid_searches": 0,
            "successful_retrievals": 0,
            "fallback_used": 0
        }
    
    async def get_rag_response(self, question: str, school_id: int, db: Session) -> RagResponse:
        """
        메인 RAG 프로세스: 키워드 + 기존 임베딩 하이브리드 검색
        """
        logger.info(f"🚀 Starting Hybrid RAG process for: '{question[:50]}...'")
        self.search_stats["total_queries"] += 1
        
        try:
            # 1. 캐시 확인
            cached_result = self.cache.get(question, school_id)
            if cached_result:
                self.search_stats["cache_hits"] += 1
                cached_result["cache_hit"] = True
                return RagResponse(**cached_result)
            
            # 2. 질문 분석 및 검색 전략 결정
            search_strategy = await self._determine_search_strategy(question)
            logger.info(f"🎯 Search strategy: {search_strategy}")
            
            # 3. 키워드 추출
            keywords = self._extract_keywords(question)
            logger.info(f"📝 Extracted keywords: {keywords}")
            
            # 4. 키워드 후보 필터링
            candidates = await self._find_keyword_candidates(keywords, school_id, db)
            
            if not candidates:
                logger.info("❌ No keyword candidates found, using fallback")
                return await self._fallback_response(question, school_id, db, "no_candidates")
            
            self.search_stats["keyword_searches"] += 1
            logger.info(f"✅ Found {len(candidates)} keyword candidates")
            
            # 5. 기준 임베딩 선택 및 벡터 검색
            reference_candidate = self._select_reference_candidate(candidates, keywords, question)
            search_results = await self._hybrid_vector_search(
                reference_candidate, school_id, db, search_strategy
            )
            
            if not search_results:
                logger.info("❌ Vector search failed, using best keyword candidate")
                return await self._generate_response_from_candidate(reference_candidate, question, "keyword_only")
            
            self.search_stats["vector_searches"] += 1
            logger.info(f"✅ Vector search found {len(search_results)} results")
            
            # 6. 검색 결과 품질 평가
            if not await self._evaluate_search_quality(search_results, search_strategy):
                logger.info("⚠️ Search quality insufficient, using keyword candidate")
                return await self._generate_response_from_candidate(reference_candidate, question, "quality_fallback")
            
            # 7. 결과 재랭킹
            ranked_results = await self._rerank_results(question, search_results, keywords)
            
            # 8. 최종 응답 생성
            response = await self._generate_enhanced_response(question, ranked_results, search_strategy)
            
            # 9. 결과 캐싱
            response_dict = response.dict()
            self.cache.set(question, school_id, response_dict)
            
            self.search_stats["successful_retrievals"] += 1
            return response
            
        except Exception as e:
            logger.error(f"Hybrid RAG process failed: {e}")
            return await self._fallback_response(question, school_id, db, "error")
    
    async def _determine_search_strategy(self, question: str) -> str:
        """질문 분석을 통한 검색 전략 결정"""
        question_lower = question.lower()
        
        # 규칙 기반 전략 결정
        if any(word in question_lower for word in ["언제", "기간", "일정", "날짜", "시간", "마감"]):
            return "temporal"  # 시간 관련
        elif any(word in question_lower for word in ["어디", "장소", "위치", "어느", "건물", "호실"]):
            return "spatial"   # 공간 관련
        elif any(word in question_lower for word in ["얼마", "비용", "금액", "가격", "수수료", "포상금"]):
            return "numerical" # 수치 관련
        elif any(word in question_lower for word in ["어떻게", "방법", "절차", "과정", "신청", "접수"]):
            return "procedural" # 절차 관련
        elif len(question.split()) <= 3:
            return "keyword"   # 단순 키워드
        else:
            return "semantic"  # 의미 검색
    
    def _extract_keywords(self, question: str) -> List[str]:
        """질문에서 의미있는 키워드 추출 (향상된 버전)"""
        # 불용어 제거 (확장됨)
        stopwords = {
            "은", "는", "이", "가", "을", "를", "에", "에서", "으로", "로", 
            "와", "과", "의", "도", "에게", "한테", "에서", "부터", "까지",
            "어떻게", "무엇", "언제", "어디", "누구", "왜", "어느", "얼마",
            "대해", "관해", "대한", "관한", "알려", "말해", "설명", "가르쳐",
            "해주세요", "알려주세요", "가르쳐주세요", "설명해주세요", "알고", "싶어요",
            "궁금", "하다", "있다", "없다", "되다", "하는", "있는", "없는", "되는"
        }
        
        # 정리 및 분리
        question_clean = question.replace("?", "").replace(".", "").replace("!", "")
        words = question_clean.split()
        
        # 의미있는 키워드만 선별 (길이 및 중요도 기반)
        keywords = []
        for word in words:
            if len(word) > 1 and word not in stopwords:
                keywords.append(word)
        
        # 중요한 키워드 우선순위 부여
        priority_keywords = []
        normal_keywords = []
        
        for keyword in keywords:
            # 중요한 키워드들 (도메인 특화)
            if any(important in keyword for important in [
                "경진대회", "진로", "장학", "취업", "인턴", "기숙사", "도서관",
                "수강", "학점", "성적", "졸업", "시험", "모집", "신청"
            ]):
                priority_keywords.append(keyword)
            else:
                normal_keywords.append(keyword)
        
        # 우선순위 키워드부터, 최대 5개
        final_keywords = (priority_keywords + normal_keywords)[:5]
        return final_keywords
    
    async def _find_keyword_candidates(self, keywords: List[str], school_id: int, db: Session) -> List[Dict]:
        """키워드를 포함한 후보 청크들 찾기 (향상된 버전)"""
        if not keywords:
            return []
        
        try:
            # 키워드별로 OR 조건 생성
            keyword_conditions = []
            for keyword in keywords:
                keyword_conditions.append(f"dc.chunk_text ILIKE '%{keyword}%'")
            
            where_clause = " OR ".join(keyword_conditions)
            
            query = text(f"""
                SELECT 
                    dc.id,
                    dc.chunk_text,
                    dc.embedding,
                    d.file_name,
                    d.source_url,
                    d.department,
                    d.category,
                    d.created_at
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                WHERE d.school_id = :school_id
                  AND ({where_clause})
                  AND dc.embedding IS NOT NULL
                  AND LENGTH(dc.chunk_text) > 50
                ORDER BY LENGTH(dc.chunk_text) DESC, d.created_at DESC
                LIMIT 15
            """)
            
            results = db.execute(query, {"school_id": school_id}).fetchall()
            
            candidates = []
            for result in results:
                # 키워드 매치 점수 계산
                keyword_matches = self._count_keyword_matches(result.chunk_text, keywords)
                relevance_score = self._calculate_relevance_score(result.chunk_text, keywords)
                
                candidates.append({
                    "id": result.id,
                    "text": result.chunk_text,
                    "embedding": result.embedding,
                    "file_name": result.file_name,
                    "source_url": result.source_url,
                    "department": result.department,
                    "category": result.category,
                    "created_at": result.created_at,
                    "keyword_matches": keyword_matches,
                    "relevance_score": relevance_score
                })
            
            return candidates
            
        except Exception as e:
            logger.error(f"Failed to find keyword candidates: {e}")
            return []
    
    def _count_keyword_matches(self, text: str, keywords: List[str]) -> int:
        """텍스트에서 키워드 매치 개수 계산"""
        text_lower = text.lower()
        return sum(1 for keyword in keywords if keyword.lower() in text_lower)
    
    def _calculate_relevance_score(self, text: str, keywords: List[str]) -> float:
        """텍스트와 키워드 간의 관련성 점수 계산"""
        text_lower = text.lower()
        total_score = 0.0
        
        for keyword in keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in text_lower:
                # 키워드 길이에 따른 가중치
                weight = len(keyword) / 10.0
                # 텍스트 내 출현 빈도
                frequency = text_lower.count(keyword_lower)
                total_score += weight * frequency
        
        # 텍스트 길이로 정규화
        normalized_score = total_score / (len(text) / 1000.0)
        return min(normalized_score, 1.0)
    
    def _select_reference_candidate(self, candidates: List[Dict], keywords: List[str], question: str) -> Dict:
        """가장 관련성 높은 후보를 기준으로 선택 (향상된 알고리즘)"""
        if not candidates:
            return None
        
        # 멀티 팩터 점수 계산
        scored_candidates = []
        
        for candidate in candidates:
            score = 0.0
            
            # 1. 키워드 매치 점수 (40%)
            keyword_score = candidate["keyword_matches"] / len(keywords)
            score += keyword_score * 0.4
            
            # 2. 관련성 점수 (30%)
            relevance_score = candidate["relevance_score"]
            score += relevance_score * 0.3
            
            # 3. 텍스트 품질 점수 (20%)
            text_quality = min(len(candidate["text"]) / 1000.0, 1.0)
            score += text_quality * 0.2
            
            # 4. 최신성 점수 (10%)
            if candidate["created_at"]:
                days_old = 30  # 임시 고정값
                freshness_score = max(0, 1 - (days_old / 365.0))  # 1년 기준
                score += freshness_score * 0.1
            
            scored_candidates.append((candidate, score))
        
        # 최고 점수 후보 선택
        best_candidate = max(scored_candidates, key=lambda x: x[1])[0]
        logger.info(f"🎯 Selected reference: Chunk {best_candidate['id']} (matches: {best_candidate['keyword_matches']})")
        
        return best_candidate
    
    async def _hybrid_vector_search(self, reference_candidate: Dict, school_id: int, db: Session, strategy: str) -> List[tuple]:
        """기준 임베딩을 사용한 벡터 유사도 검색"""
        if not reference_candidate or not reference_candidate["embedding"]:
            return []
        
        try:
            reference_embedding = reference_candidate["embedding"]
            
            # 전략별 검색 결과 수 조정
            limit = self._get_search_limit(strategy)
            
            query = text("""
                SELECT 
                    dc.id,
                    dc.chunk_text,
                    d.file_name,
                    d.source_url,
                    d.department,
                    d.category as doc_category,
                    dc.embedding <=> :reference_embedding as l2_distance,
                    1 - (dc.embedding <=> :reference_embedding) as cosine_similarity
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                WHERE d.school_id = :school_id
                  AND dc.embedding IS NOT NULL
                  AND LENGTH(dc.chunk_text) > 50
                ORDER BY dc.embedding <=> :reference_embedding
                LIMIT :limit
            """)
            
            results = db.execute(query, {
                "reference_embedding": reference_embedding,
                "school_id": school_id,
                "limit": limit
            }).fetchall()
            
            # 결과 품질 로깅
            for i, result in enumerate(results[:3]):
                distance = float(result.l2_distance)
                similarity = float(result.cosine_similarity)
                logger.info(f"    📄 Result {i+1}: Distance={distance:.4f}, Similarity={similarity:.4f}")
            
            return results
            
        except Exception as e:
            logger.error(f"Hybrid vector search failed: {e}")
            return []
    
    def _get_search_limit(self, strategy: str) -> int:
        """검색 전략별 결과 수 결정"""
        limits = {
            "keyword": 3,
            "temporal": 5,
            "spatial": 4,
            "numerical": 4,
            "procedural": 6,
            "semantic": 5
        }
        return limits.get(strategy, 5)
    
    async def _evaluate_search_quality(self, search_results: List[tuple], strategy: str) -> bool:
        """검색 전략별 품질 평가 (완화된 기준)"""
        if not search_results:
            return False
        
        best_result = search_results[0]
        best_distance = float(best_result.l2_distance)
        best_similarity = float(best_result.cosine_similarity)
        
        # 기존 임베딩 재활용 방식에 맞춰 임계값 완화
        if strategy == "keyword":
            threshold_type = "low"  # 키워드 검색은 매우 관대하게
        elif strategy in ["temporal", "numerical"]:
            threshold_type = "medium"  # 정확한 정보가 중요하지만 완화
        else:
            threshold_type = "low"  # 전반적으로 완화된 기준
        
        # 완화된 임계값
        relaxed_distance_thresholds = {
            "high": 0.5,
            "medium": 0.8,
            "low": 1.2
        }
        
        relaxed_similarity_thresholds = {
            "high": 0.5,
            "medium": 0.3,
            "low": 0.1
        }
        
        distance_ok = best_distance < relaxed_distance_thresholds[threshold_type]
        similarity_ok = best_similarity > relaxed_similarity_thresholds[threshold_type]
        
        logger.info(f"🎯 Quality check ({threshold_type}): "
              f"Distance={best_distance:.4f} ({'✅' if distance_ok else '❌'}), "
              f"Similarity={best_similarity:.4f} ({'✅' if similarity_ok else '❌'})")
        
        return distance_ok or similarity_ok
    
    async def _rerank_results(self, question: str, search_results: List[tuple], keywords: List[str]) -> List[tuple]:
        """검색 결과 재랭킹 (키워드 친화적)"""
        logger.info(f"🔄 Re-ranking {len(search_results)} results...")
        
        if len(search_results) <= 1:
            return search_results
        
        try:
            scored_results = []
            
            for result in search_results:
                # 기본 점수 (유사도)
                base_score = float(result.cosine_similarity)
                
                # 보너스 점수 계산
                bonus_score = 0.0
                
                # 키워드 매치 보너스 (중요!)
                keyword_matches = self._count_keyword_matches(result.chunk_text, keywords)
                if keyword_matches > 0:
                    keyword_bonus = min(keyword_matches * 0.1, 0.3)  # 최대 30% 보너스
                    bonus_score += keyword_bonus
                
                # 부서 정보 보너스
                if hasattr(result, 'department') and result.department:
                    bonus_score += 0.05
                
                # 텍스트 품질 보너스
                if len(result.chunk_text) > 100:
                    bonus_score += 0.02
                
                # 카테고리 관련성 보너스
                if hasattr(result, 'doc_category'):
                    category_bonus = self._calculate_category_bonus(question, result.doc_category)
                    bonus_score += category_bonus
                
                final_score = base_score + bonus_score
                scored_results.append((result, final_score))
            
            # 점수 기준으로 재정렬
            scored_results.sort(key=lambda x: x[1], reverse=True)
            ranked_results = [result for result, score in scored_results]
            
            logger.info("✅ Re-ranking complete")
            return ranked_results
            
        except Exception as e:
            logger.warning(f"Re-ranking failed, using original order: {e}")
            return search_results
    
    def _calculate_category_bonus(self, question: str, doc_category: str) -> float:
        """문서 카테고리와 질문 간의 관련성 보너스"""
        question_lower = question.lower()
        
        category_keywords = {
            "career": ["진로", "취업", "인턴", "경진대회", "채용"],
            "scholarship": ["장학", "학비", "등록금"],
            "academic": ["학사", "수강", "학점", "성적", "졸업"],
            "announcement": ["공지", "안내", "모집", "신청"]
        }
        
        if doc_category in category_keywords:
            keywords = category_keywords[doc_category]
            matches = sum(1 for keyword in keywords if keyword in question_lower)
            return min(matches * 0.02, 0.1)  # 최대 10% 보너스
        
        return 0.0
    
    async def _generate_enhanced_response(self, question: str, search_results: List[tuple], strategy: str) -> RagResponse:
        """향상된 답변 생성 (키워드 친화적)"""
        logger.info("📝 Generating enhanced response...")
        
        if not search_results:
            return await self._fallback_response(question, 1, None, "no_results")
        
        # 컨텍스트 구성 (더 풍부하게)
        context_parts = []
        source_documents = []
        
        for i, result in enumerate(search_results):
            chunk_text = result.chunk_text
            source_info = f"출처: {result.file_name or result.source_url or '내부 문서'}"
            
            if result.department:
                source_info += f" (담당: {result.department})"
            
            context_parts.append(f"문서 {i+1}: {chunk_text}\n{source_info}")
            
            source_documents.append({
                "document_id": getattr(result, 'document_id', result.id),
                "chunk_id": result.id,
                "text": chunk_text[:300] + "..." if len(chunk_text) > 300 else chunk_text,
                "source": result.file_name or result.source_url,
                "department": result.department,
                "category": result.doc_category,
                "similarity_score": float(result.cosine_similarity),
                "distance": float(result.l2_distance),
                "rank": i + 1
            })
        
        context = "\n\n".join(context_parts)
        
        # LLM을 통한 답변 생성
        final_answer = self.llm.get_chat_response(context, question)
        
        # 신뢰도 점수 계산 (완화된 기준)
        confidence_score = min(float(search_results[0].cosine_similarity) + 0.2, 1.0)
        
        return RagResponse(
            answer=final_answer,
            source_documents=source_documents,
            confidence_score=confidence_score,
            search_strategy="hybrid_keyword_vector",
            fallback_used=False,
            cache_hit=False
        )
    
    async def _generate_response_from_candidate(self, candidate: Dict, question: str, strategy: str) -> RagResponse:
        """키워드 후보로부터 직접 응답 생성"""
        if not candidate:
            return await self._fallback_response(question, 1, None, "no_candidate")
        
        logger.info(f"📝 Generating response from keyword candidate: {candidate['id']}")
        
        answer = self.llm.get_chat_response(candidate["text"], question)
        
        source_documents = [{
            "document_id": candidate["id"],
            "chunk_id": candidate["id"],
            "text": candidate["text"][:300] + "..." if len(candidate["text"]) > 300 else candidate["text"],
            "source": candidate["file_name"] or candidate["source_url"],
            "department": candidate["department"],
            "category": candidate["category"],
            "keyword_matches": candidate["keyword_matches"],
            "relevance_score": candidate["relevance_score"],
            "rank": 1
        }]
        
        return RagResponse(
            answer=answer,
            source_documents=source_documents,
            confidence_score=0.7,
            search_strategy=strategy,
            fallback_used=False,
            cache_hit=False
        )
    
    async def _fallback_response(self, question: str, school_id: int, db: Session, reason: str) -> RagResponse:
        """향상된 Fallback 로직"""
        logger.info(f"🚨 Fallback triggered: {reason}")
        self.search_stats["fallback_used"] += 1
        
        # 질문 카테고리 분류
        category = self.llm.get_query_category(question)
        logger.info(f"📊 Question categorized as: {category}")
        
        # DB에서 담당 부서 정보 조회 (안전하게)
        contact = None
        if db:
            try:
                contact = db.query(models.DefaultContact).filter(
                    models.DefaultContact.school_id == school_id,
                    models.DefaultContact.category == category
                ).first()
            except:
                pass
        
        if contact:
            answer = self._format_enhanced_fallback_answer(question, category, contact, reason)
        else:
            answer = self._format_generic_fallback_answer(question, category, reason)
        
        return RagResponse(
            answer=answer,
            source_documents=[],
            confidence_score=0.0,
            search_strategy="fallback",
            fallback_used=True,
            category=category,
            cache_hit=False
        )
    
    def _format_enhanced_fallback_answer(self, question: str, category: str, contact, reason: str) -> str:
        """향상된 Fallback 답변 포맷"""
        category_names = {
            "academic": "학사",
            "scholarship": "장학금", 
            "facilities": "시설",
            "career": "진로",
            "other": "기타"
        }
        
        category_kr = category_names.get(category, "관련")
        
        return f"""죄송합니다. '{question}'에 대한 구체적인 정보를 현재 찾지 못했습니다.

## 📞 담당 부서 안내

**🏢 {contact.department}**
- 📞 연락처: **{contact.contact_info or '직접 방문 또는 홈페이지 확인'}**
- 📋 담당업무: {contact.description or f'{category_kr} 관련 업무'}

## 💡 추가 도움말

**즉시 도움이 필요하시다면:**
1. 위 담당 부서에 전화 문의
2. 학교 홈페이지 공지사항 확인  
3. 학과 사무실 방문
4. 학생지원센터 종합 상담

감사합니다! 🙏"""

    def _format_generic_fallback_answer(self, question: str, category: str, reason: str) -> str:
        """일반적인 Fallback 답변"""
        return f"""죄송합니다. '{question}'에 대한 구체적인 정보를 현재 찾지 못했습니다.

## 📞 추천 문의처
- **학생지원센터** (종합 상담)  
- **해당 학과 사무실**
- **학교 대표 전화**

## 💡 다른 방법
1. 학교 홈페이지에서 관련 공지사항 확인
2. 학생 포털 시스템 검색  
3. 동기나 선배에게 문의
4. 더 구체적인 키워드로 다시 질문

도움이 되지 못해 죄송합니다. 🙏"""
    
    def get_search_stats(self) -> Dict[str, Any]:
        """상세 검색 통계 반환"""
        total = self.search_stats["total_queries"]
        if total == 0:
            return self.search_stats
            
        return {
            **self.search_stats,
            "cache_hit_rate": round((self.search_stats["cache_hits"] / total) * 100, 2),
            "keyword_search_rate": round((self.search_stats["keyword_searches"] / total) * 100, 2),
            "vector_search_rate": round((self.search_stats["vector_searches"] / total) * 100, 2),
            "success_rate": round((self.search_stats["successful_retrievals"] / total) * 100, 2),
            "fallback_rate": round((self.search_stats["fallback_used"] / total) * 100, 2)
        }

# 전역 RAG 서비스 인스턴스
hybrid_rag_service = HybridRAGService()

# 기존 인터페이스 유지 (하위 호환성)
async def get_rag_response(question: str, school_id: int, db: Session) -> RagResponse:
    """메인 RAG 함수 - 키워드 + 기존 임베딩 하이브리드"""
    return await hybrid_rag_service.get_rag_response(question, school_id, db)

# 유틸리티 함수들
async def get_search_statistics() -> Dict[str, Any]:
    """검색 통계 조회"""
    return hybrid_rag_service.get_search_stats()

async def clear_search_cache():
    """검색 캐시 클리어"""
    hybrid_rag_service.cache.cache.clear()
    hybrid_rag_service.cache.timestamps.clear()
    logger.info("🧹 Search cache cleared")

if __name__ == "__main__":
    print("=== Hybrid RAG Service v3.0 (Complete) ===")
    print("Features:")
    print("- Keyword filtering + Existing embedding reuse")
    print("- Advanced caching system")
    print("- Multi-factor candidate selection")
    print("- Enhanced re-ranking with keyword bonus")
    print("- Comprehensive search strategies")
    print("- Detailed statistics tracking")