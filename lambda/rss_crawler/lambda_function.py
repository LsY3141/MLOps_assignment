import feedparser
import json
import requests
import os
import re

BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000/api")

def parse_with_regex(text):
    print("--- Attempting fallback parsing with Regex ---")
    items = []
    # Find all <item> blocks
    item_blocks = re.findall(r'<item>(.*?)</item>', text, re.DOTALL)
    for block in item_blocks:
        title_match = re.search(r'<title>(.*?)</title>', block, re.DOTALL)
        link_match = re.search(r'<link>(.*?)</link>', block, re.DOTALL)
        description_match = re.search(r'<description>(.*?)</description>', block, re.DOTALL)
        
        title = title_match.group(1).strip() if title_match else ""
        link = link_match.group(1).strip() if link_match else ""
        # For description, also remove CDATA tags if they exist
        description = description_match.group(1).strip() if description_match else ""
        description = description.replace('<![CDATA[', '').replace(']]>', '')

        if title and link:
            items.append({'title': title, 'link': link, 'summary': description})
    return items

def lambda_handler(event, context):
    print(f"Received event: {event}")
    try:
        school_id, rss_url = event['school_id'], event['rss_url']
    except KeyError:
        return {'statusCode': 400, 'body': json.dumps('Error: Event must include "school_id" and "rss_url".')}

    print(f"Parsing RSS feed from: {rss_url}")
    feed = feedparser.parse(rss_url)

    entries = feed.entries
    if feed.bozo:
        print(f"Warning: feedparser reported non-well-formed feed. Exception: {feed.bozo_exception}")
        print("--- Attempting to fetch and parse manually ---")
        try:
            raw_content = requests.get(rss_url).text
            entries = parse_with_regex(raw_content)
        except Exception as e:
            print(f"Manual parsing also failed: {e}")
            return {'statusCode': 500, 'body': json.dumps("Failed to parse RSS feed with both methods.")}

    print(f"Found {len(entries)} entries.")
    
    new_entries_count = 0
    for entry in reversed(entries):
        source_url = entry.get("link")
        # The scraped link might be relative, so we need to build the full URL
        if source_url and not source_url.startswith('http'):
            base_url = "https://www.yeonsung.ac.kr" # Assuming this base URL
            source_url = base_url + source_url

        if not source_url:
            print(f"Skipping entry without a link: {entry.get('title')}")
            continue

        try:
            response = requests.get(f"{BACKEND_API_URL}/documents/by_source_url", params={"source_url": source_url}, timeout=5)
            if response.status_code == 200:
                print(f"Skipping existing entry: {source_url}")
                continue
        except requests.exceptions.RequestException as e:
            print(f"Error checking for document existence: {e}")
            continue

        print(f"Found new entry: {entry.get('title')}. Ingesting...")
        text_content = f"{entry.get('title')}\n\n{entry.get('summary', entry.get('description', ''))}"
        
        payload = {"school_id": school_id, "source_url": source_url, "category": "announcement", "text": text_content}
        
        try:
            ingest_response = requests.post(f"{BACKEND_API_URL}/documents/add_by_text", json=payload, timeout=30)
            if ingest_response.status_code == 201:
                new_entries_count += 1
                print(f"Successfully ingested: {entry.get('title')}")
            else:
                print(f"Failed to ingest: {entry.get('title')}. Status: {ingest_response.status_code}, Body: {ingest_response.text}")
        except requests.exceptions.RequestException as e:
            print(f"Error ingesting document: {e}")

    return {'statusCode': 200, 'body': json.dumps(f"Crawl complete. Found {len(entries)} entries, ingested {new_entries_count} new entries.")}

if __name__ == '__main__':
    test_event = {"school_id": 1, "rss_url": "https://www.yeonsung.ac.kr/bbs/ko/79/rssList.do?row=50"}
    result = lambda_handler(test_event, None)
    print("\n--- Lambda execution result ---")
    print(result)