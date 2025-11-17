/**
 * 메시지 버블 컴포넌트
 * 사용자/AI 메시지를 표시
 */

import React from 'react';
import ReactMarkdown from 'react-markdown';

const MessageBubble = ({ message }) => {
  const isUser = message.role === 'user';
  const isError = message.isError;

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} animate-fadeIn`}>
      <div
        className={`max-w-3xl px-5 py-4 rounded-2xl shadow-md ${
          isUser
            ? 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white'
            : isError
            ? 'bg-red-50 text-red-900 border-2 border-red-300'
            : 'bg-white border border-gray-200 text-gray-800'
        }`}
      >
        {/* 메시지 내용 */}
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div className="prose prose-sm max-w-none">
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
        )}

        {/* 메타데이터 (AI 응답인 경우) */}
        {!isUser && !isError && message.metadata && (
          <div className="mt-3 pt-3 border-t border-gray-200 text-sm text-gray-600">
            {message.metadata.department && (
              <div>
                <span className="font-semibold">담당 부서:</span> {message.metadata.department}
              </div>
            )}
            {message.metadata.contact && (
              <div>
                <span className="font-semibold">연락처:</span>{' '}
                <a href={`tel:${message.metadata.contact}`} className="text-blue-600 hover:underline">
                  {message.metadata.contact}
                </a>
              </div>
            )}
          </div>
        )}

        {/* 응답 타입 배지 */}
        {!isUser && !isError && message.responseType && (
          <div className="mt-2">
            <span
              className={`inline-block px-2 py-1 text-xs rounded ${
                message.responseType === 'rag'
                  ? 'bg-green-100 text-green-800'
                  : 'bg-yellow-100 text-yellow-800'
              }`}
            >
              {message.responseType === 'rag' ? '📚 문서 기반 답변' : '📞 담당 부서 안내'}
            </span>
          </div>
        )}

        {/* 타임스탬프 */}
        <div className={`mt-1 text-xs ${isUser ? 'text-blue-200' : 'text-gray-400'}`}>
          {message.timestamp.toLocaleTimeString('ko-KR', {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </div>
      </div>
    </div>
  );
};

export default MessageBubble;
