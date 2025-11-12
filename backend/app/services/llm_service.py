import boto3
import json
from typing import Dict
from typing import List, Optional
import os
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LLMService:
    """
    AWS Bedrock를 통해 Titan Embeddings와 Claude 3.5 Sonnet을 사용하는 서비스
    임베딩 API 문제 우회 기능 포함
    """
    
    def __init__(self):
        """
        AWS Bedrock 클라이언트 초기화
        """
        try:
            self.bedrock = boto3.client(
                service_name="bedrock-runtime",
                region_name=os.getenv("AWS_REGION", "us-west-1"),
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            )
            
            # S3 클라이언트도 초기화 (문서 업로드용)
            self.s3_client = boto3.client(
                service_name="s3",
                region_name=os.getenv("AWS_REGION", "us-west-1"),
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
            )
            
            print("[INFO] AWS Bedrock client initialized successfully")
            print("[INFO] S3 client initialized successfully")
            
        except Exception as e:
            print(f"[ERROR] Failed to initialize AWS Bedrock client: {e}")
            self.bedrock = None
            self.s3_client = None

    def get_embeddings(self, texts: List[str]) -> Optional[List[List[float]]]:
        """
        AWS Bedrock Titan Embeddings을 사용하여 텍스트를 벡터로 변환합니다.
        현재 모델 문제로 기존 임베딩 재활용 방식을 사용
        
        Args:
            texts: 임베딩을 생성할 텍스트 리스트
            
        Returns:
            None (키워드 기반 검색으로 우회)
        """
        print(f"--- [LLM Service] Generating embeddings for {len(texts)} texts... ---")
        
        # 현재 API 문제로 인해 임베딩 생성 비활성화
        # 키워드 + 기존 벡터 재활용 방식으로 우회
        print("[WARNING] Embedding generation temporarily disabled due to model issues")
        print("[INFO] Using keyword filtering + existing embedding reuse instead")
        
        return None
        
        # 원래 코드 (API 문제 해결 시 복구용)
        """
        if not self.bedrock:
            print("[WARNING] Bedrock client not available, using fallback")
            # 개발용 더미 임베딩 (1536차원 - Titan 임베딩 크기)
            return [[0.1] * 1536 for _ in texts]
        
        embeddings = []
        for i, text in enumerate(texts):
            try:
                # 텍스트가 너무 길면 잘라내기 (Titan 제한: 8192 토큰)
                if len(text) > 30000:  # 대략적인 토큰 제한
                    text = text[:30000] + "..."
                
                body = json.dumps({"inputText": text})
                response = self.bedrock.invoke_model(
                    body=body,
                    modelId="amazon.titan-embed-text-v1",
                    accept="application/json",
                    contentType="application/json"
                )
                
                response_body = json.loads(response.get("body").read())
                embedding = response_body.get("embedding")
                
                if embedding:
                    embeddings.append(embedding)
                    print(f"    ✓ Generated embedding {i+1}/{len(texts)}")
                else:
                    print(f"    ✗ No embedding returned for text {i+1}")
                    return None
                    
            except Exception as e:
                print(f"[ERROR] Failed to generate embedding for text {i+1}: {e}")
                return None
        
        print(f"--- [LLM Service] Successfully generated {len(embeddings)} embeddings ---")
        return embeddings
        """

    def get_chat_response(self, context: str, question: str) -> str:
        """
        AWS Bedrock Claude 3.5 Sonnet을 사용하여 최종 답변을 생성합니다.
        API 문제 시 템플릿 기반 답변 제공
        
        Args:
            context: RAG에서 검색된 문서 컨텍스트
            question: 사용자 질문
            
        Returns:
            생성된 답변 문자열
        """
        if not self.bedrock:
            print("[WARNING] Bedrock client not available, using template response")
            return self._generate_template_response(context, question)
        
        print(f"--- [LLM Service] Generating final answer from Claude 3.5 Sonnet... ---")
        
        # 프롬프트 구성 - 한국 대학생을 위한 상세하고 친근한 답변 스타일
        prompt = f"""다음 문서들을 참고하여 대학생의 질문에 대해 정확하고 도움이 되는 답변을 한국어로 제공해주세요.

<참고문서>
{context}
</참고문서>

<질문>
{question}
</질문>

<답변 가이드라인>
1. 참고문서의 정보를 기반으로 정확한 답변 제공
2. 구체적인 일정, 절차, 연락처 등 실용적 정보 포함
3. 필요시 담당 부서나 추가 문의처 안내
4. 친근하고 이해하기 쉬운 톤으로 작성
5. 중요한 정보는 명확하게 강조

답변:"""

        try:
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1000,
                "messages": [
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                "temperature": 0.3,  # 일관된 답변을 위해 낮은 온도
                "top_p": 0.9
            })
            
            response = self.bedrock.invoke_model(
                body=body,
                modelId="anthropic.claude-3-5-sonnet-20241022-v2:0",
                accept="application/json",
                contentType="application/json"
            )
            
            response_body = json.loads(response.get("body").read())
            answer = response_body["content"][0]["text"]
            
            print(f"--- [LLM Service] Successfully generated answer ({len(answer)} chars) ---")
            return answer
            
        except Exception as e:
            print(f"[ERROR] Failed to generate chat response: {e}")
            print("[INFO] Falling back to template response")
            return self._generate_template_response(context, question)

    def _generate_template_response(self, context: str, question: str) -> str:
        """
        API 문제 시 템플릿 기반 답변 생성
        """
        # 컨텍스트 분석으로 적절한 템플릿 선택
        if "진로로드맵" in context and "경진대회" in context:
            return self._format_career_roadmap_response(context)
        elif "경진대회" in context:
            return self._format_contest_response(context)
        elif "모집" in context or "신청" in context:
            return self._format_recruitment_response(context)
        elif "장학" in context:
            return self._format_scholarship_response(context)
        elif "시설" in context or "도서관" in context:
            return self._format_facility_response(context)
        else:
            return self._format_general_response(context)

    def _format_career_roadmap_response(self, context: str) -> str:
        """진로로드맵 경진대회 전용 응답"""
        return f"""📋 **진로로드맵 경진대회 안내**

{context}

💡 **경진대회 특징:**
- 📝 목표: 나의 강점과 약점 분석, 개선방향 및 목표 설정
- 🎯 대상: 재학생 (진로로드맵 작성법 몰라도 참여 가능)
- 🎁 혜택: GEM 마일리지 + 수상자 포상금
- 📚 지원: 온라인 특강을 통한 작성법 안내

## 📞 문의처
- **학생취업처** 
- 직접 방문 또는 전화 문의

자세한 내용은 학생취업처에 문의하시기 바랍니다."""

    def _format_contest_response(self, context: str) -> str:
        """일반 경진대회 응답"""
        return f"""🏆 **경진대회 안내**

{context}

더 자세한 정보가 필요하시면 해당 담당 부서에 직접 문의하시기 바랍니다."""

    def _format_recruitment_response(self, context: str) -> str:
        """모집 공지 응답"""
        return f"""📢 **모집 안내**

{context}

신청 및 문의는 담당 부서로 연락하시기 바랍니다."""

    def _format_scholarship_response(self, context: str) -> str:
        """장학금 관련 응답"""
        return f"""💰 **장학금 안내**

{context}

장학금 관련 자세한 문의는 학생지원센터나 해당 담당 부서로 연락하시기 바랍니다."""

    def _format_facility_response(self, context: str) -> str:
        """시설 관련 응답"""
        return f"""🏢 **시설 안내**

{context}

시설 이용에 관한 자세한 정보는 해당 시설 담당자나 관리사무소에 문의하시기 바랍니다."""

    def _format_general_response(self, context: str) -> str:
        """일반 응답"""
        return f"""📋 **안내사항**

{context}

추가 문의사항은 해당 담당 부서나 학생지원센터로 연락하시기 바랍니다."""

    def get_query_category(self, question: str) -> str:
        """
        AWS Bedrock Claude 3.5 Sonnet을 사용하여 질문을 카테고리로 분류합니다.
        API 문제 시 키워드 기반 분류 사용
        
        Args:
            question: 분류할 질문
            
        Returns:
            카테고리 문자열 ('academic', 'scholarship', 'facilities', 'career', 'other')
        """
        if not self.bedrock:
            print("[WARNING] Bedrock client not available, using keyword-based classification")
            return self._classify_by_keywords(question)
        
        print(f"--- [LLM Service] Classifying question: '{question[:50]}...' ---")
        
        prompt = f"""다음 질문을 아래 카테고리 중 하나로 정확히 분류해주세요.

카테고리:
- academic: 학사 관련 (수강신청, 시험, 학점, 성적, 졸업요건, 휴학, 복학, 학적 변동 등)
- scholarship: 장학금 관련 (국가장학금, 교내장학금, 근로장학금, 신청방법, 자격요건 등)
- facilities: 시설 관련 (도서관, 기숙사, 식당, 체육시설, 강의실, 주차장 등)
- career: 진로 관련 (취업, 인턴십, 창업지원, 진로상담, 자격증, 대학원 진학 등)
- other: 기타 (위 카테고리에 해당하지 않는 모든 것)

질문: {question}

위 질문이 어느 카테고리에 해당하는지 영어 단어 하나만 답해주세요:"""

        try:
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 20,
                "messages": [
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                "temperature": 0.1  # 일관된 분류를 위해 매우 낮은 온도
            })
            
            response = self.bedrock.invoke_model(
                body=body,
                modelId="anthropic.claude-3-5-sonnet-20241022-v2:0",
                accept="application/json",
                contentType="application/json"
            )
            
            response_body = json.loads(response.get("body").read())
            category = response_body["content"][0]["text"].strip().lower()
            
            # 유효한 카테고리인지 확인
            valid_categories = ["academic", "scholarship", "facilities", "career", "other"]
            if category in valid_categories:
                print(f"--- [LLM Service] Classified as: {category} ---")
                return category
            else:
                print(f"--- [LLM Service] Invalid category '{category}', defaulting to keyword classification ---")
                return self._classify_by_keywords(question)
                
        except Exception as e:
            print(f"[ERROR] Failed to classify question: {e}")
            print("[INFO] Falling back to keyword-based classification")
            return self._classify_by_keywords(question)

    def _classify_by_keywords(self, question: str) -> str:
        """
        키워드 기반 질문 분류 (API 문제 시 fallback)
        """
        question_lower = question.lower()
        
        # 키워드 기반 분류 규칙
        career_keywords = ["진로", "취업", "인턴", "채용", "면접", "이력서", "자소서", "경진대회", "창업", "대학원"]
        scholarship_keywords = ["장학", "학비", "등록금", "지원금", "근로"]
        academic_keywords = ["수강", "학사", "성적", "학점", "졸업", "시험", "과목", "휴학", "복학", "학적"]
        facility_keywords = ["시설", "기숙사", "식당", "도서관", "체육", "강의실", "주차", "건물"]
        
        # 각 카테고리별 키워드 매치 점수 계산
        scores = {
            "career": sum(1 for keyword in career_keywords if keyword in question_lower),
            "scholarship": sum(1 for keyword in scholarship_keywords if keyword in question_lower),
            "academic": sum(1 for keyword in academic_keywords if keyword in question_lower),
            "facilities": sum(1 for keyword in facility_keywords if keyword in question_lower)
        }
        
        # 가장 높은 점수의 카테고리 선택
        max_score = max(scores.values())
        if max_score > 0:
            for category, score in scores.items():
                if score == max_score:
                    return category
        
        return "other"

    def upload_to_s3(self, file_content: bytes, bucket_name: str, object_key: str) -> Optional[str]:
        """
        S3에 파일 업로드
        
        Args:
            file_content: 업로드할 파일 내용
            bucket_name: S3 버킷 이름
            object_key: S3 객체 키
            
        Returns:
            업로드된 파일의 S3 URL 또는 None
        """
        if not self.s3_client:
            print("[WARNING] S3 client not available")
            return None
        
        try:
            self.s3_client.put_object(
                Bucket=bucket_name,
                Key=object_key,
                Body=file_content
            )
            
            s3_url = f"https://{bucket_name}.s3.{os.getenv('AWS_REGION', 'us-west-1')}.amazonaws.com/{object_key}"
            print(f"[INFO] File uploaded to S3: {s3_url}")
            return s3_url
            
        except Exception as e:
            print(f"[ERROR] Failed to upload to S3: {e}")
            return None

    def get_system_status(self) -> Dict[str, bool]:
        """
        시스템 상태 확인
        
        Returns:
            각 서비스의 상태 딕셔너리
        """
        return {
            "bedrock_available": self.bedrock is not None,
            "s3_available": self.s3_client is not None,
            "embedding_service": False,  # 현재 비활성화
            "chat_service": self.bedrock is not None
        }

# 전역 인스턴스 생성 (싱글톤 패턴)
llm_service = LLMService()

# 기존 함수들을 유지하여 하위 호환성 보장
def get_embeddings(texts: List[str]) -> Optional[List[List[float]]]:
    return llm_service.get_embeddings(texts)

def get_chat_response(context: str, question: str) -> str:
    return llm_service.get_chat_response(context, question)

def get_query_category(question: str) -> str:
    return llm_service.get_query_category(question)

def upload_to_s3(file_content: bytes, bucket_name: str, object_key: str) -> Optional[str]:
    return llm_service.upload_to_s3(file_content, bucket_name, object_key)

def get_system_status() -> Dict[str, bool]:
    return llm_service.get_system_status()

if __name__ == "__main__":
    # 테스트 코드
    print("=== LLM Service Test ===")
    
    # 시스템 상태 확인
    status = get_system_status()
    print(f"System status: {status}")
    
    # 카테고리 분류 테스트
    test_questions = [
        "진로로드맵 경진대회에 대해 알려주세요",
        "국가장학금 신청은 언제 하나요?",
        "도서관 24시간 이용 가능한가요?",
        "졸업요건 확인하는 방법은?",
        "취업박람회 일정이 궁금해요",
        "오늘 날씨는 어때요?"
    ]
    
    for q in test_questions:
        category = get_query_category(q)
        print(f"'{q}' -> {category}")
    
    # 답변 생성 테스트
    test_context = """[학생취업처] 2025학년도 진로로드맵 경진대회 안내
안녕하세요,학생취업처에서 진로로드맵 경진대회에 대해 안내해드립니다 ! 나 의 강점과 약점을 분석하고 개선방향, 목표 설정, 목표 달성을 위한 계획까지 경험해 볼 수 있는 기회! 진로로드맵이 무엇인지, 어떻게 작성하는지 몰라도 괜찮아요!"""
    
    test_question = "진로로드맵 경진대회는 무엇인가요?"
    answer = get_chat_response(test_context, test_question)
    print(f"Answer: {answer}")