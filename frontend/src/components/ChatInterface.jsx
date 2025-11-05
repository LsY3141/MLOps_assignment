/**
 * 챗봇 인터페이스 컴포넌트
 * 메인 채팅 화면
 */

import React, { useState, useRef, useEffect } from 'react';
import MessageBubble from './MessageBubble';
import { chatAPI } from '../services/api';

const ChatInterface = ({ schoolId = 'demo_school' }) => {
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

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* 헤더 */}
      <div className="bg-blue-600 text-white p-4 shadow-md">
        <h1 className="text-xl font-bold">🎓 캠퍼스메이트</h1>
        <p className="text-sm text-blue-100">대학 행정 AI 도우미</p>
      </div>

      {/* 메시지 영역 */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}

        {isLoading && (
          <div className="flex items-center space-x-2 text-gray-500">
            <div className="animate-bounce">●</div>
            <div className="animate-bounce delay-100">●</div>
            <div className="animate-bounce delay-200">●</div>
            <span className="ml-2">답변을 생성하고 있습니다...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* 입력 영역 */}
      <div className="bg-white border-t border-gray-200 p-4">
        <div className="max-w-4xl mx-auto flex items-end space-x-2">
          <textarea
            className="flex-1 border border-gray-300 rounded-lg p-3 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
            rows="2"
            placeholder="궁금한 점을 입력해주세요... (예: 휴학 신청은 어떻게 하나요?)"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            disabled={isLoading}
          />
          <button
            className={`px-6 py-3 rounded-lg font-medium transition-colors ${
              isLoading || !inputValue.trim()
                ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                : 'bg-blue-600 text-white hover:bg-blue-700'
            }`}
            onClick={handleSendMessage}
            disabled={isLoading || !inputValue.trim()}
          >
            전송
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChatInterface;
