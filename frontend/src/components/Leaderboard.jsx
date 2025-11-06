import React, { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import apiService from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import Sidebar from './Sidebar';
import UserHeader from './UserHeader';

const Leaderboard = () => {
  const { user } = useAuth();
  const [activeItem, setActiveItem] = useState('Leaderboard');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [leaderboardData, setLeaderboardData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Mobile navigation items (for mobile menu only)
  const navigationItems = [
    { name: 'Dashboard', path: '/dashboard' },
    { name: 'My Calls', path: '/mycalls' },
    { name: 'Upload Call', path: '/uploadcall' },
    { name: 'Leaderboard', path: '/leaderboard' }
  ];

  // OPTIMIZED: Fetch leaderboard data - INSTANT load with cache, update in background
  const hasLoadedDataRef = useRef(false);
  const abortControllerRef = useRef(null);
  const isInitialMount = useRef(true);
  const [isInitialLoad, setIsInitialLoad] = useState(true);
  
  useEffect(() => {
    const fetchLeaderboard = async (skipCache = false) => {
      // Cancel previous request if still pending
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      
      // Create new abort controller for this request
      abortControllerRef.current = new AbortController();
      
      try {
        setError('');
        
        // Fetch leaderboard - all roles can see it, but reps see only top 3
        const response = await apiService.getLeaderboard(skipCache ? { skipCache: true } : {});
        
        // Validate response to prevent null data
        if (!response || typeof response !== 'object') {
          console.warn('Invalid leaderboard response:', response);
          return; // Keep existing data
        }
        
        const leaderboard = response.leaderboard;
        
        // OPTIMIZED: Only update if we have valid data (prevent null values)
        if (Array.isArray(leaderboard)) {
          setLeaderboardData(leaderboard);
          hasLoadedDataRef.current = true; // Mark as successfully loaded
        } else {
          console.warn('Leaderboard data is not an array:', leaderboard);
          // Keep existing data, don't clear it
        }
      } catch (err) {
        // Only log error if it's not an abort
        if (err.name !== 'AbortError') {
          console.error('Failed to fetch leaderboard:', err);
          // Only show error if we've never successfully loaded data
          if (!hasLoadedDataRef.current) {
            setError('Failed to load leaderboard data. Please try again.');
          }
        }
        // Don't clear existing data on error - keep showing what we have
      } finally {
        // Always hide loading after first fetch
        setLoading(false);
      }
    };

    // CRITICAL: On initial mount, try to get cached data INSTANTLY
    if (isInitialMount.current) {
      isInitialMount.current = false;
      
      // Try to get cached data immediately (cache returns Promise.resolve which is instant)
      apiService.getLeaderboard().then((cachedResponse) => {
        if (cachedResponse && cachedResponse.leaderboard && Array.isArray(cachedResponse.leaderboard) && cachedResponse.leaderboard.length > 0) {
          // If we have cached data, show it INSTANTLY
          setLeaderboardData(cachedResponse.leaderboard);
          hasLoadedDataRef.current = true;
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
      fetchLeaderboard(true).then(() => {
        setIsInitialLoad(false);
      }); // Skip cache to get fresh data
    } else {
      // Subsequent mounts: fetch with cache (will be instant if cached)
      fetchLeaderboard().then(() => {
        setIsInitialLoad(false);
      });
    }

    // Auto-refresh every 2 seconds (optimized from 1 second for better performance)
    const refreshInterval = setInterval(() => fetchLeaderboard(true), 2000); // Skip cache for refresh
    
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      clearInterval(refreshInterval);
    };
  }, [user]); // Only depend on user

  // Get top 3 for cards
  const topThree = leaderboardData.slice(0, 3);
  // Get all data for table (or limit for reps)
  const tableData = user?.role?.toLowerCase() === 'rep' 
    ? leaderboardData.slice(0, 3) 
    : leaderboardData;

  // Medal component for top 3
  const MedalIcon = ({ rank, className = "w-12 h-12" }) => {
    if (rank === 1) {
      return (
        <div className={`${className} relative`}>
          <svg viewBox="0 0 64 64" className="w-full h-full">
            <circle cx="32" cy="32" r="28" fill="#FFD700" stroke="#FFA500" strokeWidth="2"/>
            <text x="32" y="42" textAnchor="middle" fontSize="24" fontWeight="bold" fill="#000">1</text>
            <path d="M 32 8 L 28 4 L 36 4 Z" fill="#0066CC"/>
            <path d="M 28 4 L 28 12 L 36 12 L 36 4 Z" fill="#0066CC"/>
          </svg>
        </div>
      );
    } else if (rank === 2) {
      return (
        <div className={`${className} relative`}>
          <svg viewBox="0 0 64 64" className="w-full h-full">
            <circle cx="32" cy="32" r="28" fill="#C0C0C0" stroke="#808080" strokeWidth="2"/>
            <text x="32" y="42" textAnchor="middle" fontSize="24" fontWeight="bold" fill="#000">2</text>
            <path d="M 32 8 L 28 4 L 36 4 Z" fill="#0066CC"/>
            <path d="M 28 4 L 28 12 L 36 12 L 36 4 Z" fill="#0066CC"/>
          </svg>
        </div>
      );
    } else if (rank === 3) {
      return (
        <div className={`${className} relative`}>
          <svg viewBox="0 0 64 64" className="w-full h-full">
            <circle cx="32" cy="32" r="28" fill="#CD7F32" stroke="#8B4513" strokeWidth="2"/>
            <text x="32" y="42" textAnchor="middle" fontSize="24" fontWeight="bold" fill="#000">3</text>
            <path d="M 32 8 L 28 4 L 36 4 Z" fill="#0066CC"/>
            <path d="M 28 4 L 28 12 L 36 12 L 36 4 Z" fill="#0066CC"/>
          </svg>
        </div>
      );
    }
    return null;
  };

  // Get badges for achievements
  const getBadges = (rep, rank) => {
    const badges = [];
    
    // Medal badge
    if (rank === 1) badges.push({ type: 'medal', rank: 1, color: 'gold' });
    else if (rank === 2) badges.push({ type: 'medal', rank: 2, color: 'silver' });
    else if (rank === 3) badges.push({ type: 'medal', rank: 3, color: 'bronze' });
    
    // Achievement badges (example logic)
    if (rep.total_calls >= 150) badges.push({ type: 'text', label: 'Best', color: 'blue' });
    if (rep.total_calls >= 140) badges.push({ type: 'text', label: 'Most', color: 'blue' });
    if (rep.average_score >= 85 && rank <= 3) badges.push({ type: 'text', label: 'Top', color: 'blue' });
    
    return badges;
  };


  return (
    <div className="min-h-screen bg-gray-50">
      {/* Mobile Header */}
      <div className="lg:hidden bg-white shadow-sm border-b border-gray-200">
        <div className="flex items-center justify-between px-4 py-3">
          <h1 className="text-lg font-semibold text-gray-900">Leaderboard</h1>
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-2 rounded-md text-gray-600 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-indigo-500"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
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
                {/* Page Header with Trophy and Title */}
                <div className="mb-8">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-4">
                      {/* Trophy Icon */}
                      <div className="text-5xl">🏆</div>
                      <div>
                        <h1 className="text-4xl font-bold text-gray-900" style={{ fontFamily: 'serif' }}>
                          Leaderboard
                        </h1>
                        <p className="mt-2 text-sm text-gray-500">
                          Top performing representatives
                        </p>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Error State */}
                {error && (
                  <div className="bg-red-50 border border-red-200 rounded-xl p-6 mb-6">
                    <div className="flex items-center">
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

                {/* Skeleton Loader */}
                {(loading || isInitialLoad) && leaderboardData.length === 0 && (
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                    {[1, 2, 3].map((i) => (
                      <div key={i} className="bg-white rounded-xl shadow-lg p-6 animate-pulse">
                        <div className="h-16 bg-gray-200 rounded mb-4"></div>
                        <div className="h-6 bg-gray-200 rounded mb-2"></div>
                        <div className="h-4 bg-gray-200 rounded mb-4"></div>
                        <div className="h-20 bg-gray-200 rounded"></div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Top 3 Cards */}
                {!loading && !error && topThree.length > 0 && (
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                    {topThree.map((rep, index) => {
                      const rank = index + 1;
                      return (
                        <div 
                          key={rep.name || index}
                          className="bg-white rounded-xl shadow-lg overflow-hidden relative"
                        >
                          {/* Purple gradient in top-right corner */}
                          <div className="absolute top-0 right-0 w-24 h-24 bg-gradient-to-br from-purple-200 to-blue-200 rounded-bl-full opacity-30"></div>
                          
                          <div className="p-6 relative">
                            {/* Medal at top center */}
                            <div className="flex justify-center mb-4">
                              <MedalIcon rank={rank} className="w-16 h-16" />
                            </div>
                            
                            {/* Name */}
                            <h3 className="text-2xl font-bold text-gray-900 text-center mb-2" style={{ fontFamily: 'serif' }}>
                              {rep.name || 'Unknown Representative'}
                            </h3>
                            
                            {/* Client Name */}
                            <p className="text-sm text-gray-500 text-center mb-6">
                              {rep.client_name || 'Unknown Client'}
                            </p>
                            
                            {/* Metrics Box */}
                            <div className="bg-gray-50 rounded-lg p-4 space-y-4">
                              <div className="flex justify-between items-center">
                                <span className="text-sm text-gray-600">Calls Completed</span>
                                <span className="text-lg font-bold text-gray-900">{rep.total_calls || 0}</span>
                              </div>
                              <div className="flex justify-between items-center">
                                <span className="text-sm text-gray-600">Avg Quality Score</span>
                                <span className="text-lg font-bold text-gray-900">
                                  {((rep.average_score || 0) / 10).toFixed(1)}
                                </span>
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* Full Rankings Table */}
                {!loading && !error && (
                  <div className="bg-white rounded-xl shadow-lg overflow-hidden">
                    <div className="px-6 py-4 border-b border-gray-200">
                      <h3 className="text-lg font-semibold text-gray-900">Full Rankings</h3>
                    </div>
                    
                    {tableData.length === 0 ? (
                      <div className="px-6 py-12 text-center">
                        <div className="mx-auto w-24 h-24 bg-gray-100 rounded-full flex items-center justify-center mb-4">
                          <svg className="w-12 h-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" />
                          </svg>
                        </div>
                        <h3 className="text-lg font-semibold text-gray-900 mb-2">No rankings yet</h3>
                        <p className="text-sm text-gray-500 mb-6">
                          Rankings will appear here once calls are processed with scores.
                        </p>
                      </div>
                    ) : (
                      <div className="overflow-x-auto">
                        <table className="min-w-full divide-y divide-gray-200">
                          <thead className="bg-gray-50">
                            <tr>
                              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                #
                              </th>
                              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                Rep Name
                              </th>
                              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                Client
                              </th>
                              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                Calls
                              </th>
                              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                Quality Score
                              </th>
                              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                Badges
                              </th>
                            </tr>
                          </thead>
                          <tbody className="bg-white divide-y divide-gray-200">
                            {tableData.map((rep, index) => {
                              const rank = index + 1;
                              const badges = getBadges(rep, rank);
                              return (
                                <tr key={rep.name || index} className="hover:bg-gray-50 transition-colors">
                                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                                    {rank}
                                  </td>
                                  <td className="px-6 py-4 whitespace-nowrap text-sm font-semibold text-gray-900">
                                    {rep.name || 'Unknown Representative'}
                                  </td>
                                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                    {rep.client_name || 'Unknown Client'}
                                  </td>
                                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                    {rep.total_calls || 0}
                                  </td>
                                  <td className="px-6 py-4 whitespace-nowrap">
                                    <span className="text-sm font-bold text-gray-900">
                                      {((rep.average_score || 0) / 10).toFixed(1)}
                                    </span>
                                  </td>
                                  <td className="px-6 py-4 whitespace-nowrap">
                                    <div className="flex items-center space-x-2">
                                      {badges.map((badge, badgeIndex) => {
                                        if (badge.type === 'medal') {
                                          return (
                                            <MedalIcon key={badgeIndex} rank={badge.rank} className="w-8 h-8" />
                                          );
                                        } else if (badge.type === 'text') {
                                          return (
                                            <span
                                              key={badgeIndex}
                                              className="inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium bg-blue-100 text-blue-800"
                                            >
                                              {badge.label}
                                            </span>
                                          );
                                        }
                                        return null;
                                      })}
                                    </div>
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </main>
        </div>
      </div>
    </div>
  );
};

export default Leaderboard;
