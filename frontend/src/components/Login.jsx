import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useTranslation } from 'react-i18next';

const Login = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLogin] = useState(true);
  const [activeTab, setActiveTab] = useState('admin'); // 'admin' | 'client' | 'rep'
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();
  const { t } = useTranslation();

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      navigate('/dashboard');
    }
  }, [isAuthenticated, navigate]);

  // OPTIMIZED: Memoized submit handler to prevent unnecessary re-renders
  const handleSubmit = useCallback(async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = await login(email, password);
      const userRole = (res?.user?.role || '').toLowerCase();
      if (userRole && userRole !== activeTab) {
        await logout();
        setError(t('login.pleaseSignInUsingTab', { role: userRole }));
        return;
      }
      
      // Store username for toast notification
      const username = res?.user?.name || res?.user?.email?.split('@')[0] || 'User';
      localStorage.setItem('showWelcomeToast', 'true');
      localStorage.setItem('welcomeUsername', username);
      
      // Navigate to dashboard
      navigate('/dashboard');
    } catch (error) {
      setError(error.message);
    } finally {
      setLoading(false);
    }
  }, [email, password, activeTab, login, logout, navigate, t]);

  // OPTIMIZED: Memoized tab buttons to prevent re-renders
  const tabButtons = useMemo(() => (
    ['admin','client','rep'].map((tab) => (
      <button
        type="button"
        key={tab}
        onClick={() => setActiveTab(tab)}
        className={`flex-1 py-2.5 px-4 rounded-full text-sm font-medium transition-all ${
          activeTab === tab 
            ? 'bg-gradient-to-r from-purple-500 to-blue-500 text-white shadow-md' 
            : 'bg-white text-gray-600 hover:text-gray-900'
        }`}
      >
        {tab.charAt(0).toUpperCase()+tab.slice(1)}
      </button>
    ))
  ), [activeTab]);

  return (
    <div className="h-screen w-screen flex flex-col justify-center items-center fixed inset-0 overflow-auto" style={{
        background: 'linear-gradient(to right, #f3e8ff, #e0f2fe)'
      }}>
        {/* Back to Home Link - Top Left */}
        <Link
          to="/"
          className="absolute top-6 left-6 z-10 inline-flex items-center px-4 py-2.5 bg-white/90 backdrop-blur-sm rounded-xl shadow-md text-sm font-semibold text-gray-700 hover:text-purple-600 hover:bg-white hover:shadow-lg transition-all duration-200 border border-gray-200/50"
        >
          <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          {t('login.backToHome')}
        </Link>
        
        <div className="w-full max-w-md px-6">
        {/* Enzura Logo */}
        <div className="flex flex-col items-center mb-8">
          <h1 className="text-5xl font-bold mb-4" style={{
            background: 'linear-gradient(to right, #9333ea, #3b82f6, #06b6d4)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text',
            textShadow: '0 0 30px rgba(147, 51, 234, 0.3)',
            letterSpacing: '-0.5px'
          }}>
            {t('login.title')}
          </h1>
          <h2 className="text-xl font-semibold text-gray-900 mb-2">
            {t('login.welcomeBack')}
          </h2>
          <p className="text-sm text-gray-600">
            {t('login.signInToContinue')}
          </p>
        </div>
        
        <div className="bg-white rounded-xl shadow-lg border border-cyan-200 py-8 px-8 sm:px-10">
          <form className="space-y-6" onSubmit={handleSubmit}>
            {/* SELECT ROLE Section */}
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-gray-700 mb-3">
                {t('login.selectRole')}
              </label>
              <div className="flex gap-2 bg-gray-50 rounded-full p-1">
                {tabButtons}
              </div>
            </div>

            {/* EMAIL ADDRESS Section */}
            <div>
              <label htmlFor="email" className="block text-xs font-bold uppercase tracking-wider text-gray-700 mb-3">
                {t('login.emailAddress')}
              </label>
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="appearance-none block w-full px-4 py-3 border border-gray-300 rounded-lg placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent text-sm bg-white"
              />
            </div>

            {/* PASSWORD Section */}
            <div>
              <label htmlFor="password" className="block text-xs font-bold uppercase tracking-wider text-gray-700 mb-3">
                {t('login.password')}
              </label>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete={isLogin ? "current-password" : "new-password"}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="appearance-none block w-full px-4 py-3 border border-gray-300 rounded-lg placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent text-sm bg-white"
              />
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                <div className="flex">
                  <div className="flex-shrink-0">
                    <svg className="h-5 w-5 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </div>
                  <div className="ml-3">
                    <p className="text-sm text-red-800">{error}</p>
                  </div>
                </div>
              </div>
            )}

            {/* Sign in Button */}
            <div>
              <button
                type="submit"
                disabled={loading}
                className="w-full flex justify-center py-3 px-4 border border-transparent rounded-lg shadow-md text-sm font-medium text-white bg-gradient-to-r from-purple-500 to-blue-500 hover:from-purple-600 hover:to-blue-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-purple-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
              >
                {loading ? (
                  <>
                    <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    {t('common.loading')}
                  </>
                ) : (
                  t('login.signIn')
                )}
              </button>
            </div>
          </form>
        </div>
        </div>
      </div>
  );
};

export default Login;