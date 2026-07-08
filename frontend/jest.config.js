export default {
  testEnvironment: 'jsdom',
  transform: {
    '^.+\\.(js|jsx)$': 'babel-jest',
  },
  moduleNameMapper: {
    '^../services/(.*)$': '<rootDir>/src/services/$1',
    '^../stores/(.*)$': '<rootDir>/src/stores/$1',
    '^../utils/(.*)$': '<rootDir>/src/utils/$1',
    '^import\\.meta\\.env$': '<rootDir>/src/utils/test-env.js',
  },
  setupFilesAfterEnv: ['@testing-library/jest-dom'],
  testPathIgnorePatterns: ['/node_modules/', '/dist/'],
  globals: {
    'import.meta.env': {
      VITE_API_BASE_URL: '/api',
      VITE_SSE_URL: '/sse',
    },
  },
}