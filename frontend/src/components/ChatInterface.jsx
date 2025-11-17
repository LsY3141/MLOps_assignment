/**
 * 챗봇 인터페이스 컴포넌트
 * 메인 채팅 화면 + 문서 업로드 모달
 */

import React, { useState, useRef, useEffect } from 'react';
import MessageBubble from './MessageBubble';
import { chatAPI } from '../services/api';
import axios from 'axios';

const ChatInterface = ({ schoolId = 1 }) => {
  const [messages, setMessages] = useState([
    {
      id: '0',
      role: 'assistant',
      content: '안녕하세요! 캠퍼스메이트입니다. 학사 행정과 관련된 궁금한 점을 편하게 물어보세요.',
      timestamp: new Date(),
    },
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId] = useState(() => `session_${Date.now()}`);
  const messagesEndRef = useRef(null);

  // 문서 업로드 모달 상태
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadCategory, setUploadCategory] = useState('academic');
  const [uploadDepartment, setUploadDepartment] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);

  const categories = [
    { value: 'academic', label: '학사' },
    { value: 'scholarship', label: '장학' },
    { value: 'facilities', label: '시설' },
    { value: 'career', label: '진로/취업' },
    { value: 'general', label: '일반' },
  ];

  // 메시지 목록 자동 스크롤
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // 질문 전송
  const handleSendMessage = async () => {
    const trimmedInput = inputValue.trim();
    if (!trimmedInput || isLoading) return;

    // 사용자 메시지 추가
    const userMessage = {
      id: `user_${Date.now()}`,
      role: 'user',
      content: trimmedInput,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);

    try {
      // API 호출
      const response = await chatAPI.sendQuery(schoolId, trimmedInput, sessionId);

      // AI 응답 메시지 추가
      const assistantMessage = {
        id: `assistant_${Date.now()}`,
        role: 'assistant',
        content: response.answer,
        responseType: response.response_type,
        sourceDocuments: response.source_documents,
        metadata: response.metadata,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      // 에러 메시지 표시
      const errorMessage = {
        id: `error_${Date.now()}`,
        role: 'assistant',
        content: '죄송합니다. 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요.',
        isError: true,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, errorMessage]);
      console.error('Chat error:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // Enter 키 처리
  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // 파일 선택
  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (!file) {
      setUploadFile(null);
      return;
    }

    if (!file.name.toLowerCase().endsWith('.pdf')) {
      alert('PDF 파일만 업로드 가능합니다.');
      setUploadFile(null);
      return;
    }

    if (file.size > 50 * 1024 * 1024) {
      alert('파일 크기는 50MB를 초과할 수 없습니다.');
      setUploadFile(null);
      return;
    }

    setUploadFile(file);
    setUploadResult(null);
  };

  // 문서 업로드
  const handleUpload = async () => {
    if (!uploadFile) return;

    try {
      setUploading(true);
      setUploadResult(null);

      // 1. Presigned URL 요청
      const { data: presignedData } = await axios.post(
        `${process.env.REACT_APP_API_URL || 'http://localhost:8000'}/api/documents/presigned-url`,
        {
          school_id: schoolId,
          category: uploadCategory,
          file_name: uploadFile.name,
          department: uploadDepartment || null,
        }
      );

      // 2. S3에 직접 업로드
      await axios.put(presignedData.upload_url, uploadFile, {
        headers: {
          'Content-Type': 'application/pdf',
        },
      });

      setUploadResult({
        success: true,
        message: '문서 업로드 완료! 자동으로 벡터화 처리 중입니다...',
      });

      // 폼 초기화
      setUploadFile(null);
      setUploadDepartment('');
      document.getElementById('file-upload-input').value = '';

      // 3초 후 모달 닫기
      setTimeout(() => {
        setShowUploadModal(false);
        setUploadResult(null);
      }, 3000);

    } catch (error) {
      console.error('Upload error:', error);
      setUploadResult({
        success: false,
        message: error.response?.data?.detail || '업로드 중 오류가 발생했습니다.',
      });
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-gradient-to-br from-blue-50 to-indigo-50">
      {/* 헤더 */}
      <div className="bg-gradient-to-r from-blue-600 to-indigo-600 text-white p-6 shadow-lg">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              🎓 캠퍼스메이트
            </h1>
            <p className="text-sm text-blue-100 mt-1">대학 행정 업무를 쉽고 빠르게 도와드립니다</p>
          </div>

          {/* 문서 업로드 버튼 */}
          <button
            onClick={() => setShowUploadModal(true)}
            className="px-5 py-2.5 bg-white text-blue-600 rounded-lg font-medium hover:bg-blue-50 transition-all shadow-md hover:shadow-lg"
          >
            📄 문서 업로드
          </button>
        </div>
      </div>

      {/* 메시지 영역 */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-4xl mx-auto space-y-6">
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}

          {isLoading && (
            <div className="flex items-center space-x-2 text-gray-600">
              <div className="flex space-x-1">
                <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{animationDelay: '0ms'}}></div>
                <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{animationDelay: '150ms'}}></div>
                <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{animationDelay: '300ms'}}></div>
              </div>
              <span className="ml-2 text-sm">답변을 생성하고 있습니다...</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* 입력 영역 */}
      <div className="bg-white border-t border-gray-200 p-6 shadow-lg">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-end space-x-3">
            <textarea
              className="flex-1 border-2 border-gray-300 rounded-xl p-4 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
              rows="2"
              placeholder="궁금한 점을 입력해주세요... (예: 휴학 신청은 어떻게 하나요?)"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={handleKeyPress}
              disabled={isLoading}
            />
            <button
              className={`px-8 py-4 rounded-xl font-semibold transition-all shadow-md hover:shadow-lg ${
                isLoading || !inputValue.trim()
                  ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                  : 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white hover:from-blue-700 hover:to-indigo-700'
              }`}
              onClick={handleSendMessage}
              disabled={isLoading || !inputValue.trim()}
            >
              전송
            </button>
          </div>
        </div>
      </div>

      {/* 문서 업로드 모달 */}
      {showUploadModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold text-gray-800">📄 문서 업로드</h2>
              <button
                onClick={() => setShowUploadModal(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                ✕
              </button>
            </div>

            <div className="space-y-4">
              {/* 파일 선택 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  PDF 파일 <span className="text-red-500">*</span>
                </label>
                <input
                  id="file-upload-input"
                  type="file"
                  accept=".pdf"
                  onChange={handleFileChange}
                  disabled={uploading}
                  className="block w-full text-sm text-gray-500
                    file:mr-4 file:py-2 file:px-4
                    file:rounded-md file:border-0
                    file:text-sm file:font-semibold
                    file:bg-blue-50 file:text-blue-700
                    hover:file:bg-blue-100
                    disabled:opacity-50"
                />
                {uploadFile && (
                  <p className="mt-1 text-sm text-gray-600">
                    {uploadFile.name} ({(uploadFile.size / 1024 / 1024).toFixed(2)} MB)
                  </p>
                )}
              </div>

              {/* 카테고리 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  카테고리 <span className="text-red-500">*</span>
                </label>
                <select
                  value={uploadCategory}
                  onChange={(e) => setUploadCategory(e.target.value)}
                  disabled={uploading}
                  className="block w-full px-3 py-2 border border-gray-300 rounded-md
                    focus:outline-none focus:ring-blue-500 focus:border-blue-500
                    disabled:opacity-50"
                >
                  {categories.map((cat) => (
                    <option key={cat.value} value={cat.value}>
                      {cat.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* 담당 부서 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  담당 부서 (선택)
                </label>
                <input
                  type="text"
                  value={uploadDepartment}
                  onChange={(e) => setUploadDepartment(e.target.value)}
                  disabled={uploading}
                  placeholder="예: 학사지원팀"
                  className="block w-full px-3 py-2 border border-gray-300 rounded-md
                    focus:outline-none focus:ring-blue-500 focus:border-blue-500
                    disabled:opacity-50"
                />
              </div>

              {/* 업로드 버튼 */}
              <button
                onClick={handleUpload}
                disabled={!uploadFile || uploading}
                className={`w-full py-3 px-4 rounded-md font-medium text-white transition-colors ${
                  !uploadFile || uploading
                    ? 'bg-gray-300 cursor-not-allowed'
                    : 'bg-blue-600 hover:bg-blue-700'
                }`}
              >
                {uploading ? (
                  <span className="flex items-center justify-center">
                    <svg className="animate-spin h-5 w-5 mr-2" viewBox="0 0 24 24">
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                        fill="none"
                      />
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                      />
                    </svg>
                    업로드 중...
                  </span>
                ) : (
                  '📤 업로드'
                )}
              </button>

              {/* 결과 메시지 */}
              {uploadResult && (
                <div
                  className={`p-3 rounded-md ${
                    uploadResult.success
                      ? 'bg-green-50 border border-green-200'
                      : 'bg-red-50 border border-red-200'
                  }`}
                >
                  <p
                    className={`text-sm ${
                      uploadResult.success ? 'text-green-800' : 'text-red-800'
                    }`}
                  >
                    {uploadResult.success ? '✅' : '❌'} {uploadResult.message}
                  </p>
                </div>
              )}

              {/* 안내 */}
              <div className="text-xs text-gray-500 space-y-1">
                <p>• PDF 파일만 업로드 가능 (최대 50MB)</p>
                <p>• 업로드 후 자동으로 벡터화 처리됩니다</p>
                <p>• 처리 완료 후 챗봇이 검색할 수 있습니다</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ChatInterface;
