"""
LLM 서비스
AWS Bedrock을 통한 Claude 및 Titan 모델 연동
"""

import boto3
import json
from typing import List, Dict, Any
from app.utils.config import settings


class LLMService:
    """
    AWS Bedrock LLM 서비스 관리 클래스
    """
    
    def __init__(self):
        self.bedrock_runtime = boto3.client(
            service_name='bedrock-runtime',
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
        
        self.claude_model_id = settings.BEDROCK_CLAUDE_MODEL
        self.embedding_model_id = settings.BEDROCK_EMBEDDING_MODEL
    
    async def generate_answer(self, query: str, context: str) -> str:
        """
        RAG 기반 답변 생성
        
        Args:
            query: 사용자 질문
            context: 검색된 문서 컨텍스트
            
        Returns:
            생성된 답변
        """
        system_prompt = """
당신은 대학 행정 정보를 안내하는 친절한 AI 어시스턴트입니다.
제공된 문서 컨텍스트를 기반으로 정확하고 구조화된 답변을 제공해주세요.

답변 형식:
1. 핵심 정보를 명확하게 제시
2. 담당 부서 및 연락처 정보 포함
3. 필요한 서류나 절차가 있다면 상세히 안내
4. 근거 문서 출처 명시
"""
        
        user_prompt = f"""
[참고 문서]
{context}

[학생 질문]
{query}

위 문서를 바탕으로 학생의 질문에 답변해주세요.
"""
        
        try:
            # TODO: 실제 Bedrock Claude API 호출
            # response = self.bedrock_runtime.invoke_model(
            #     modelId=self.claude_model_id,
            #     body=json.dumps({
            #         "anthropic_version": "bedrock-2023-05-31",
            #         "max_tokens": 1024,
            #         "system": system_prompt,
            #         "messages": [
            #             {
            #                 "role": "user",
            #                 "content": user_prompt
            #             }
            #         ]
            #     })
            # )
            # 
            # response_body = json.loads(response['body'].read())
            # return response_body['content'][0]['text']
            
            # 임시 반환값
            return "이 기능은 현재 개발 중입니다. AWS Bedrock Claude API를 연동하면 실제 답변이 생성됩니다."
            
        except Exception as e:
            raise Exception(f"답변 생성 중 오류 발생: {str(e)}")
    
    async def classify_intent(self, query: str) -> str:
        """
        질문의 의도(카테고리) 분류
        
        Args:
            query: 사용자 질문
            
        Returns:
            분류된 카테고리 (학사/장학/시설 등)
        """
        system_prompt = """
당신은 대학생 질문을 분류하는 전문가입니다.
질문을 다음 카테고리 중 하나로 분류해주세요:
- 학사 (휴학, 복학, 수강신청, 학점 등)
- 장학 (장학금, 학자금 대출 등)
- 시설 (도서관, 기숙사, 식당 등)
- 행사 (축제, 세미나, 채용박람회 등)
- 기타

카테고리명만 반환하세요.
"""
        
        try:
            # TODO: 실제 Bedrock Claude API 호출
            # response = self.bedrock_runtime.invoke_model(...)
            
            # 임시 반환값 (간단한 키워드 매칭)
            query_lower = query.lower()
            
            if any(keyword in query_lower for keyword in ["휴학", "복학", "수강", "학점", "전공", "졸업"]):
                return "학사"
            elif any(keyword in query_lower for keyword in ["장학", "장학금", "학자금", "등록금"]):
                return "장학"
            elif any(keyword in query_lower for keyword in ["도서관", "기숙사", "식당", "주차"]):
                return "시설"
            elif any(keyword in query_lower for keyword in ["축제", "행사", "세미나", "채용"]):
                return "행사"
            else:
                return "기타"
                
        except Exception as e:
            raise Exception(f"의도 분류 중 오류 발생: {str(e)}")
    
    async def get_embedding(self, text: str) -> List[float]:
        """
        텍스트를 임베딩 벡터로 변환
        
        Args:
            text: 변환할 텍스트
            
        Returns:
            1536차원 임베딩 벡터
        """
        try:
            # TODO: 실제 Bedrock Titan Embeddings API 호출
            # response = self.bedrock_runtime.invoke_model(
            #     modelId=self.embedding_model_id,
            #     body=json.dumps({
            #         "inputText": text
            #     })
            # )
            # 
            # response_body = json.loads(response['body'].read())
            # return response_body['embedding']
            
            # 임시 반환값 (0 벡터)
            return [0.0] * 1536
            
        except Exception as e:
            raise Exception(f"임베딩 생성 중 오류 발생: {str(e)}")
    
    async def batch_embed(self, texts: List[str]) -> List[List[float]]:
        """
        여러 텍스트를 한 번에 임베딩
        
        Args:
            texts: 텍스트 리스트
            
        Returns:
            임베딩 벡터 리스트
        """
        embeddings = []
        
        for text in texts:
            embedding = await self.get_embedding(text)
            embeddings.append(embedding)
        
        return embeddings
