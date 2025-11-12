import React, { useState } from 'react';
import { postQuery } from './services/api';

function App() {
  const [question, setQuestion] = useState('');
  const [response, setResponse] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!question) return;

    setLoading(true);
    setError(null);
    setResponse(null);

    try {
      // Using school_id=1 as a default for now
      const res = await postQuery(question, 1);
      setResponse(res.data);
    } catch (err) {
      setError('Failed to get a response from the server.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container mx-auto p-4">
      <h1 className="text-2xl font-bold mb-4">CampusMate Chat</h1>
      
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question..."
          className="w-full p-2 border rounded mb-2"
          disabled={loading}
        />
        <button 
          type="submit" 
          className="w-full bg-blue-500 text-white p-2 rounded hover:bg-blue-600 disabled:bg-blue-300"
          disabled={loading}
        >
          {loading ? 'Thinking...' : 'Send'}
        </button>
      </form>

      {error && <div className="mt-4 p-4 bg-red-100 text-red-700 rounded">{error}</div>}

      {response && (
        <div className="mt-4 p-4 border rounded bg-gray-50">
          <h2 className="font-bold">Answer:</h2>
          <p className="mb-2">{response.answer}</p>
          <h3 className="font-semibold">Sources:</h3>
          {response.source_documents.length > 0 ? (
            <ul>
              {response.source_documents.map((doc, index) => (
                <li key={index} className="text-sm text-gray-600 border-t mt-1 pt-1">
                  <strong>{doc.source}:</strong> {doc.content}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-gray-500">No sources provided.</p>
          )}
        </div>
      )}
    </div>
  );
}

export default App;