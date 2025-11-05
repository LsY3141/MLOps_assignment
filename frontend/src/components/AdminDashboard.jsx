/**
 * 관리자 대시보드 컴포넌트
 * 문서 업로드 및 관리
 */

import React, { useState } from 'react';
import { adminAPI } from '../services/api';

const AdminDashboard = ({ schoolId = 'demo_school' }) => {
  const [selectedFile, setSelectedFile] = useState(null);
  const [metadata, setMetadata] = useState({
    title: '',
    category: '학사',
    department: '',
    contact: '',
  });
  const [uploadStatus, setUploadStatus] = useState(null);
  const [isUploading, setIsUploading] = useState(false);

  // 파일 선택 핸들러
  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      setSelectedFile(file);
      // 파일명을 제목에 자동 입력
      if (!metadata.title) {
        setMetadata((prev) => ({
          ...prev,
          title: file.name.replace(/\.[^/.]+$/, ''),
        }));
      }
    }
  };

  // 메타데이터 입력 핸들러
  const handleMetadataChange = (field, value) => {
    setMetadata((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  // 문서 업로드
  const handleUpload = async () => {
    if (!selectedFile) {
      alert('파일을 선택해주세요.');
      return;
    }

    if (!metadata.title || !metadata.department || !metadata.contact) {
      alert('모든 필수 항목을 입력해주세요.');
      return;
    }

    setIsUploading(true);
    setUploadStatus(null);

    try {
      const response = await adminAPI.uploadDocument(selectedFile, {
        ...metadata,
        schoolId,
      });

      setUploadStatus({
        type: 'success',
        message: '문서가 성공적으로 업로드되었습니다!',
      });

      // 폼 초기화
      setSelectedFile(null);
      setMetadata({
        title: '',
        category: '학사',
        department: '',
        contact: '',
      });
      document.getElementById('file-input').value = '';
    } catch (error) {
      setUploadStatus({
        type: 'error',
        message: `업로드 실패: ${error.response?.data?.detail || error.message}`,
      });
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 헤더 */}
      <div className="bg-blue-600 text-white p-6 shadow-md">
        <h1 className="text-2xl font-bold">📊 관리자 대시보드</h1>
        <p className="text-blue-100 mt-1">문서 업로드 및 지식베이스 관리</p>
      </div>

      {/* 메인 컨텐츠 */}
      <div className="max-w-4xl mx-auto p-6">
        {/* 문서 업로드 섹션 */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4">📄 문서 업로드</h2>

          {/* 파일 선택 */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              파일 선택 <span className="text-red-500">*</span>
            </label>
            <input
              id="file-input"
              type="file"
              accept=".pdf,.docx,.doc"
              onChange={handleFileSelect}
              className="block w-full text-sm text-gray-500
                file:mr-4 file:py-2 file:px-4
                file:rounded-lg file:border-0
                file:text-sm file:font-semibold
                file:bg-blue-50 file:text-blue-700
                hover:file:bg-blue-100"
            />
            {selectedFile && (
              <p className="mt-2 text-sm text-gray-600">선택된 파일: {selectedFile.name}</p>
            )}
          </div>

          {/* 메타데이터 입력 */}
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                문서 제목 <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={metadata.title}
                onChange={(e) => handleMetadataChange('title', e.target.value)}
                className="w-full border border-gray-300 rounded-lg p-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="예: 2025학년도 휴학 신청 안내"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                카테고리 <span className="text-red-500">*</span>
              </label>
              <select
                value={metadata.category}
                onChange={(e) => handleMetadataChange('category', e.target.value)}
                className="w-full border border-gray-300 rounded-lg p-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="학사">학사</option>
                <option value="장학">장학</option>
                <option value="시설">시설</option>
                <option value="행사">행사</option>
                <option value="기타">기타</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                담당 부서 <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={metadata.department}
                onChange={(e) => handleMetadataChange('department', e.target.value)}
                className="w-full border border-gray-300 rounded-lg p-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="예: 학사지원팀"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                연락처 <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={metadata.contact}
                onChange={(e) => handleMetadataChange('contact', e.target.value)}
                className="w-full border border-gray-300 rounded-lg p-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="예: 031-123-4567"
              />
            </div>
          </div>

          {/* 업로드 버튼 */}
          <button
            onClick={handleUpload}
            disabled={isUploading || !selectedFile}
            className={`w-full py-3 rounded-lg font-medium transition-colors ${
              isUploading || !selectedFile
                ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                : 'bg-blue-600 text-white hover:bg-blue-700'
            }`}
          >
            {isUploading ? '업로드 중...' : '업로드'}
          </button>

          {/* 상태 메시지 */}
          {uploadStatus && (
            <div
              className={`mt-4 p-3 rounded-lg ${
                uploadStatus.type === 'success'
                  ? 'bg-green-100 text-green-800'
                  : 'bg-red-100 text-red-800'
              }`}
            >
              {uploadStatus.message}
            </div>
          )}
        </div>

        {/* TODO: 문서 목록, RSS 관리 등 추가 기능 */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-xl font-semibold mb-4">📋 업로드된 문서 목록</h2>
          <p className="text-gray-500">문서 목록 기능은 추후 구현 예정입니다.</p>
        </div>
      </div>
    </div>
  );
};

export default AdminDashboard;
