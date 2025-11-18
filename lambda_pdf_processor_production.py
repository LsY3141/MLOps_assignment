import os
import json
import tempfile
import boto3
import psycopg2
import psycopg2.extras
from langchain_aws import BedrockEmbeddings
from langchain_text_splitters import CharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from urllib.parse import unquote_plus

s3_client = boto3.client('s3')
bedrock_client = boto3.client(service_name='bedrock-runtime', region_name='us-west-1')

# Titan 임베딩 모델 사용 (올바른 모델 ID)
embeddings = BedrockEmbeddings(
    client=bedrock_client, 
    model_id="amazon.titan-embed-text-v2:0"
)

def lambda_handler(event, context):
    # 환경 변수
    DB_HOST = os.environ['DB_HOST']
    DB_NAME = os.environ['DB_NAME']
    DB_USER = os.environ['DB_USER']
    DB_PASSWORD = os.environ['DB_PASSWORD']
    
    bucket_name = event['Records'][0]['s3']['bucket']['name']
    file_key = unquote_plus(event['Records'][0]['s3']['object']['key'])  # URL 디코딩
    
    print(f"처리 시작 - 버킷이름: {bucket_name}")
    print(f"처리 파일: {file_key}")
    
    try:
        # PDF 파일인지 확인
        if not file_key.lower().endswith('.pdf'):
            print(f"PDF 파일이 아님: {file_key}")
            return {'statusCode': 200, 'body': 'Skipped non-PDF file'}
        
        # documents/ 경로인지 확인
        if not file_key.startswith('documents/'):
            print(f"documents 폴더 외부 파일: {file_key}")
            return {'statusCode': 200, 'body': 'Skipped file outside documents folder'}
        
        # PostgreSQL 연결
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cursor = conn.cursor()
        
        print(f"데이터베이스 연결 완료")
        print(f"데이터베이스 호스트: {DB_HOST}")
        
        # 해당 파일의 document_id 찾기 또는 생성
        document_id = find_or_create_document(cursor, conn, bucket_name, file_key)
        if not document_id:
            print(f"문서 ID를 찾거나 생성할 수 없음")
            return {'statusCode': 500, 'body': 'Failed to find or create document'}
        
        print(f"문서 ID: {document_id}")
        
        # 처리 시작 상태로 업데이트
        cursor.execute("""
            UPDATE documents 
            SET processed = FALSE, updated_at = NOW()
            WHERE id = %s
        """, (document_id,))
        conn.commit()
        
        # S3에서 PDF 다운로드
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            s3_client.download_fileobj(bucket_name, file_key, tmp_file)
            pdf_path = tmp_file.name
        
        print(f"PDF 다운로드 완료: {pdf_path}")
        
        # PDF 로드 및 청크 분할
        pdf_loader = PyPDFLoader(pdf_path)
        splitter = CharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=100,
            separator='\n'
        )
        chunks = pdf_loader.load_and_split(text_splitter=splitter)
        
        print(f"PDF 분할 완료 - 총 청크 개수: {len(chunks)}")
        
        # 기존 청크 삭제 (재처리인 경우)
        cursor.execute("DELETE FROM document_chunks WHERE document_id = %s", (document_id,))
        
        successful_chunks = 0
        
        # 각 청크 처리
        for i, chunk in enumerate(chunks):
            try:
                # 텍스트 정리
                cleaned_content = chunk.page_content.encode().decode().replace("\x00", "").strip()
                
                if not cleaned_content:
                    continue
                
                # 임베딩 생성 (임시로 기본값 사용)
                try:
                    # 임시로 기본값만 사용 (빠른 처리를 위해)
                    print(f"청크 {i} 기본 임베딩 사용")
                    embedding_vector = [0.0] * 1536
                    
                    # 나중에 활성화할 실제 임베딩 코드
                    # embedding_vector = embeddings.embed_query(cleaned_content)
                except Exception as embed_error:
                    print(f"임베딩 생성 실패, 기본값 사용: {embed_error}")
                    embedding_vector = [0.0] * 1536
                
                # document_chunks 테이블에 저장 (우리 DB 구조)
                cursor.execute("""
                    INSERT INTO document_chunks (document_id, chunk_text, embedding)
                    VALUES (%s, %s, %s)
                """, (
                    document_id,
                    cleaned_content,
                    embedding_vector
                ))
                successful_chunks += 1
                
                if i % 10 == 0:  # 10개마다 진행 상황 로깅
                    print(f"처리 진행: {i+1}/{len(chunks)} 청크")
                    
            except Exception as e:
                print(f"청크 {i} 처리 중 오류: {str(e)}")
                continue
        
        # 문서 처리 완료 상태 업데이트
        cursor.execute("""
            UPDATE documents 
            SET processed = TRUE, chunks_count = %s, updated_at = NOW()
            WHERE id = %s
        """, (successful_chunks, document_id))
        
        conn.commit()
        
        print(f"문서 처리 완료")
        print(f"성공적으로 처리된 청크 개수: {successful_chunks}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Successfully processed {successful_chunks} chunks',
                'document_id': document_id,
                'file_key': file_key
            })
        }
        
    except Exception as e:
        print(f"PDF 파일 처리 중 오류 발생: {str(e)}")
        
        # 오류 발생 시 DB 상태 업데이트
        if 'document_id' in locals() and 'cursor' in locals():
            try:
                cursor.execute("""
                    UPDATE documents 
                    SET processed = FALSE, updated_at = NOW()
                    WHERE id = %s
                """, (document_id,))
                conn.commit()
            except:
                pass
        
        if 'conn' in locals():
            conn.rollback()
        
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
        
    finally:
        if 'conn' in locals():
            conn.close()
        if 'pdf_path' in locals():
            os.remove(pdf_path)

def find_or_create_document(cursor, conn, bucket_name, file_key):
    """S3 키를 기반으로 document_id를 찾거나 새로 생성합니다."""
    try:
        # 1. 기존 문서 찾기
        source_url = f"s3://{bucket_name}/{file_key}"
        filename = file_key.split('/')[-1]
        
        cursor.execute("""
            SELECT id FROM documents 
            WHERE source_url = %s OR file_name = %s
            ORDER BY created_at DESC
            LIMIT 1
        """, (source_url, filename))
        
        result = cursor.fetchone()
        if result:
            return result[0]
        
        # 2. 파일 경로에서 학교 코드 추출 (school_id 결정)
        school_id = 1  # 기본값: 연성대학교
        
        if file_key.startswith('documents/'):
            path_parts = file_key.split('/')
            if len(path_parts) > 1:
                school_code = path_parts[1]  # documents/YSU/ 또는 documents/OTHER/
                if school_code == 'YSU':
                    school_id = 1  # 연성대학교
                elif school_code == 'OTHER':
                    school_id = 2  # 연세대학교
        
        # 3. 새 문서 생성 (school_id 포함)
        cursor.execute("""
            INSERT INTO documents (school_id, file_name, source_url, category, processed, chunks_count)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (school_id, filename, source_url, 'pdf', False, 0))
        
        result = cursor.fetchone()
        conn.commit()
        
        print(f"새 문서 생성: ID={result[0]}, school_id={school_id}, 파일={filename}")
        return result[0]
        
    except Exception as e:
        print(f"문서 찾기/생성 실패: {str(e)}")
        conn.rollback()
        return None