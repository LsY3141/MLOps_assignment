import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import ChatInterface from './components/ChatInterface';
import AdminDashboard from './components/AdminDashboard';
import DocumentUpload from './components/DocumentUpload';

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-gray-50">
        {/* 네비게이션 바 */}
        <nav className="bg-white shadow-sm border-b">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between h-16 items-center">
              <div className="flex space-x-8">
                <Link
                  to="/"
                  className="inline-flex items-center px-1 pt-1 text-sm font-medium text-gray-900 hover:text-blue-600"
                >
                  🎓 챗봇
                </Link>
                <Link
                  to="/upload"
                  className="inline-flex items-center px-1 pt-1 text-sm font-medium text-gray-500 hover:text-gray-900"
                >
                  📄 문서 업로드
                </Link>
                <Link
                  to="/admin"
                  className="inline-flex items-center px-1 pt-1 text-sm font-medium text-gray-500 hover:text-gray-900"
                >
                  ⚙️ 관리자
                </Link>
              </div>
            </div>
          </div>
        </nav>

        {/* 라우트 */}
        <Routes>
          <Route path="/" element={<ChatInterface />} />
          <Route path="/upload" element={<DocumentUpload />} />
          <Route path="/admin" element={<AdminDashboard />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
