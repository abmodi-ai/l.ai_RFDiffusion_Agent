import { useEffect } from 'react';
import { useAuthStore } from '@/store/authStore';
import { LoginForm } from '@/components/Auth/LoginForm';
import { RegisterForm } from '@/components/Auth/RegisterForm';
import { ChatContainer } from '@/components/Chat/ChatContainer';
import { Sidebar } from '@/components/Layout/Sidebar';
import { Header } from '@/components/Layout/Header';
import { useState } from 'react';

export default function App() {
  const { token, user, isLoading, checkAuth } = useAuthStore();
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login');

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  if (isLoading && !user) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600" />
      </div>
    );
  }

  if (!token || !user) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-primary-50 to-primary-100">
        <div className="w-full max-w-md p-8">
          <div className="text-center mb-8">
            <h1 className="text-4xl font-bold text-primary-800">Ligant.ai</h1>
            <p className="text-gray-600 mt-2">
              AI-powered protein binder design with RFdiffusion
            </p>
          </div>

          <div className="bg-white rounded-xl shadow-lg p-6">
            <div className="flex mb-6 border-b">
              <button
                className={`flex-1 pb-3 text-sm font-medium ${
                  authMode === 'login'
                    ? 'text-primary-600 border-b-2 border-primary-600'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
                onClick={() => setAuthMode('login')}
              >
                Sign In
              </button>
              <button
                className={`flex-1 pb-3 text-sm font-medium ${
                  authMode === 'register'
                    ? 'text-primary-600 border-b-2 border-primary-600'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
                onClick={() => setAuthMode('register')}
              >
                Create Account
              </button>
            </div>

            {authMode === 'login' ? <LoginForm /> : <RegisterForm />}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col">
        <Header />
        <ChatContainer />
      </div>
    </div>
  );
}
