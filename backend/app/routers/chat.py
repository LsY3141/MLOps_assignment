"""
챗봇 질의응답 API 라우터
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from app.services.rag_service import RAGService
from app.services.llm_service import LLMService

router = APIRouter()


class ChatRequest(BaseModel):
    """
    챗봇 질문 요청 모델
    """
    school_id: str = Field(..., description="학교 ID")
    query: str = Field(..., min_length=1, max_length=500, description="사용자 질문")
    session_id: Optional[str] = Field(None, description="세션 ID (대화 이력 추적용)")


class ChatResponse(BaseModel):
    """
    챗봇 응답 모델
    """
    answer: str = Field(..., description="생성된 답변")
    source_documents: Optional[list] = Field(None, description="참고 문서 목록")
    metadata: Optional[Dict[str, Any]] = Field(None, description="추가 메타데이터")
    response_type: str = Field(..., description="응답 타입: 'rag' 또는 'fallback'")


@router.post("/query", response_model=ChatResponse)
async def chat_query(request: ChatRequest):
    """
    사용자 질문에 대한 답변 생성
    
    - **school_id**: 학교 고유 ID
    - **query**: 사용자의 자연어 질문
    - **session_id**: (선택) 대화 세션 추적용 ID
    
    Returns:
        ChatResponse: AI가 생성한 답변 및 관련 정보
    """
    try:
        # TODO: 실제 RAG 서비스 구현
        # rag_service = RAGService()
        # result = await rag_service.query(
        #     school_id=request.school_id,
        #     query=request.query
        # )
        
        # 임시 응답 (구현 예정)
        return ChatResponse(
            answer="이 기능은 현재 개발 중입니다. RAG 파이프라인을 구현하면 실제 답변이 제공됩니다.",
            source_documents=None,
            metadata={
                "school_id": request.school_id,
                "query": request.query
            },
            response_type="rag"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"답변 생성 중 오류 발생: {str(e)}")


@router.get("/history/{session_id}")
async def get_chat_history(session_id: str):
    """
    대화 이력 조회
    
    Args:
        session_id: 세션 ID
        
    Returns:
        대화 이력 목록
    """
    # TODO: 대화 이력 조회 구현
    return {
        "session_id": session_id,
        "messages": [],
        "message": "대화 이력 조회 기능은 현재 개발 중입니다."
    }


@router.post("/feedback")
async def submit_feedback(
    session_id: str,
    message_id: str,
    rating: int,
    comment: Optional[str] = None
):
    """
    사용자 피드백 제출
    
    Args:
        session_id: 세션 ID
        message_id: 메시지 ID
        rating: 평점 (1-5)
        comment: 피드백 코멘트
        
    Returns:
        피드백 제출 결과
    """
    if rating < 1 or rating > 5:
        raise HTTPException(status_code=400, detail="평점은 1-5 사이여야 합니다.")
    
    # TODO: 피드백 저장 구현
    return {
        "status": "success",
        "message": "피드백이 제출되었습니다."
    }
