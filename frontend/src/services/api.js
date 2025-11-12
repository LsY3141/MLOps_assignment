import axios from 'axios';

const apiClient = axios.create({
  baseURL: 'http://localhost:8000/api', // Our backend API
  headers: {
    'Content-Type': 'application/json',
  },
});

export const postQuery = (question, schoolId) => {
  return apiClient.post('/chat/query', {
    question: question,
    school_id: schoolId,
  });
};