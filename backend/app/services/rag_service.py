"""
RAG (검색 증강 생성) 서비스
벡터 검색 및 답변 생성 파이프라인
"""

from typing import Dict, List, Any, Optional
from app.services.llm_service import LLMService
from app.utils.config import settings


class RAGService:
    """
    RAG 파이프라인 관리 클래스
    """
    
    def __init__(self):
        self.llm_service = LLMService()
        self.similarity_threshold = settings.SIMILARITY_THRESHOLD
        self.top_k = settings.VECTOR_SEARCH_TOP_K
    
    async def query(
        self,
        school_id: str,
        query: str,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        사용자 질문에 대한 RAG 기반 답변 생성
        
        Args:
            school_id: 학교 ID
            query: 사용자 질문
            session_id: 세션 ID (선택)
            
        Returns:
            답변 및 메타데이터
        """
        # 1. 질문을 벡터로 변환
        query_embedding = await self._embed_query(query)
        
        # 2. 벡터 DB에서 유사 문서 검색
        search_results = await self._vector_search(
            school_id=school_id,
            query_embedding=query_embedding
        )
        
        # 3. 검색 결과의 신뢰도 평가
        if self._is_confident(search_results):
            # RAG 답변 생성
            response = await self._generate_rag_response(query, search_results)
            response["response_type"] = "rag"
        else:
            # Fallback: 담당 부서 안내
            response = await self._generate_fallback_response(query, school_id)
            response["response_type"] = "fallback"
        
        return response
    
    async def _embed_query(self, query: str) -> List[float]:
        """
        질문을 벡터로 변환
        
        Args:
            query: 사용자 질문
            
        Returns:
            임베딩 벡터
        """
        # TODO: Bedrock Titan Embeddings 호출
        # embedding = self.llm_service.get_embedding(query)
        # return embedding
        
        # 임시 반환값
        return [0.0] * 1536
    
    async def _vector_search(
        self,
        school_id: str,
        query_embedding: List[float]
    ) -> List[Dict[str, Any]]:
        """
        pgvector를 사용한 유사도 검색
        
        Args:
            school_id: 학교 ID
            query_embedding: 질문 임베딩 벡터
            
        Returns:
            검색 결과 리스트
        """
        # TODO: RDS pgvector 검색 구현
        # SELECT * FROM documents
        # WHERE school_id = :school_id
        # ORDER BY embedding <=> :query_embedding
        # LIMIT :top_k
        
        # 임시 반환값
        return []
    
    def _is_confident(self, search_results: List[Dict[str, Any]]) -> bool:
        """
        검색 결과의 신뢰도 평가
        
        Args:
            search_results: 검색 결과
            
        Returns:
            신뢰도 충분 여부
        """
        if not search_results:
            return False
        
        # 최상위 결과의 유사도가 임계값 이상인지 확인
        top_similarity = search_results[0].get("similarity", 0.0)
        return top_similarity >= self.similarity_threshold
    
    async def _generate_rag_response(
        self,
        query: str,
        search_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        검색 결과를 기반으로 RAG 답변 생성
        
        Args:
            query: 사용자 질문
            search_results: 검색된 문서들
            
        Returns:
            생성된 답변 및 메타데이터
        """
        # 검색 결과를 컨텍스트로 구성
        context = self._build_context(search_results)
        
        # LLM을 사용하여 답변 생성
        answer = await self.llm_service.generate_answer(
            query=query,
            context=context
        )
        
        return {
            "answer": answer,
            "source_documents": search_results,
            "metadata": {
                "department": search_results[0].get("department"),
                "contact": search_results[0].get("contact"),
            }
        }
    
    async def _generate_fallback_response(
        self,
        query: str,
        school_id: str
    ) -> Dict[str, Any]:
        """
        정보 부재 시 Fallback 응답 생성
        
        Args:
            query: 사용자 질문
            school_id: 학교 ID
            
        Returns:
            Fallback 응답
        """
        # LLM을 사용하여 질문의 의도(카테고리) 파악
        category = await self.llm_service.classify_intent(query)
        
        # 카테고리에 해당하는 기본 담당 부서 조회
        default_contact = await self._get_default_contact(school_id, category)
        
        fallback_message = f"""
죄송하지만, 정확한 정보를 찾을 수 없습니다.

아래 부서로 문의하시면 정확한 안내를 받으실 수 있습니다:

**{default_contact.get('department', '해당 부서')}**
- 담당자: {default_contact.get('contact_person', '미정')}
- 연락처: {default_contact.get('phone', '미정')}
- 위치: {default_contact.get('location', '미정')}
        """.strip()
        
        return {
            "answer": fallback_message,
            "source_documents": None,
            "metadata": default_contact
        }
    
    def _build_context(self, search_results: List[Dict[str, Any]]) -> str:
        """
        검색 결과를 LLM용 컨텍스트로 변환
        
        Args:
            search_results: 검색 결과
            
        Returns:
            컨텍스트 문자열
        """
        context_parts = []
        
        for idx, doc in enumerate(search_results, 1):
            context_parts.append(f"[문서 {idx}]")
            context_parts.append(f"제목: {doc.get('title', '제목 없음')}")
            context_parts.append(f"내용: {doc.get('content', '')}")
            context_parts.append(f"담당 부서: {doc.get('department', '미정')}")
            context_parts.append(f"연락처: {doc.get('contact', '미정')}")
            context_parts.append("")
        
        return "\n".join(context_parts)
    
    async def _get_default_contact(
        self,
        school_id: str,
        category: str
    ) -> Dict[str, str]:
        """
        카테고리별 기본 담당 부서 조회
        
        Args:
            school_id: 학교 ID
            category: 카테고리
            
        Returns:
            담당 부서 정보
        """
        # TODO: DB에서 default_contacts 테이블 조회
        
        # 임시 반환값
        return {
            "department": "학사지원팀",
            "contact_person": "홍길동",
            "phone": "031-123-4567",
            "location": "본관 2층"
        }
