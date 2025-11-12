import boto3
import json
from typing import List

bedrock_runtime = boto3.client(
    service_name="bedrock-runtime", 
    region_name="us-east-1"
)

def get_embeddings(texts: List[str]) -> List[List[float]]:
    # ... (existing function)
    embeddings = []
    for text in texts:
        body = json.dumps({"inputText": text})
        try:
            response = bedrock_runtime.invoke_model(
                body=body, 
                modelId="amazon.titan-embed-text-v1",
                accept="application/json", 
                contentType="application/json"
            )
            response_body = json.loads(response.get("body").read())
            embedding = response_body.get("embedding")
            embeddings.append(embedding)
        except Exception as e:
            print(f"Error generating embedding for text: '{text[:50]}...': {e}")
            continue
    return embeddings

def get_chat_response(context: str, question: str) -> str:
    # ... (existing function)
    print("--- [LLM Service] Generating final answer from Claude 3 Sonnet... ---")
    prompt = f"""Human: You are a helpful university administration assistant chatbot.
    Based on the following context, please provide a clear and concise answer to the user's question.
    If the context does not contain the answer, say that you don't have enough information.

    Context:
    {context}

    Question:
    {question}

    Assistant:"""
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31", "max_tokens": 2048,
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
    })
    try:
        response = bedrock_runtime.invoke_model(
            body=body, modelId="anthropic.claude-3-sonnet-20240229-v1:0",
            accept="application/json", contentType="application/json")
        response_body = json.loads(response.get("body").read())
        answer = response_body.get("content")[0].get("text")
        print(f"--- [LLM Service] Successfully generated answer. ---")
        return answer
    except Exception as e:
        print(f"Error generating chat response: {e}")
        return "Sorry, I encountered an error while generating a response."

def get_query_category(question: str) -> str:
    """
    Uses a generative LLM to classify the user's question into a predefined category.
    """
    print(f"--- [LLM Service] Classifying question: '{question}' ---")
    
    categories = ["academics", "scholarship", "facilities", "admission", "other"]
    
    prompt = f"""Human: You are a text classification assistant.
    Classify the following user question into one of these categories: {', '.join(categories)}.
    Respond with only the category name and nothing else.

    Question:
    {question}

    Assistant:"""

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31", "max_tokens": 10,
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
    })

    try:
        response = bedrock_runtime.invoke_model(
            body=body, modelId="anthropic.claude-3-sonnet-20240229-v1:0",
            accept="application/json", contentType="application/json")
        response_body = json.loads(response.get("body").read())
        category = response_body.get("content")[0].get("text").strip().lower()
        
        if category in categories:
            print(f"--- [LLM Service] Classified question as: {category} ---")
            return category
        else:
            print(f"--- [LLM Service] Classification failed or returned invalid category: '{category}'. Defaulting to 'other'. ---")
            return "other"
    except Exception as e:
        print(f"Error classifying question: {e}")
        return "other"