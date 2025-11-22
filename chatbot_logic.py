import streamlit as st
import json
import re
from langchain.schema import Document
from langchain_aws import ChatBedrock
from sqlalchemy import text

from database import is_similar_keyword

# --- 챗봇 핵심 로직 ---

def search_documents(engine, vectorstore, query, school_id, embeddings):
    """벡터 검색과 키워드 검색을 결합한 하이브리드 검색을 수행합니다."""
    try:
        # 1. 벡터 유사도 검색 (by LangChain PGVector)
        if vectorstore:
            # school_id를 기준으로 필터링
            filter_criteria = {"school_id": school_id}
            vector_results = vectorstore.similarity_search_with_relevance_scores(
                query=query,
                k=5,
                filter=filter_criteria
            )
            # vector_results는 (Document, score) 튜플의 리스트
        else:
            vector_results = []

        # 2. 키워드 기반 검색 (Fallback)
        with engine.connect() as conn:
            keyword_results_raw = conn.execute(text(f"""
                SELECT dc.chunk_text, d.source_url, d.file_name, d.category, d.created_at
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                WHERE d.school_id = :school_id AND dc.chunk_text ILIKE :query
                ORDER BY d.created_at DESC
                LIMIT 5
            """), {"school_id": school_id, "query": f"%{query}%"}).fetchall()

        # 3. 결과 통합 및 Document 객체 변환
        processed_sources = set()
        combined_results = []

        # 벡터 검색 결과 처리
        for doc, score in vector_results:
            if doc.metadata['source'] not in processed_sources:
                doc.metadata['relevance_score'] = score
                combined_results.append(doc)
                processed_sources.add(doc.metadata['source'])

        # 키워드 검색 결과 처리 (벡터 검색 결과와 중복되지 않게)
        for row in keyword_results_raw:
            source_url = row.source_url
            if source_url not in processed_sources:
                metadata = {
                    "source": source_url,
                    "filename": row.file_name or "RSS 공지사항",
                    "category": row.category,
                    "date": row.created_at.strftime("%Y-%m-%d") if row.created_at else "N/A",
                    "title": extract_title_from_text(row.chunk_text),
                    "relevance_score": calculate_relevance_score(query, row.chunk_text, {}) # 점수 별도 계산
                }
                combined_results.append(Document(page_content=row.chunk_text, metadata=metadata))
                processed_sources.add(source_url)
        
        # 최종적으로 관련성 점수 기준으로 정렬
        combined_results.sort(key=lambda x: x.metadata.get('relevance_score', 0.0), reverse=True)
        
        return combined_results[:5] # 상위 5개 결과만 반환

    except Exception as e:
        st.error(f"문서 검색 실패: {str(e)}")
        return []

def generate_ai_response(bedrock_client, query, search_results):
    """검색된 문서를 바탕으로 AI 답변을 생성합니다."""
    try:
        # ChatBedrock 인스턴스 생성
        llm = ChatBedrock(
            client=bedrock_client,
            model_id="anthropic.claude-3-sonnet-20240229-v1:0", # Sonnet 모델 사용
            model_kwargs={"temperature": 0.7, "max_tokens": 4000}
        )

        if search_results:
            context = "\n".join([f"<doc>{doc.page_content}</doc>" for doc in search_results])
            sources = "\n".join([f"- {doc.metadata.get('title', '제목 없음')} ({doc.metadata.get('date', '날짜 정보 없음')})" for doc in search_results])
            
            prompt = f"""당신은 학사 정보 전문 AI 챗봇 'ClassMATE'입니다. 주어진 <docs> 안의 문서 내용을 바탕으로 사용자의 질문에 대해 명확하고 친절하게 한국어로 답변해주세요.
문서에 없는 내용은 절대 언급하지 말고, 확실한 정보만 답변에 포함해주세요.

<docs>
{context}
</docs>

사용자 질문: {query}

답변 마지막에는 반드시 다음 형식으로 참고 자료를 명시해주세요.
---
📋 **참고 자료:**
{sources}
"""
        else:
            prompt = f"""당신은 학사 정보 전문 AI 챗봇 'ClassMATE'입니다.
사용자 질문: {query}

주어진 정보가 없으므로, 질문에 직접 답변하지 마세요. 대신, 관련 정보를 찾을 수 없다고 안내하고 학교 공식 홈페이지나 담당 부서에 문의하라고 친절하게 안내해주세요."""

        # LangChain을 통해 AI 모델 호출
        response = llm.invoke(prompt)
        return response.content

    except Exception as e:
        return f"죄송합니다. AI 응답 생성 중 오류가 발생했습니다: {str(e)}"


# --- 헬퍼 함수 (관련성 점수, 텍스트 처리 등) ---

def extract_title_from_text(text):
    """텍스트에서 제목을 추출합니다."""
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if line.startswith('제목:'):
            return line.replace('제목:', '').strip()
        if line and 10 < len(line) < 100:
            return line
    return text[:50] + "..." if len(text) > 50 else text

def preprocess_query(query):
    """자연어 쿼리에서 핵심 키워드를 추출합니다."""
    stopwords = ['에', '대해', '대한', '에서', '으로', '로', '이', '가', '을', '를', '은', '는', '궁금합니다', '궁금해요', '알고싶어요', '알려주세요', '문의', '질문', '어떻게', '언제', '어디서', '무엇', '왜', '어떤', '입니다', '해주세요']
    words = re.sub(r'[^\w가-힣\s]', ' ', query).split()
    core_keywords = [word.strip() for word in words if len(word.strip()) > 1 and word not in stopwords]
    return ' '.join(core_keywords)

def calculate_relevance_score(query, document_content, metadata):
    """간소화된 관련성 점수 계산."""
    # 이 함수는 벡터 검색의 점수를 사용하므로, 키워드 검색 fallback을 위한 간이 계산만 수행
    processed_query = preprocess_query(query).lower()
    doc_text = document_content.lower()
    score = 0
    if processed_query in doc_text:
        score += 0.5
    
    query_words = set(processed_query.split())
    doc_words = set(doc_text.split())
    common_words = query_words.intersection(doc_words)
    score += 0.1 * len(common_words)
    
    return min(score, 1.0)

def get_relevance_indicator(score):
    """점수에 따른 관련성 지시자 아이콘을 반환합니다."""
    if score >= 0.7:
        return "✅", "높음", "success"
    elif score >= 0.4:
        return "⚠️", "보통", "warning"
    else:
        return "❌", "낮음", "error"
