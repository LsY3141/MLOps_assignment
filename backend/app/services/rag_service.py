from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.services import llm_service
from app.database import models

# A threshold for L2 distance. A lower value means more similar.
# If the distance is greater than this, we consider it irrelevant.
DISTANCE_THRESHOLD = 0.6

class RagResponse(BaseModel):
    answer: str
    source_documents: list

async def get_rag_response(question: str, school_id: int, db: Session) -> RagResponse:
    """
    Performs the RAG process, with a fallback based on similarity score.
    """
    print(f"--- Starting RAG process for question: '{question}' ---")

    # 1. Create an embedding for the user's question
    query_embedding = llm_service.get_embeddings([question])
    if not query_embedding:
        return RagResponse(answer="Sorry, I could not process your question.", source_documents=[])
    
    # 2. Search for similar document chunks, including the distance score
    distance = models.DocumentChunk.embedding.l2_distance(query_embedding[0]).label("distance")
    results_with_distance = (
        db.query(models.DocumentChunk, distance)
        .join(models.Document)
        .filter(models.Document.school_id == school_id)
        .order_by(distance)
        .limit(3)
        .all()
    )
    
    # 3. Trigger fallback if no relevant documents are found OR if the best result is not similar enough
    if not results_with_distance or results_with_distance[0].distance > DISTANCE_THRESHOLD:
        print(f"--- [Fallback] No relevant docs found or similarity too low (best distance: {results_with_distance[0].distance if results_with_distance else 'N/A'}). ---")
        category = llm_service.get_query_category(question)
        contact = db.query(models.DefaultContact).filter(
            models.DefaultContact.school_id == school_id, models.DefaultContact.category == category).first()
        
        if contact:
            answer = (f"정확한 답변을 찾지 못했습니다. 하지만 질문하신 내용이 '{category}' 카테고리와 관련된 것 같습니다.\n"
                      f"이 문제는 '{contact.department}' 부서에 문의하시면 더 정확한 안내를 받으실 수 있습니다.\n"
                      f"연락처: {contact.contact_info or '별도 문의'}")
        else:
            answer = "죄송합니다, 질문에 대한 답변을 찾지 못했고, 관련 부서 정보도 찾을 수 없었습니다."
        return RagResponse(answer=answer, source_documents=[])

    # 4. If results are relevant, proceed with RAG
    relevant_chunks = [result.DocumentChunk for result in results_with_distance]
    context = "\n\n".join([chunk.chunk_text for chunk in relevant_chunks])
    final_answer = llm_service.get_chat_response(context, question)
    source_documents = [{"document_id": chunk.document_id, "chunk_id": chunk.id, "text": chunk.chunk_text} for chunk in relevant_chunks]

    return RagResponse(answer=final_answer, source_documents=source_documents)