import streamlit as st
from datetime import datetime
import time

# 리팩토링된 모듈 import
from config import settings
from database import (
    init_postgresql_vectorstore, init_pgvector, get_schools_list, get_school_stats,
    get_file_metadata, add_rss_feed, get_rss_feeds, delete_rss_feed,
    delete_document_from_db, get_school_code_by_id, find_relevant_department
)
from aws_utils import (
    init_aws_clients, upload_to_s3, delete_file_from_s3
)
from chatbot_logic import (
    search_documents, generate_ai_response, get_relevance_indicator
)

# --- UI 렌더링 함수 ---

def render_school_selector(engine):
    """학교 선택 UI를 렌더링하고 선택된 학교 ID와 이름을 반환합니다."""
    schools = get_schools_list(engine)
    if not schools:
        st.error("학교 목록을 불러올 수 없습니다.")
        return None, None

    if 'selected_school' not in st.session_state or st.session_state.selected_school not in schools:
        st.session_state.selected_school = list(schools.keys())[0]

    selected_school_name = st.selectbox(
        "🏫 학교 선택",
        options=list(schools.keys()),
        index=list(schools.keys()).index(st.session_state.selected_school),
        key="school_selector"
    )

    if selected_school_name != st.session_state.selected_school:
        st.session_state.selected_school = selected_school_name
        st.session_state.rss_url_input = ""
        st.rerun()

    school_id = schools[selected_school_name]
    st.info(f"📚 현재 선택: **{selected_school_name}** (ID: {school_id})")
    return school_id, selected_school_name

def display_search_results(search_results):
    """검색 결과를 Streamlit UI에 표시합니다."""
    if not search_results:
        return

    st.write(f"🎯 **검색 결과: {len(search_results)}개 관련 항목 발견**")
    
    for i, doc in enumerate(search_results, 1):
        score = doc.metadata.get('relevance_score', 0.0)
        indicator, level, _ = get_relevance_indicator(score)
        
        with st.expander(f"{indicator} **항목 {i}**: {doc.metadata.get('title', '제목 없음')} | 관련성: {score:.1%} ({level})"):
            st.write(f"**📅 날짜**: {doc.metadata.get('date', 'N/A')}")
            st.write(f"**📂 출처**: {doc.metadata.get('filename', 'N/A')}")
            st.write("**📄 내용**:")
            preview = doc.page_content[:300] + "..." if len(doc.page_content) > 300 else doc.page_content
            st.text(preview)

# --- 메인 애플리케이션 ---

def main():
    st.set_page_config(page_title="학사 정보 검색 시스템", page_icon="🔍", layout="wide")
    st.title("🔍 ClassMATE")
    st.caption("당신의 학교에 궁금한 점을 무엇이든 물어보세요!")

    # --- 초기화 ---
    engine = init_postgresql_vectorstore()
    bedrock_client, embeddings, s3_client = init_aws_clients()

    if not engine or not bedrock_client:
        st.error("시스템 초기화에 실패했습니다. 설정을 확인해주세요.")
        return

    # --- UI ---
    school_id, selected_school = render_school_selector(engine)
    if not school_id:
        return

    stats = get_school_stats(engine, school_id)
    col1, col2, col3 = st.columns(3)
    col1.metric("📄 총 문서", stats["total_documents"])
    col2.metric("✅ 처리 완료", stats["processed_documents"])
    col3.metric("📊 총 청크", stats["total_chunks"])
    st.divider()

    vectorstore = init_pgvector(embeddings, engine)
    
    tab1, tab2, tab3, tab4 = st.tabs(["💬 챗봇", "📄 PDF 관리", "🔗 RSS 피드 관리", "📊 파일 통계"])

    # 탭 1: 챗봇
    with tab1:
        st.header(f"💬 {selected_school} 학사 정보 챗봇")
        search_query = st.text_input("궁금한 내용을 입력하세요:", placeholder="예: 장학금 신청 방법", key=f"query_{school_id}")

        if search_query:
            with st.spinner("문서 검색 및 AI 답변 생성 중..."):
                results = search_documents(engine, vectorstore, search_query, school_id, embeddings)
                
                if results:
                    display_search_results(results)
                    st.write("---")
                    ai_response = generate_ai_response(bedrock_client, search_query, results)
                    st.subheader("🤖 AI 응답")
                    st.markdown(ai_response)
                else:
                    department = find_relevant_department(engine, search_query, school_id)
                    if department:
                        st.info("📞 담당 부서 안내")
                        contact_info = f"**{department['name']}** ({department.get('staff_name', '담당자')})\n- 전화번호: {department.get('staff_phone') or department.get('main_phone', '정보 없음')}\n- 이메일: {department.get('staff_email', '정보 없음')}"
                        st.markdown(f"관련 문서를 찾지 못했습니다. **'{search_query}'** 관련 업무는 아래 부서로 문의하시면 정확한 답변을 받으실 수 있습니다.\n\n{contact_info}")
                    else:
                        st.warning("관련 문서를 찾을 수 없습니다. 학교 대표 부서나 홈페이지를 통해 문의해주세요.")

    # 탭 2: PDF 관리
    with tab2:
        st.header("📄 PDF 파일 업로드 및 관리")
        uploaded_file = st.file_uploader("PDF 파일을 선택하세요", type=['pdf'], key=f"uploader_{school_id}")
        
        if uploaded_file:
            school_code = get_school_code_by_id(engine, school_id)
            s3_key = f"documents/{school_code}/{datetime.now().strftime('%Y%m%d')}_{uploaded_file.name}"
            if st.button("업로드", key=f"upload_btn_{uploaded_file.name}"):
                if upload_to_s3(uploaded_file, s3_client, s3_key):
                    from database import save_file_metadata
                    save_file_metadata(engine, uploaded_file.name, s3_key, "pdf", school_id)
                    st.success(f"✅ '{uploaded_file.name}' 업로드 완료! Lambda에 의해 자동 처리됩니다.")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("S3 업로드 실패")

        st.divider()
        st.subheader("📂 업로드된 파일 목록")
        file_metadata = get_file_metadata(engine, school_id)
        if not file_metadata.empty:
            for idx, row in file_metadata.iterrows():
                cols = st.columns([0.5, 0.2, 0.2, 0.1])
                cols[0].text(row['filename'])
                cols[1].text('✅ 처리완료' if row['processed'] else '⏳ 미처리')
                cols[2].text(f"{int(row['chunks_count'])} 청크")
                if cols[3].button("삭제", key=f"del_pdf_{row['id']}", type="primary"):
                    s3_key_to_delete = row['s3_key'].replace(f"s3://{settings.S3_BUCKET_NAME}/", "")
                    delete_file_from_s3(s3_client, s3_key_to_delete)
                    delete_document_from_db(engine, row['id'])
                    st.success(f"'{row['filename']}' 삭제 완료")
                    st.rerun()
        else:
            st.info("업로드된 PDF 파일이 없습니다.")

    # 탭 3: RSS 피드 관리
    with tab3:
        st.header("🔗 RSS 피드 추가 및 관리")
        rss_url = st.text_input("추가할 RSS 피드 URL을 입력하세요:", key=f"rss_url_{school_id}")
        if st.button("➕ RSS 추가", disabled=not rss_url):
            if add_rss_feed(engine, school_id, rss_url):
                st.success("RSS 피드 추가 완료!")
                st.rerun()
            else:
                st.warning("이미 등록된 피드이거나 추가에 실패했습니다.")

        st.divider()
        st.subheader("📡 등록된 RSS 피드 목록")
        rss_feeds = get_rss_feeds(engine, school_id)
        if not rss_feeds.empty:
            for idx, row in rss_feeds.iterrows():
                cols = st.columns([0.6, 0.3, 0.1])
                cols[0].text(row['title'] or row['rss_url'])
                cols[1].text(f"상태: {'✅' if row['status']=='active' else '⏸️'}")
                if cols[2].button("삭제", key=f"del_rss_{row['id']}", type="primary"):
                    delete_rss_feed(engine, row['id'])
                    st.success(f"'{row['title']}' 피드 삭제 완료")
                    st.rerun()
        else:
            st.info("등록된 RSS 피드가 없습니다.")
            
    # 탭 4: 파일 통계 (구현 예정)
    with tab4:
        st.header("📊 파일 통계")
        st.info("이 기능은 현재 개발 중입니다.")
        # 여기에 통계 관련 UI 및 로직 추가 예정

if __name__ == "__main__":
    main()
