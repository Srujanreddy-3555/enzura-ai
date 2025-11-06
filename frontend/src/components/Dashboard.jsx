import React, { useState, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import apiService from '../services/api';
import { SkeletonCard, SkeletonTableRow } from './SkeletonLoader';
import SuccessToast from './SuccessToast';
import Sidebar from './Sidebar';
import UserHeader from './UserHeader';

const Dashboard = () => {
  const [activeItem, setActiveItem] = useState('Dashboard');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [dashboardData, setDashboardData] = useState({
    totalCalls: 0,
    processedCalls: 0,
    processingCalls: 0,
    averageScore: 0,
    recentCalls: [],
    // Multi-tenant data
    clientInfo: null,
    uploadMethodStats: { manual: 0, s3_auto: 0 },
    salesRepStats: []
  });
  // OPTIMIZED: No loading state - show UI immediately!
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [showToast, setShowToast] = useState(false);
  const [toastUsername, setToastUsername] = useState('');

  const handleLogout = async () => {
    try {
      await logout();
      navigate('/login');
    } catch (error) {
      console.error('Logout failed:', error);
      // Force logout even if API call fails
      navigate('/login');
    }
  };

  // Mobile navigation items (for mobile menu only)
  const navigationItems = [
    { name: 'Dashboard', path: '/dashboard' },
    { name: 'My Calls', path: '/mycalls' },
    { name: 'Upload Call', path: '/uploadcall' },
    { name: 'Leaderboard', path: '/leaderboard' },
    ...(user?.role?.toLowerCase() === 'admin' ? [
      { name: 'Client Management', path: '/client-management' },
      { name: 'S3 Monitoring', path: '/s3-monitoring' },
      { name: 'Reports', path: '/reports' }
    ] : [])
  ];


  // Check for welcome toast on mount
  useEffect(() => {
    const showWelcomeToast = localStorage.getItem('showWelcomeToast');
    const welcomeUsername = localStorage.getItem('welcomeUsername');
    
    if (showWelcomeToast === 'true' && welcomeUsername) {
      setToastUsername(welcomeUsername);
      setShowToast(true);
      // Clear the flag so it doesn't show again
      localStorage.removeItem('showWelcomeToast');
      localStorage.removeItem('welcomeUsername');
    }
  }, []);

  // OPTIMIZED: Fetch dashboard data - INSTANT load with cache, update in background
  const abortControllerRef = useRef(null);
  const isInitialMount = useRef(true);
  const [isInitialLoad, setIsInitialLoad] = useState(true);
  
  useEffect(() => {
    const processStats = (stats) => {
      if (!stats || typeof stats !== 'object') {
        return null;
      }
      
      // Calculate sales rep stats from recent calls
      const salesRepStats = (stats.recentCalls || []).reduce((acc, call) => {
        if (call && call.sales_rep_name) {
          const existing = acc.find(rep => rep.name === call.sales_rep_name);
          if (existing) {
            existing.callCount++;
            existing.totalScore += call.score || 0;
            existing.avgScore = Math.round(existing.totalScore / existing.callCount);
          } else {
            acc.push({
              name: call.sales_rep_name,
              callCount: 1,
              totalScore: call.score || 0,
              avgScore: call.score || 0
            });
          }
        }
        return acc;
      }, []);
      
      return {
        totalCalls: stats.totalCalls ?? 0,
        processedCalls: stats.processedCalls ?? 0,
        processingCalls: stats.processingCalls ?? 0,
        averageScore: stats.averageScore ?? 0,
        recentCalls: Array.isArray(stats.recentCalls) ? stats.recentCalls : [],
        clientInfo: user?.client_name ? { name: user.client_name, id: user.client_id } : null,
        uploadMethodStats: stats.uploadMethodStats || { manual: 0, s3_auto: 0 },
        salesRepStats: salesRepStats.length > 0 ? salesRepStats.sort((a, b) => b.callCount - a.callCount).slice(0, 5) : []
      };
    };
    
    const fetchDashboardData = async (skipCache = false) => {
      // Cancel previous request if still pending
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      
      // Create new abort controller for this request
      abortControllerRef.current = new AbortController();
      
      try {
        // OPTIMIZED: Use dedicated stats endpoint with caching
        // On initial mount, cache will return instantly if available
        const stats = await apiService.getDashboardStats(skipCache ? { skipCache: true } : {});
        
        const processedData = processStats(stats);
        if (processedData) {
          setDashboardData(processedData);
        }
        
      } catch (err) {
        // Only log error if it's not an abort (abort is expected)
        if (err.name !== 'AbortError') {
          console.error('Failed to fetch dashboard data:', err);
        }
        // Don't clear existing data on error - keep showing what we have
      }
    };

    // OPTIMIZED: Only fetch if user is authenticated and loaded
    if (!user) {
      return () => {}; // Wait for user
    }

    // CRITICAL: On initial mount, try to get cached data INSTANTLY (synchronous-like)
    if (isInitialMount.current) {
      isInitialMount.current = false;
      
      // Try to get cached data immediately (cache returns Promise.resolve which is instant)
      apiService.getDashboardStats().then((cachedStats) => {
        const processedData = processStats(cachedStats);
        if (processedData && processedData.totalCalls > 0) {
          // If we have cached data with calls, show it INSTANTLY
          setDashboardData(processedData);
          setIsInitialLoad(false);
        } else {
          // No cached data, show skeleton
          setIsInitialLoad(true);
        }
      }).catch(() => {
        // Ignore cache errors on initial mount
        setIsInitialLoad(true);
      });
      
      // Then fetch fresh data in background
      fetchDashboardData(true).then(() => {
        setIsInitialLoad(false);
      }); // Skip cache to get fresh data
    } else {
      // Subsequent mounts: fetch with cache (will be instant if cached)
      fetchDashboardData().then(() => {
        setIsInitialLoad(false);
      });
    }

    // OPTIMIZED: Auto-refresh every 3 seconds (faster updates, better performance)
    const refreshInterval = setInterval(() => {
      fetchDashboardData(true); // Skip cache for refresh to get fresh data
    }, 3000);

    // Cleanup: cancel pending requests and clear interval
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      clearInterval(refreshInterval);
    };
  }, [user]); // Only depend on user


  return (
    <>
      {showToast && (
        <SuccessToast
          message="Welcome back"
          username={toastUsername}
          onClose={() => setShowToast(false)}
          duration={3000}
        />
      )}
      <div className="min-h-screen bg-gray-50">
        {/* Mobile Header */}
      <div className="lg:hidden bg-white shadow-sm border-b border-gray-200">
        <div className="flex items-center justify-between px-4 py-3">
          <h1 className="text-lg font-semibold text-gray-900">Dashboard</h1>
          <div className="flex items-center space-x-2">
            <button
              onClick={handleLogout}
              className="p-2 rounded-md text-gray-600 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-red-500"
              title="Logout"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
            </button>
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-2 rounded-md text-gray-600 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-indigo-500"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
          </div>
        </div>
        
        {/* Mobile Navigation */}
        {sidebarOpen && (
          <div className="px-4 pb-3 space-y-1 bg-gray-900">
            {navigationItems.map((item) => (
              <Link
                key={item.name}
                to={item.path}
                className={`block px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  activeItem === item.name
                    ? 'bg-gray-800 text-white'
                    : 'text-gray-300 hover:bg-gray-700 hover:text-white'
                }`}
                onClick={() => setActiveItem(item.name)}
              >
                {item.name}
              </Link>
            ))}
            
            {/* Mobile Logout */}
            {user && (
              <>
                <div className="border-t border-gray-700 my-2"></div>
                <div className="px-3 py-2 text-xs text-gray-400">
                  Logged in as {user.name}
                </div>
                <button
                  onClick={handleLogout}
                  className="block w-full text-left px-3 py-2 rounded-md text-sm font-medium text-gray-300 hover:bg-gray-700 hover:text-white transition-colors"
                >
                  Logout
                </button>
              </>
            )}
          </div>
        )}
      </div>

      <div className="flex">
        {/* Desktop Sidebar */}
        <Sidebar 
          sidebarOpen={sidebarOpen}
          setSidebarOpen={setSidebarOpen}
          activeItem={activeItem}
          setActiveItem={setActiveItem}
        />

        {/* Main Content */}
        <div className={`flex flex-col flex-1 transition-all duration-300 ${
          sidebarOpen ? 'lg:pl-64' : 'lg:pl-16'
        }`}>
          {/* Top Right User Header */}
          <UserHeader />
          <main className="flex-1">
            <div className="py-6">
              <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                {/* Page Header */}
                <div className="mb-8">
                  <div className="flex items-center justify-between">
                    <div>
                      {/* Welcome Message with Gradient Name */}
                      <div className="flex items-center">
                        <h1 className="text-4xl font-bold text-black" style={{ fontFamily: 'serif' }}>
                          Welcome back,{' '}
                          <span className="bg-gradient-to-r from-purple-600 to-blue-600 bg-clip-text text-transparent">
                            {user?.name || 'User'}!
                          </span>
                        </h1>
                        <span className="ml-3 text-4xl">👋</span>
                      </div>
                      <p className="mt-2 text-base text-gray-500 font-normal">
                        Here's your call analytics overview
                      </p>
                      {/* Multi-tenant info */}
                      {dashboardData.clientInfo && (
                        <div className="mt-3 flex items-center space-x-2">
                          <div className="bg-indigo-100 text-indigo-800 px-3 py-1 rounded-full text-sm font-medium">
                            Client: {dashboardData.clientInfo.name}
                          </div>
                          {user?.role === 'admin' && (
                            <div className="bg-purple-100 text-purple-800 px-3 py-1 rounded-full text-sm font-medium">
                              Admin Access
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Skeleton Loader - Show while initial data is loading */}
                {isInitialLoad && dashboardData.totalCalls === 0 && (
                  <>
                    {/* Stats Grid Skeleton */}
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                      {[1, 2, 3, 4].map((i) => (
                        <SkeletonCard key={i} />
                      ))}
                    </div>
                    
                    {/* Recent Calls Skeleton */}
                    <div className="bg-white shadow rounded-xl">
                      <div className="px-4 py-5 sm:p-6">
                        <div className="h-6 bg-gray-300 rounded w-32 mb-6 animate-pulse"></div>
                        <div className="overflow-hidden">
                          <table className="min-w-full divide-y divide-gray-200">
                            <thead className="bg-gray-50">
                              <tr>
                                {['Call ID', 'Filename', 'Sales Rep', 'Status', 'Score', 'Date'].map((header) => (
                                  <th key={header} className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                                    <div className="h-4 bg-gray-300 rounded w-20 animate-pulse"></div>
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody className="bg-white divide-y divide-gray-200">
                              {[1, 2, 3, 4, 5].map((i) => (
                                <SkeletonTableRow key={i} />
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    </div>
                  </>
                )}

                {/* Empty State - No Calls */}
                {!isInitialLoad && dashboardData.totalCalls === 0 && (
                  <div className="bg-white shadow rounded-xl p-12 mb-8">
                    <div className="text-center">
                      <div className="mx-auto flex items-center justify-center h-24 w-24 rounded-full bg-indigo-100 mb-6">
                        <svg className="h-12 w-12 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                        </svg>
                      </div>
                      <h3 className="text-2xl font-bold text-gray-900 mb-2">You haven't uploaded any calls yet</h3>
                      <p className="text-lg text-gray-600 mb-8 max-w-md mx-auto">
                        Start by uploading your first call recording to see analytics, insights, and performance metrics.
                      </p>
                      <Link
                        to="/uploadcall"
                        className="inline-flex items-center px-8 py-4 border border-transparent text-lg font-medium rounded-lg text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition-colors shadow-lg"
                      >
                        <svg className="w-6 h-6 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                        </svg>
                        Upload Your First Call
                      </Link>
                    </div>
                  </div>
                )}

                {/* Dashboard Content - When Calls Exist */}
                {dashboardData.totalCalls > 0 && (
                  <>
                    {/* Stats Grid */}
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                      {/* Total Calls Card */}
                      <div className="bg-white border border-gray-200 rounded-2xl p-6">
                        <div className="flex items-start justify-between mb-4">
                          <h3 className="text-xs font-semibold text-gray-600 uppercase tracking-wide">Total Calls</h3>
                          <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
                            <svg className="w-5 h-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                            </svg>
                          </div>
                        </div>
                        <div className="mb-4">
                          <p className="text-3xl font-bold text-black">{dashboardData.totalCalls}</p>
                        </div>
                        <div className="flex items-center space-x-2">
                          <div className="w-8 h-8 bg-green-100 rounded-lg flex items-center justify-center">
                            <svg className="w-4 h-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                            </svg>
                          </div>
                          <span className="text-sm font-semibold text-green-600">+12%</span>
                          <span className="text-xs text-gray-500">from last month</span>
                        </div>
                      </div>

                      {/* Processed Card */}
                      <div className="bg-white border border-purple-200 rounded-2xl p-6">
                        <div className="flex items-start justify-between mb-4">
                          <h3 className="text-xs font-semibold text-gray-600 uppercase tracking-wide">Processed</h3>
                          <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
                            <svg className="w-5 h-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                          </div>
                        </div>
                        <div className="mb-4">
                          <p className="text-3xl font-bold text-black">{dashboardData.processedCalls}</p>
                        </div>
                        <div className="flex items-center space-x-2">
                          <div className="w-8 h-8 bg-green-100 rounded-lg flex items-center justify-center">
                            <svg className="w-4 h-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                            </svg>
                          </div>
                          <span className="text-sm font-semibold text-green-600">+15%</span>
                          <span className="text-xs text-gray-500">from last month</span>
                        </div>
                      </div>

                      {/* Processing Card */}
                      <div className="bg-white border border-gray-200 rounded-2xl p-6">
                        <div className="flex items-start justify-between mb-4">
                          <h3 className="text-xs font-semibold text-gray-600 uppercase tracking-wide">Processing</h3>
                          <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
                            <svg className="w-5 h-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                          </div>
                        </div>
                        <div className="mb-4">
                          <p className="text-3xl font-bold text-black">{dashboardData.processingCalls}</p>
                        </div>
                        <div className="flex items-center space-x-2">
                          <div className="w-8 h-8 bg-green-100 rounded-lg flex items-center justify-center">
                            <svg className="w-4 h-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                            </svg>
                          </div>
                          <span className="text-sm font-semibold text-green-600">+8%</span>
                          <span className="text-xs text-gray-500">from last month</span>
                        </div>
                      </div>

                      {/* Average Score Card */}
                      <div className="bg-white border border-gray-200 rounded-2xl p-6">
                        <div className="flex items-start justify-between mb-4">
                          <h3 className="text-xs font-semibold text-gray-600 uppercase tracking-wide">Avg Score</h3>
                          <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
                            <svg className="w-5 h-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
                            </svg>
                          </div>
                        </div>
                        <div className="mb-4">
                          <p className="text-3xl font-bold text-black">{dashboardData.averageScore}%</p>
                        </div>
                        <div className="flex items-center space-x-2">
                          <div className="w-8 h-8 bg-green-100 rounded-lg flex items-center justify-center">
                            <svg className="w-4 h-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                            </svg>
                          </div>
                          <span className="text-sm font-semibold text-green-600">+23%</span>
                          <span className="text-xs text-gray-500">from last month</span>
                        </div>
                      </div>
                    </div>

                    {/* Additional Stats for Multi-Tenant */}
                    {dashboardData.uploadMethodStats && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
                        {/* Upload Method Stats */}
                        <div className="bg-white shadow rounded-xl">
                          <div className="px-4 py-5 sm:p-6">
                            <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
                              Upload Methods
                            </h3>
                            <div className="space-y-3">
                              <div className="flex items-center justify-between">
                                <div className="flex items-center">
                                  <div className="w-3 h-3 bg-blue-500 rounded-full mr-3"></div>
                                  <span className="text-sm font-medium text-gray-700">Manual Upload</span>
                                </div>
                                <span className="text-sm font-bold text-gray-900">{dashboardData.uploadMethodStats.manual}</span>
                              </div>
                              <div className="flex items-center justify-between">
                                <div className="flex items-center">
                                  <div className="w-3 h-3 bg-green-500 rounded-full mr-3"></div>
                                  <span className="text-sm font-medium text-gray-700">S3 Auto Upload</span>
                                </div>
                                <span className="text-sm font-bold text-gray-900">{dashboardData.uploadMethodStats.s3_auto}</span>
                              </div>
                            </div>
                          </div>
                        </div>

                        {/* Sales Rep Performance */}
                        {dashboardData.salesRepStats.length > 0 && (
                          <div className="bg-white shadow rounded-xl">
                            <div className="px-4 py-5 sm:p-6">
                              <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
                                Top Sales Reps
                              </h3>
                              <div className="space-y-3">
                                {dashboardData.salesRepStats.slice(0, 3).map((rep, index) => (
                                  <div key={rep.name} className="flex items-center justify-between">
                                    <div className="flex items-center">
                                      <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold text-white mr-3 ${
                                        index === 0 ? 'bg-yellow-500' : index === 1 ? 'bg-gray-400' : 'bg-orange-500'
                                      }`}>
                                        {index + 1}
                                      </div>
                                      <span className="text-sm font-medium text-gray-700">{rep.name}</span>
                                    </div>
                                    <div className="text-right">
                                      <div className="text-sm font-bold text-gray-900">{rep.callCount} calls</div>
                                      <div className="text-xs text-gray-500">{rep.avgScore}% avg</div>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Recent Calls Section */}
                    <div className="bg-white shadow rounded-xl">
                      <div className="px-4 py-5 sm:p-6">
                        <div className="flex items-center justify-between mb-6">
                          <h3 className="text-lg leading-6 font-medium text-gray-900">
                            Recent Calls
                          </h3>
                          <Link
                            to="/mycalls"
                            className="text-sm font-medium text-indigo-600 hover:text-indigo-500"
                          >
                            View all →
                          </Link>
                        </div>
                        
                        {dashboardData.recentCalls.length > 0 ? (
                          <div className="overflow-hidden">
                            <table className="min-w-full divide-y divide-gray-200">
                              <thead className="bg-gray-50">
                                <tr>
                                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    Call ID
                                  </th>
                                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    Filename
                                  </th>
                                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    Sales Rep
                                  </th>
                                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    Upload Method
                                  </th>
                                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    Status
                                  </th>
                                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    Score
                                  </th>
                                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    Date
                                  </th>
                                </tr>
                              </thead>
                              <tbody className="bg-white divide-y divide-gray-200">
                                {dashboardData.recentCalls.map((call) => (
                                  <tr key={call.id} className="hover:bg-gray-50">
                                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                                      {call.id}
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                      {call.filename}
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                      {call.sales_rep_name || 'N/A'}
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap">
                                      <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                                        call.upload_method === 'manual' ? 'bg-blue-100 text-blue-800' : 'bg-green-100 text-green-800'
                                      }`}>
                                        {call.upload_method === 'manual' ? 'Manual' : 'S3 Auto'}
                                      </span>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap">
                                      <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                                        call.status === 'processed' ? 'bg-green-100 text-green-800' :
                                        call.status === 'processing' ? 'bg-yellow-100 text-yellow-800' :
                                        'bg-red-100 text-red-800'
                                      }`}>
                                        {call.status}
                                      </span>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                      {call.score ? `${call.score}%` : 'N/A'}
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                      {new Date(call.upload_date).toLocaleDateString()}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        ) : (
                          <div className="text-center py-8">
                            <p className="text-gray-500">No recent calls to display.</p>
                          </div>
                        )}
                      </div>
                    </div>
                  </>
                )}

              </div>
            </div>
          </main>
        </div>
      </div>
      </div>
    </>
  );
};

export default Dashboard;