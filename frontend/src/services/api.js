/**
 * API 통신 서비스
 * 백엔드 FastAPI와의 HTTP 통신 관리
 */

import axios from 'axios';

// API 기본 URL (환경변수로 관리)
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// Axios 인스턴스 생성
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 요청 인터셉터 (필요시 인증 토큰 추가 등)
apiClient.interceptors.request.use(
  (config) => {
    // TODO: 인증이 필요한 경우 토큰 추가
    // const token = localStorage.getItem('token');
    // if (token) {
    //   config.headers.Authorization = `Bearer ${token}`;
    // }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 응답 인터셉터 (에러 핸들링)
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      // 서버가 응답을 반환한 경우
      console.error('API Error:', error.response.data);
    } else if (error.request) {
      // 요청은 보냈지만 응답이 없는 경우
      console.error('No response from server');
    } else {
      // 요청 설정 중 에러 발생
      console.error('Request setup error:', error.message);
    }
    return Promise.reject(error);
  }
);

/**
 * 챗봇 API
 */
export const chatAPI = {
  /**
   * 질문 전송 및 답변 받기
   */
  sendQuery: async (schoolId, query, sessionId = null) => {
    try {
      const response = await apiClient.post('/api/chat/query', {
        school_id: schoolId,
        query: query,
        session_id: sessionId,
      });
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  /**
   * 대화 이력 조회
   */
  getHistory: async (sessionId) => {
    try {
      const response = await apiClient.get(`/api/chat/history/${sessionId}`);
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  /**
   * 피드백 제출
   */
  submitFeedback: async (sessionId, messageId, rating, comment = null) => {
    try {
      const response = await apiClient.post('/api/chat/feedback', {
        session_id: sessionId,
        message_id: messageId,
        rating: rating,
        comment: comment,
      });
      return response.data;
    } catch (error) {
      throw error;
    }
  },
};

/**
 * 관리자 API
 */
export const adminAPI = {
  /**
   * 문서 업로드
   */
  uploadDocument: async (file, metadata) => {
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('title', metadata.title);
      formData.append('category', metadata.category);
      formData.append('department', metadata.department);
      formData.append('contact', metadata.contact);
      formData.append('school_id', metadata.schoolId);

      const response = await apiClient.post('/api/admin/document', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  /**
   * 문서 목록 조회
   */
  getDocuments: async (schoolId, category = null, skip = 0, limit = 20) => {
    try {
      const params = { school_id: schoolId, skip, limit };
      if (category) params.category = category;

      const response = await apiClient.get('/api/admin/documents', { params });
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  /**
   * 문서 삭제
   */
  deleteDocument: async (documentId, schoolId) => {
    try {
      const response = await apiClient.delete(`/api/admin/document/${documentId}`, {
        params: { school_id: schoolId },
      });
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  /**
   * RSS 피드 추가
   */
  addRSSFeed: async (feedData) => {
    try {
      const formData = new FormData();
      formData.append('school_id', feedData.schoolId);
      formData.append('feed_url', feedData.feedUrl);
      formData.append('category', feedData.category);
      formData.append('department', feedData.department);
      formData.append('contact', feedData.contact);

      const response = await apiClient.post('/api/admin/rss', formData);
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  /**
   * RSS 피드 목록 조회
   */
  getRSSFeeds: async (schoolId) => {
    try {
      const response = await apiClient.get('/api/admin/rss', {
        params: { school_id: schoolId },
      });
      return response.data;
    } catch (error) {
      throw error;
    }
  },
};

export default apiClient;
