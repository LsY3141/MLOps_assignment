/**
 * 문서 업로드 컴포넌트
 * S3로 PDF 파일 직접 업로드 (Lambda가 자동으로 벡터화 처리)
 */

import React, { useState } from 'react';
import axios from 'axios';

const DocumentUpload = ({ schoolId = 1 }) => {
  const [file, setFile] = useState(null);
  const [category, setCategory] = useState('academic');
  const [department, setDepartment] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const [error, setError] = useState(null);

  const categories = [
    { value: 'academic', label: '학사' },
    { value: 'scholarship', label: '장학' },
    { value: 'facilities', label: '시설' },
    { value: 'career', label: '진로/취업' },
    { value: 'general', label: '일반' },
  ];

  // 파일 선택 핸들러
  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];

    if (!selectedFile) {
      setFile(null);
      return;
    }

    // PDF 파일 검증
    if (!selectedFile.name.toLowerCase().endsWith('.pdf')) {
      setError('PDF 파일만 업로드 가능합니다.');
      setFile(null);
      return;
    }

    // 파일 크기 검증 (50MB)
    if (selectedFile.size > 50 * 1024 * 1024) {
      setError('파일 크기는 50MB를 초과할 수 없습니다.');
      setFile(null);
      return;
    }

    setFile(selectedFile);
    setError(null);
    setUploadResult(null);
  };

  // S3 Presigned URL 방식으로 업로드
  const uploadToS3Direct = async () => {
    try {
      setUploading(true);
      setError(null);

      // 1. 백엔드에서 S3 Presigned URL 요청
      const { data: presignedData } = await axios.post(
        `${process.env.REACT_APP_API_URL || 'http://localhost:8000'}/api/documents/presigned-url`,
        {
          school_id: schoolId,
          category: category,
          file_name: file.name,
          department: department || null,
        }
      );

      // 2. Presigned URL로 S3에 직접 업로드
      await axios.put(presignedData.upload_url, file, {
        headers: {
          'Content-Type': 'application/pdf',
        },
      });

      setUploadResult({
        success: true,
        message: '문서가 업로드되었습니다. 자동 벡터화 처리 중입니다...',
        s3_key: presignedData.s3_key,
      });

      // 폼 초기화
      setFile(null);
      setDepartment('');
      document.getElementById('file-input').value = '';

    } catch (err) {
      console.error('Upload error:', err);
      setError(err.response?.data?.detail || '업로드 중 오류가 발생했습니다.');
    } finally {
      setUploading(false);
    }
  };

  // 백엔드 API를 통한 업로드 (기존 방식 - 대안)
  const uploadViaBackend = async () => {
    try {
      setUploading(true);
      setError(null);

      const formData = new FormData();
      formData.append('file', file);
      formData.append('school_id', schoolId);
      formData.append('category', category);
      if (department) {
        formData.append('department', department);
      }

      const { data } = await axios.post(
        `${process.env.REACT_APP_API_URL || 'http://localhost:8000'}/api/admin/upload-document`,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        }
      );

      setUploadResult({
        success: true,
        message: '문서가 성공적으로 업로드되고 벡터화되었습니다!',
        document_id: data.document_id,
        chunk_count: data.chunk_count,
      });

      // 폼 초기화
      setFile(null);
      setDepartment('');
      document.getElementById('file-input').value = '';

    } catch (err) {
      console.error('Upload error:', err);
      setError(err.response?.data?.detail || '업로드 중 오류가 발생했습니다.');
    } finally {
      setUploading(false);
    }
  };

  // 업로드 실행 (S3 직접 업로드 방식 사용)
  const handleUpload = () => {
    uploadToS3Direct(); // 또는 uploadViaBackend()
  };

  return (
    <div className="max-w-2xl mx-auto p-6 bg-white rounded-lg shadow-md">
      <h2 className="text-2xl font-bold mb-6 text-gray-800">📄 문서 업로드</h2>

      <div className="space-y-4">
        {/* 파일 선택 */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            PDF 파일 선택 <span className="text-red-500">*</span>
          </label>
          <input
            id="file-input"
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
          {file && (
            <p className="mt-2 text-sm text-gray-600">
              선택된 파일: <strong>{file.name}</strong> ({(file.size / 1024 / 1024).toFixed(2)} MB)
            </p>
          )}
        </div>

        {/* 카테고리 선택 */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            카테고리 <span className="text-red-500">*</span>
          </label>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            disabled={uploading}
            className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm
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

        {/* 담당 부서 (선택) */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            담당 부서 (선택)
          </label>
          <input
            type="text"
            value={department}
            onChange={(e) => setDepartment(e.target.value)}
            disabled={uploading}
            placeholder="예: 학사지원팀"
            className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm
              focus:outline-none focus:ring-blue-500 focus:border-blue-500
              disabled:opacity-50"
          />
        </div>

        {/* 업로드 버튼 */}
        <button
          onClick={handleUpload}
          disabled={!file || uploading}
          className={`w-full py-3 px-4 rounded-md font-medium text-white transition-colors ${
            !file || uploading
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
            '📤 업로드 및 벡터화'
          )}
        </button>

        {/* 성공 메시지 */}
        {uploadResult && uploadResult.success && (
          <div className="p-4 bg-green-50 border border-green-200 rounded-md">
            <div className="flex">
              <span className="text-green-500 text-xl mr-2">✅</span>
              <div>
                <p className="font-medium text-green-800">{uploadResult.message}</p>
                {uploadResult.document_id && (
                  <p className="text-sm text-green-700 mt-1">
                    문서 ID: {uploadResult.document_id}, 청크 수: {uploadResult.chunk_count}
                  </p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* 에러 메시지 */}
        {error && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-md">
            <div className="flex">
              <span className="text-red-500 text-xl mr-2">❌</span>
              <p className="text-red-800">{error}</p>
            </div>
          </div>
        )}
      </div>

      {/* 안내 사항 */}
      <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-md">
        <h3 className="font-medium text-blue-900 mb-2">💡 안내 사항</h3>
        <ul className="text-sm text-blue-800 space-y-1 list-disc list-inside">
          <li>PDF 파일만 업로드 가능합니다.</li>
          <li>파일 크기는 최대 50MB입니다.</li>
          <li>업로드 후 자동으로 텍스트 추출 및 벡터화가 진행됩니다.</li>
          <li>처리 완료 후 챗봇이 해당 문서를 검색할 수 있습니다.</li>
        </ul>
      </div>
    </div>
  );
};

export default DocumentUpload;
