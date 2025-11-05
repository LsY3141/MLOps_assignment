"""
AWS Lambda - RSS 자동 크롤링 함수
매일 오전 6시에 EventBridge로 트리거됨
"""

import json
import os
import boto3
import feedparser
import psycopg2
from datetime import datetime
from typing import List, Dict, Any

# 환경 변수
DB_HOST = os.environ.get('DB_HOST')
DB_NAME = os.environ.get('DB_NAME')
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
API_ENDPOINT = os.environ.get('API_ENDPOINT')  # EC2 FastAPI 엔드포인트

def lambda_handler(event, context):
    """
    Lambda 핸들러 함수
    
    Args:
        event: EventBridge 이벤트
        context: Lambda 컨텍스트
        
    Returns:
        처리 결과
    """
    print(f"RSS 크롤링 시작: {datetime.utcnow().isoformat()}")
    
    try:
        # 1. DB에서 활성화된 RSS 피드 목록 조회
        rss_feeds = get_active_rss_feeds()
        print(f"활성 RSS 피드 수: {len(rss_feeds)}")
        
        if not rss_feeds:
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': '활성화된 RSS 피드가 없습니다.',
                    'processed': 0
                })
            }
        
        # 2. 각 피드 처리
        total_new_items = 0
        for feed in rss_feeds:
            new_items = process_rss_feed(feed)
            total_new_items += new_items
            print(f"피드 {feed['id']}: {new_items}개 신규 항목 처리")
        
        # 3. 결과 반환
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'RSS 크롤링 완료',
                'feeds_processed': len(rss_feeds),
                'new_items': total_new_items,
                'timestamp': datetime.utcnow().isoformat()
            })
        }
        
    except Exception as e:
        print(f"오류 발생: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }


def get_active_rss_feeds() -> List[Dict[str, Any]]:
    """
    DB에서 활성화된 RSS 피드 목록 조회
    
    Returns:
        RSS 피드 리스트
    """
    conn = None
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, school_id, feed_url, category, department, contact
            FROM rss_feeds
            WHERE is_active = 1
        """)
        
        rows = cursor.fetchall()
        
        feeds = []
        for row in rows:
            feeds.append({
                'id': row[0],
                'school_id': row[1],
                'feed_url': row[2],
                'category': row[3],
                'department': row[4],
                'contact': row[5]
            })
        
        cursor.close()
        return feeds
        
    except Exception as e:
        print(f"DB 조회 오류: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()


def process_rss_feed(feed: Dict[str, Any]) -> int:
    """
    개별 RSS 피드 처리
    
    Args:
        feed: RSS 피드 정보
        
    Returns:
        처리된 신규 항목 수
    """
    try:
        # 1. RSS 피드 파싱
        parsed_feed = feedparser.parse(feed['feed_url'])
        
        if not parsed_feed.entries:
            print(f"피드 {feed['id']}: 항목 없음")
            return 0
        
        # 2. 신규 항목 필터링
        new_entries = filter_new_entries(parsed_feed.entries, feed['school_id'])
        
        if not new_entries:
            print(f"피드 {feed['id']}: 신규 항목 없음")
            return 0
        
        # 3. EC2 API로 신규 항목 전송
        for entry in new_entries:
            send_to_api(entry, feed)
        
        # 4. 마지막 크롤링 시간 업데이트
        update_last_crawled(feed['id'])
        
        return len(new_entries)
        
    except Exception as e:
        print(f"피드 {feed['id']} 처리 오류: {str(e)}")
        return 0


def filter_new_entries(entries: List[Any], school_id: str) -> List[Dict[str, Any]]:
    """
    이미 존재하는 항목 필터링
    
    Args:
        entries: RSS 항목 리스트
        school_id: 학교 ID
        
    Returns:
        신규 항목 리스트
    """
    conn = None
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        
        cursor = conn.cursor()
        
        new_entries = []
        for entry in entries:
            entry_id = entry.get('id') or entry.get('link')
            
            # DB에 이미 존재하는지 확인
            cursor.execute("""
                SELECT COUNT(*)
                FROM documents
                WHERE school_id = %s AND source_url = %s
            """, (school_id, entry_id))
            
            count = cursor.fetchone()[0]
            
            if count == 0:
                new_entries.append({
                    'id': entry_id,
                    'title': entry.get('title', '제목 없음'),
                    'link': entry.get('link', ''),
                    'summary': entry.get('summary', ''),
                    'published': entry.get('published', '')
                })
        
        cursor.close()
        return new_entries
        
    except Exception as e:
        print(f"신규 항목 필터링 오류: {str(e)}")
        return []
    finally:
        if conn:
            conn.close()


def send_to_api(entry: Dict[str, Any], feed: Dict[str, Any]) -> None:
    """
    EC2 API로 신규 항목 전송
    
    Args:
        entry: RSS 항목
        feed: RSS 피드 정보
    """
    import requests
    
    try:
        payload = {
            'school_id': feed['school_id'],
            'title': entry['title'],
            'content': entry['summary'],
            'source_url': entry['link'],
            'category': feed['category'],
            'department': feed['department'],
            'contact': feed['contact']
        }
        
        response = requests.post(
            f"{API_ENDPOINT}/api/admin/rss/process",
            json=payload,
            timeout=30
        )
        
        response.raise_for_status()
        print(f"API 전송 성공: {entry['title']}")
        
    except Exception as e:
        print(f"API 전송 오류: {str(e)}")
        raise


def update_last_crawled(feed_id: int) -> None:
    """
    마지막 크롤링 시간 업데이트
    
    Args:
        feed_id: RSS 피드 ID
    """
    conn = None
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE rss_feeds
            SET last_crawled_at = %s
            WHERE id = %s
        """, (datetime.utcnow(), feed_id))
        
        conn.commit()
        cursor.close()
        
    except Exception as e:
        print(f"크롤링 시간 업데이트 오류: {str(e)}")
    finally:
        if conn:
            conn.close()
