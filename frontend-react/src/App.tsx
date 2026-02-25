import { useEffect } from 'react';
import { useAuthStore } from '@/store/authStore';
import { LoginForm } from '@/components/Auth/LoginForm';
import { ChatContainer } from '@/components/Chat/ChatContainer';
import { Sidebar } from '@/components/Layout/Sidebar';
import { Header } from '@/components/Layout/Header';

export default function App() {
  const { token, user, isLoading, checkAuth } = useAuthStore();

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
            <h2 className="text-lg font-semibold text-gray-800 mb-4">Sign In</h2>
            <LoginForm />
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
