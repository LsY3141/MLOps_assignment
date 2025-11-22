#!/usr/bin/env python3
"""
AWS Bedrock에서 사용 가능한 임베딩 모델을 확인하는 디버깅 스크립트
"""
import boto3
import json
from config import settings

def check_bedrock_models():
    """사용 가능한 Bedrock 모델 목록을 확인합니다."""
    print(f"🔍 AWS 리전: {settings.AWS_REGION}")
    print("=" * 80)

    try:
        # Bedrock 클라이언트 생성
        bedrock_client = boto3.client("bedrock", region_name=settings.AWS_REGION)

        # 모든 foundation 모델 조회
        response = bedrock_client.list_foundation_models()

        print("\n📊 사용 가능한 임베딩 모델:")
        print("-" * 80)

        embedding_models = []
        for model in response['modelSummaries']:
            # 임베딩 모델만 필터링 (outputModalities에 'EMBEDDING'이 있는 경우)
            if 'EMBEDDING' in model.get('outputModalities', []):
                embedding_models.append(model)
                print(f"\n✅ 모델 ID: {model['modelId']}")
                print(f"   이름: {model['modelName']}")
                print(f"   제공자: {model['providerName']}")
                if 'inferenceTypesSupported' in model:
                    print(f"   지원 추론 타입: {', '.join(model['inferenceTypesSupported'])}")

        print("\n" + "=" * 80)
        print(f"📈 총 {len(embedding_models)}개의 임베딩 모델을 사용할 수 있습니다.")

        # Cohere 모델만 별도로 표시
        print("\n🔵 Cohere 임베딩 모델:")
        print("-" * 80)
        cohere_models = [m for m in embedding_models if 'cohere' in m['modelId'].lower()]
        for model in cohere_models:
            print(f"  • {model['modelId']} - {model['modelName']}")

        # Titan 모델만 별도로 표시
        print("\n🟠 Amazon Titan 임베딩 모델:")
        print("-" * 80)
        titan_models = [m for m in embedding_models if 'titan' in model['modelId'].lower() and 'embed' in model['modelId'].lower()]
        for model in titan_models:
            print(f"  • {model['modelId']} - {model['modelName']}")

    except Exception as e:
        print(f"❌ 오류 발생: {str(e)}")
        print("\n💡 가능한 원인:")
        print("  1. IAM 역할에 bedrock:ListFoundationModels 권한이 없음")
        print("  2. 리전 설정이 잘못됨")
        print("  3. Bedrock 서비스에 접근할 수 없음")

def test_embedding_model(model_id):
    """특정 모델로 임베딩 테스트를 수행합니다."""
    print(f"\n🧪 모델 테스트: {model_id}")
    print("=" * 80)

    try:
        from langchain_aws import BedrockEmbeddings

        bedrock_runtime_client = boto3.client("bedrock-runtime", region_name=settings.AWS_REGION)

        embeddings = BedrockEmbeddings(
            client=bedrock_runtime_client,
            region_name=settings.AWS_REGION,
            model_id=model_id
        )

        # 간단한 텍스트로 임베딩 테스트
        test_text = "안녕하세요, 테스트입니다."
        result = embeddings.embed_query(test_text)

        print(f"✅ 성공! 임베딩 차원: {len(result)}")
        print(f"   첫 5개 값: {result[:5]}")
        return True

    except Exception as e:
        print(f"❌ 실패: {str(e)}")
        return False

if __name__ == "__main__":
    print("🚀 AWS Bedrock 모델 디버깅 스크립트")
    print("=" * 80)

    # 1. 사용 가능한 모델 목록 확인
    check_bedrock_models()

    # 2. 여러 모델 ID로 테스트
    print("\n\n🧪 임베딩 모델 테스트")
    print("=" * 80)

    test_models = [
        "cohere.embed-multilingual-v3",
        "cohere.embed-english-v3",
        "amazon.titan-embed-text-v1",
        "amazon.titan-embed-text-v2:0",
    ]

    print("\n다음 모델들을 테스트합니다:")
    for model in test_models:
        print(f"  • {model}")

    print("\n" + "-" * 80)

    successful_models = []
    for model_id in test_models:
        if test_embedding_model(model_id):
            successful_models.append(model_id)

    print("\n\n📋 테스트 결과 요약")
    print("=" * 80)
    print(f"✅ 성공한 모델 ({len(successful_models)}개):")
    for model in successful_models:
        print(f"  • {model}")

    if successful_models:
        print(f"\n💡 권장: aws_utils.py에서 다음 모델을 사용하세요:")
        print(f"   model_id=\"{successful_models[0]}\"")
    else:
        print("\n⚠️  모든 모델 테스트 실패")
        print("   AWS Bedrock 콘솔에서 Model Access를 확인하세요:")
        print(f"   https://console.aws.amazon.com/bedrock/home?region={settings.AWS_REGION}#/modelaccess")
