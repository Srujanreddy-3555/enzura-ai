import React, { useState, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import apiService from '../services/api';
import { SkeletonTableRow } from './SkeletonLoader';
import ConfirmDialog from './ConfirmDialog';
import Sidebar from './Sidebar';
import UserHeader from './UserHeader';

const MyCalls = () => {
  const [activeItem, setActiveItem] = useState('My Calls');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('All'); // Can be 'All', 'PROCESSED', 'PROCESSING', or 'FAILED'
  const [callsData, setCallsData] = useState([]);
  const [insightsData, setInsightsData] = useState({}); // Store insights by call_id
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [deletingCall, setDeletingCall] = useState(null);
  const [confirmDialog, setConfirmDialog] = useState({ isOpen: false, onConfirm: null, title: '', message: '' });
  const navigate = useNavigate();
  
  // OPTIMIZED: Server-side pagination state for large call lists (200+ calls)
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage] = useState(20); // Show 20 calls per page for optimal performance
  const [totalCalls, setTotalCalls] = useState(0); // Total count from server

  // Mobile navigation items (for mobile menu only)
  const navigationItems = [
    { name: 'Dashboard', path: '/dashboard' },
    { name: 'My Calls', path: '/mycalls' },
    { name: 'Upload Call', path: '/uploadcall' },
    { name: 'Leaderboard', path: '/leaderboard' }
  ];


  // OPTIMIZED: Use ref to cancel pending requests on navigation
  const abortControllerRef = useRef(null);
  
  // Fetch calls data from API with auto-refresh
  useEffect(() => {
    const fetchCalls = async (showLoading = false) => {
      // Cancel previous request if still pending
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      
      // Create new abort controller
      abortControllerRef.current = new AbortController();
      
      try {
        if (showLoading) {
          setLoading(true);
        }
        // Convert statusFilter to uppercase for API (backend expects uppercase enum values)
        const apiStatusFilter = statusFilter === 'All' ? null : statusFilter.toUpperCase();
        // OPTIMIZED: Calculate skip for server-side pagination
        const skip = (currentPage - 1) * itemsPerPage;
        const response = await apiService.getCalls(apiStatusFilter, searchTerm || null, skip, itemsPerPage);
        
        // Validate response - now returns { calls: [], total: number, skip: number, limit: number }
        if (!response || !Array.isArray(response.calls)) {
          console.warn('Invalid calls response:', response);
          return; // Keep existing data
        }
        
        // CRITICAL: Set calls and total count immediately so UI renders fast
        setCallsData(response.calls);
        setTotalCalls(response.total || 0);
        setError('');
        
        // OPTIMIZED: Fetch insights in background (non-blocking) - don't wait for it
        const processedCalls = response.calls ? response.calls.filter(call => 
          call.status && (call.status.toLowerCase() === 'processed' || call.status.toUpperCase() === 'PROCESSED')
        ) : [];
        
        if (processedCalls.length > 0) {
          // Fetch insights asynchronously - don't block UI rendering
          apiService.getBatchInsights(processedCalls.map(call => call.id))
            .then((batchInsights) => {
              const insightsMap = {};
              Object.keys(batchInsights).forEach(callIdStr => {
                const callId = parseInt(callIdStr);
                if (batchInsights[callId]) {
                  insightsMap[callId] = batchInsights[callId];
                }
              });
              setInsightsData(prev => ({ ...prev, ...insightsMap }));
            })
            .catch((err) => {
              // Silently continue - insights will load later
              console.warn('Insights fetch failed, will retry:', err);
            });
        }
        
        // CRITICAL: Extract duration for PROCESSED calls WITHOUT duration IMMEDIATELY
        if (response.calls && response.calls.length > 0) {
          const processedCallsWithoutDuration = response.calls.filter(c => 
            (c.status === 'PROCESSED' || c.status === 'processed') && 
            (!c.duration || c.duration <= 0 || c.duration === null)
          );
          
          if (processedCallsWithoutDuration.length > 0) {
            console.log(`🔧 Found ${processedCallsWithoutDuration.length} PROCESSED calls without duration, extracting now...`);
            // Run duration extraction immediately - don't wait
            Promise.allSettled(
              processedCallsWithoutDuration.map(async (call) => {
                // Skip if already extracting
                if (extractingRef.current.has(call.id)) {
                  return { callId: call.id, skipped: true };
                }
                
                extractingRef.current.add(call.id);
                try {
                  console.log(`🔧 Extracting duration for call ${call.id} (${call.filename})...`);
                  const result = await apiService.extractCallDuration(call.id);
                  if (result && result.success && result.duration) {
                    console.log(`✅ Duration extracted for call ${call.id}: ${result.duration_formatted}`);
                    // Update the call in local state immediately
                    setCallsData(prevCalls =>
                      prevCalls.map(c =>
                        c.id === call.id
                          ? { ...c, duration: result.duration }
                          : c
                      )
                    );
                    extractingRef.current.delete(call.id);
                    return { callId: call.id, success: true, duration: result.duration };
                  } else {
                    console.warn(`⚠️ Duration extraction for call ${call.id} returned no success or duration`);
                    extractingRef.current.delete(call.id);
                    return { callId: call.id, success: false };
                  }
                } catch (err) {
                  // Don't log errors for invalid/corrupted files - these are expected for some calls
                  const errorMsg = err.message || 'Unknown error';
                  if (errorMsg.includes('invalid value') || errorMsg.includes('corrupted') || errorMsg.includes('unsupported')) {
                    console.warn(`⚠️ Duration extraction skipped for call ${call.id}: ${errorMsg}`);
                  } else {
                    console.error(`❌ Error extracting duration for call ${call.id}:`, err);
                  }
                  extractingRef.current.delete(call.id);
                  return { callId: call.id, success: false, error: errorMsg };
                }
              })
            ).then((results) => {
              const successCount = results.filter(r => r.status === 'fulfilled' && r.value.success).length;
              console.log(`✅ Duration extraction completed: ${successCount}/${processedCallsWithoutDuration.length} successful`);
              
              // Refresh after extraction to ensure UI is updated with latest data
              setTimeout(() => {
                const refreshSkip = (currentPage - 1) * itemsPerPage;
                apiService.getCalls(apiStatusFilter, searchTerm || null, refreshSkip, itemsPerPage)
                  .then(updatedResponse => {
                    if (updatedResponse && Array.isArray(updatedResponse.calls)) {
                      setCallsData(updatedResponse.calls);
                      setTotalCalls(updatedResponse.total || 0);
                      console.log(`✅ Refreshed calls data after duration extraction`);
                    }
                  })
                  .catch((err) => {
                    console.error('Refresh after duration extraction failed:', err);
                  });
              }, 1500);
            });
          }
        }
      } catch (err) {
        // Only log error if it's not an abort (abort is expected)
        if (err.name !== 'AbortError') {
          console.error('Failed to fetch calls:', err);
          if (showLoading) {
            const errorMessage = err.message || 'Failed to load calls. Please try again.';
            setError(errorMessage.includes('Authentication') ? errorMessage : 'Failed to load calls. Please check your connection and try again.');
            // Don't clear existing data on error - keep showing what we have
            setCallsData(prevCalls => {
              // Only clear if we have no data at all
              if (prevCalls.length === 0) {
                return [];
              }
              return prevCalls; // Keep existing data
            });
          }
        }
        // Don't show error on auto-refresh to avoid interrupting user
      } finally {
        if (showLoading) {
          setLoading(false);
        }
      }
    };

    // Fetch immediately with loading
    fetchCalls(true);

    // OPTIMIZED: Increased refresh interval to 5 seconds for better performance with large datasets
    // This reduces server load while still keeping data fresh
    const refreshInterval = setInterval(() => {
      fetchCalls(false);
    }, 5000);
    
    // Cleanup: cancel pending requests and clear interval
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      clearInterval(refreshInterval);
    };
  }, [statusFilter, searchTerm, currentPage, itemsPerPage]); // Added currentPage dependency for server-side pagination
  
  // Separate effect to monitor callsData and automatically extract duration for PROCESSED calls without it
  // Use a ref to track which calls we're already extracting to prevent infinite loops
  const extractingRef = useRef(new Set());
  
  useEffect(() => {
    // Check if there are PROCESSED calls without duration in current state
    const needsDuration = callsData.filter(call => 
      (call.status === 'PROCESSED' || call.status === 'processed') && 
      (!call.duration || call.duration <= 0) &&
      !extractingRef.current.has(call.id) // Don't extract if already extracting
    );
    
    if (needsDuration.length > 0) {
      console.log(`🔄 Found ${needsDuration.length} PROCESSED calls without duration, triggering extraction...`);
      
      // Mark these calls as being extracted
      needsDuration.forEach(call => extractingRef.current.add(call.id));
      
      // Trigger extraction for each call
      Promise.allSettled(
        needsDuration.map(async (call) => {
          try {
            console.log(`🔧 Auto-extracting duration for call ${call.id}...`);
            const result = await apiService.extractCallDuration(call.id);
            if (result && result.success) {
              console.log(`✅ Duration extracted for call ${call.id}: ${result.duration_formatted}`);
              // Update the call in local state immediately
              setCallsData(prevCalls => 
                prevCalls.map(c => 
                  c.id === call.id 
                    ? { ...c, duration: result.duration }
                    : c
                )
              );
              // Remove from extracting set
              extractingRef.current.delete(call.id);
              return { callId: call.id, success: true };
            }
            extractingRef.current.delete(call.id);
            return { callId: call.id, success: false };
          } catch (err) {
            console.error(`❌ Error extracting duration for call ${call.id}:`, err);
            extractingRef.current.delete(call.id);
            return { callId: call.id, success: false };
          }
        })
      ).then(() => {
        // Refresh after extraction to ensure UI is updated
        setTimeout(async () => {
          try {
            const apiStatusFilter = statusFilter === 'All' ? null : statusFilter.toUpperCase();
            const refreshSkip = (currentPage - 1) * itemsPerPage;
            const response = await apiService.getCalls(apiStatusFilter, searchTerm || null, refreshSkip, itemsPerPage);
            if (response && Array.isArray(response.calls)) {
              setCallsData(response.calls);
              setTotalCalls(response.total || 0);
            }
          } catch (err) {
            console.error('Refresh failed:', err);
          }
        }, 2000);
      });
    }
  }, [callsData, statusFilter, searchTerm, currentPage, itemsPerPage]); // Include pagination dependencies

  // Also refresh when component becomes visible (user navigates to this page)
  useEffect(() => {
    const handleVisibilityChange = async () => {
      if (!document.hidden) {
        // Page is now visible, refresh calls
        try {
          const apiStatusFilter = statusFilter === 'All' ? null : statusFilter.toUpperCase();
          const skip = (currentPage - 1) * itemsPerPage;
          const response = await apiService.getCalls(apiStatusFilter, searchTerm || null, skip, itemsPerPage);
          if (response && Array.isArray(response.calls)) {
            setCallsData(response.calls);
            setTotalCalls(response.total || 0);
          }
        } catch (err) {
          console.error('Failed to refresh calls on visibility change:', err);
        }
      }
    };
    
    document.addEventListener('visibilitychange', handleVisibilityChange);
    
    // Also refresh when page gains focus (user switches back to tab)
    window.addEventListener('focus', handleVisibilityChange);
    
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('focus', handleVisibilityChange);
    };
  }, [statusFilter, searchTerm, currentPage, itemsPerPage]);


  const getScoreColor = (score) => {
    if (score >= 90) return 'text-green-600 font-semibold';
    if (score >= 70) return 'text-orange-600 font-semibold';
    return 'text-red-600 font-semibold';
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'processed':
      case 'PROCESSED':
        return 'bg-green-100 text-green-800';
      case 'processing':
      case 'PROCESSING':
        return 'bg-yellow-100 text-yellow-800';
      case 'failed':
      case 'FAILED':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getSentimentColor = (sentiment) => {
    if (!sentiment) return 'bg-gray-100 text-gray-800';
    const sentimentLower = String(sentiment).toLowerCase();
    switch (sentimentLower) {
      case 'positive':
        return 'bg-green-100 text-green-800';
      case 'negative':
        return 'bg-red-100 text-red-800';
      case 'neutral':
        return 'bg-blue-100 text-blue-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  // OPTIMIZED: Server-side pagination - no client-side filtering needed
  // All filtering and pagination is done on the server
  const paginatedCalls = callsData; // Already paginated from server
  const totalPages = Math.ceil(totalCalls / itemsPerPage);

  // Reset to page 1 when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [searchTerm, statusFilter]);

  const handleViewDetails = (callId) => {
    navigate(`/calldetail/${callId}`);
  };

  const handleDeleteCall = (callId) => {
    setConfirmDialog({
      isOpen: true,
      title: 'Delete Call',
      message: 'Are you sure you want to delete this call? This action cannot be undone.',
      confirmText: 'Delete',
      cancelText: 'Cancel',
      onConfirm: async () => {
        try {
          setDeletingCall(callId);
          setError(''); // Clear any previous errors
          setSuccess(''); // Clear any previous success messages
          
          await apiService.deleteCall(callId);
          
          // OPTIMIZED: Remove the call from local state immediately
          setCallsData(prevCalls => prevCalls.filter(call => call.id !== callId));
          
          // Remove insights for deleted call
          setInsightsData(prev => {
            const newInsights = { ...prev };
            delete newInsights[callId];
            return newInsights;
          });
          
          setSuccess('Call deleted successfully!');
          
          // CRITICAL: Immediately refresh to ensure ALL users see the change
          // This ensures deletes are visible everywhere (admin, client, rep)
          // No delay - refresh immediately after cache is cleared
          try {
            const apiStatusFilter = statusFilter === 'All' ? null : statusFilter.toUpperCase();
            const skip = (currentPage - 1) * itemsPerPage;
            const response = await apiService.getCalls(apiStatusFilter, searchTerm || null, skip, itemsPerPage);
            if (response && Array.isArray(response.calls)) {
              setCallsData(response.calls);
              setTotalCalls(response.total || 0);
            }
          } catch (refreshErr) {
            console.warn('Refresh after delete failed:', refreshErr);
            // Still try to fetch after a small delay as fallback
            setTimeout(async () => {
              try {
                const apiStatusFilter = statusFilter === 'All' ? null : statusFilter.toUpperCase();
                const skip = (currentPage - 1) * itemsPerPage;
                const response = await apiService.getCalls(apiStatusFilter, searchTerm || null, skip, itemsPerPage);
                if (response && Array.isArray(response.calls)) {
                  setCallsData(response.calls);
                  setTotalCalls(response.total || 0);
                }
              } catch (retryErr) {
                console.error('Retry refresh after delete also failed:', retryErr);
              }
            }, 500);
          }
          
          // Clear success message after 3 seconds
          setTimeout(() => setSuccess(''), 3000);
        } catch (err) {
          console.error('Failed to delete call:', err);
          console.error('Error details:', {
            message: err.message,
            status: err.status,
            response: err.response
          });
          
          // Extract error message from the error object
          let errorMessage = 'Failed to delete call. Please try again.';
          
          if (err.message) {
            errorMessage = err.message;
          } else if (err.detail) {
            errorMessage = err.detail;
          }
          
          setError(errorMessage);
        } finally {
          setDeletingCall(null);
        }
      }
    });
  };

  const handleDeleteAllCalls = () => {
    setConfirmDialog({
      isOpen: true,
      title: 'Delete All Calls',
      message: `Are you sure you want to delete ALL ${totalCalls} calls? This action cannot be undone!`,
      confirmText: 'Delete All',
      cancelText: 'Cancel',
      onConfirm: async () => {
        try {
          setLoading(true);
          setError('');
          
          // Delete all calls one by one
          const deletePromises = callsData.map(call => apiService.deleteCall(call.id));
          await Promise.all(deletePromises);
          
          // Clear the local state
          setCallsData([]);
          setInsightsData({});
        } catch (err) {
          console.error('Failed to delete all calls:', err);
          setError('Failed to delete some calls. Please try again.');
        } finally {
          setLoading(false);
        }
      }
    });
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Mobile Header */}
      <div className="lg:hidden bg-white shadow-sm border-b border-gray-200">
        <div className="flex items-center justify-between px-4 py-3">
          <h1 className="text-lg font-semibold text-gray-900">My Calls</h1>
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
                {/* Page Header */}
                <div className="mb-8">
                  <h1 className="text-2xl font-bold text-gray-900">My Calls</h1>
                  <p className="mt-1 text-sm text-gray-500">
                    View and manage all your call recordings and analytics.
                  </p>
                </div>

                {/* Search and Filter Controls */}
                <div className="mb-6 bg-white rounded-2xl shadow-lg border border-gray-200 p-6 relative z-10">
                  <div className="flex flex-col sm:flex-row gap-4">
                    {/* Search Box */}
                    <div className="flex-1">
                      <label className="block text-sm font-semibold text-gray-700 mb-2">
                        Search Calls
                      </label>
                      <div className="relative">
                        <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                          <svg className="h-5 w-5 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                          </svg>
                        </div>
                        <input
                          type="text"
                          placeholder="Search by Call ID or Filename..."
                          value={searchTerm}
                          onChange={(e) => setSearchTerm(e.target.value)}
                          className="block w-full pl-12 pr-4 py-3 border-2 border-gray-200 rounded-xl bg-gray-50 placeholder-gray-400 focus:outline-none focus:border-purple-500 focus:bg-white focus:ring-2 focus:ring-purple-200 transition-all duration-200 text-sm font-medium"
                        />
                      </div>
                    </div>
                    
                    {/* Status Filter */}
                    <div className="sm:w-56">
                      <label className="block text-sm font-semibold text-gray-700 mb-2">
                        Filter by Status
                      </label>
                      <div className="relative">
                        <select
                          value={statusFilter}
                          onChange={(e) => setStatusFilter(e.target.value)}
                          className="block w-full px-4 py-3 border-2 border-gray-200 rounded-xl bg-gray-50 focus:outline-none focus:border-purple-500 focus:bg-white focus:ring-2 focus:ring-purple-200 transition-all duration-200 text-sm font-medium appearance-none cursor-pointer"
                        >
                          <option value="All">All Status</option>
                          <option value="PROCESSED">Processed</option>
                          <option value="PROCESSING">Processing</option>
                          <option value="FAILED">Failed</option>
                        </select>
                        <div className="absolute inset-y-0 right-0 pr-4 flex items-center pointer-events-none">
                          <svg className="h-5 w-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                          </svg>
                        </div>
                      </div>
                    </div>
                    
                    {/* Delete All Button */}
                    {callsData.length > 0 && (
                      <div className="flex items-end">
                        <button
                          onClick={handleDeleteAllCalls}
                          className="px-6 py-3 bg-gradient-to-r from-red-500 to-red-600 text-white text-sm font-semibold rounded-xl hover:from-red-600 hover:to-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 transition-all duration-200 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 flex items-center space-x-2"
                          title="Delete All Calls (Testing Only)"
                        >
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                          <span>Delete All</span>
                        </button>
                      </div>
                    )}
                  </div>
                </div>

                {/* Skeleton Loader - Show while initial data is loading */}
                {loading && callsData.length === 0 && (
                  <div className="bg-white shadow rounded-xl overflow-hidden">
                    <div className="px-4 py-5 sm:p-6">
                      <div className="overflow-x-auto">
                        <table className="min-w-full divide-y divide-gray-200">
                          <thead className="bg-gray-50">
                            <tr>
                              {['Call ID', 'Filename', 'Status', 'Score', 'Sentiment', 'Duration', 'Date', 'Actions'].map((header) => (
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
                )}

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

                {/* Success State */}
                {success && (
                  <div className="bg-green-50 border border-green-200 rounded-xl p-6 mb-6">
                    <div className="flex items-center">
                      <div className="flex-shrink-0">
                        <svg className="h-5 w-5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                        </svg>
                      </div>
                      <div className="ml-3">
                        <p className="text-sm text-green-800">{success}</p>
                      </div>
                    </div>
                  </div>
                )}

                {/* Calls Table */}
                {!loading && !error && (
                  <div className="bg-white shadow-xl rounded-2xl border border-gray-200 overflow-hidden">
                    <div className="px-6 py-5 bg-gradient-to-r from-purple-50 to-blue-50 border-b border-gray-200">
                      <h2 className="text-lg font-bold text-gray-900">Call Records</h2>
                      <p className="text-sm text-gray-600 mt-1">{totalCalls} {totalCalls === 1 ? 'call' : 'calls'} found</p>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gradient-to-r from-gray-50 to-gray-100">
                          <tr>
                            <th className="px-6 py-4 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                              Call ID
                            </th>
                            <th className="px-6 py-4 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                              Filename
                            </th>
                            <th className="px-6 py-4 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                              Upload Date
                            </th>
                            <th className="px-6 py-4 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                              Duration
                            </th>
                            <th className="px-6 py-4 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                              Score
                            </th>
                            <th className="px-6 py-4 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                              Sentiment
                            </th>
                            <th className="px-6 py-4 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                              Status
                            </th>
                            <th className="px-6 py-4 text-left text-xs font-bold text-gray-700 uppercase tracking-wider">
                              Actions
                            </th>
                          </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-100">
                          {paginatedCalls.map((call, index) => (
                            <tr 
                              key={call.id} 
                              className={`hover:bg-gradient-to-r hover:from-purple-50 hover:to-blue-50 transition-all duration-200 cursor-pointer border-l-4 border-transparent hover:border-purple-500 ${
                                index % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'
                              }`}
                              onClick={() => handleViewDetails(call.id)}
                            >
                              <td className="px-6 py-4 whitespace-nowrap">
                                <span className="text-sm font-bold text-purple-600 bg-purple-100 px-3 py-1.5 rounded-lg">
                                  #{call.id}
                                </span>
                              </td>
                              <td className="px-6 py-4">
                                <div className="text-sm font-semibold text-gray-900 max-w-xs truncate" title={call.filename}>
                                  {call.filename}
                                </div>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap">
                                <div className="text-sm text-gray-600 font-medium">
                                  {new Date(call.upload_date).toLocaleDateString()}
                                </div>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap">
                                {(() => {
                                  // Display duration in MM:SS format
                                  const duration = call.duration;
                                  
                                  // Debug logging for missing duration
                                  if (duration === null || duration === undefined || duration === 0) {
                                    // Log once per call to avoid spam
                                    if (call.status === 'PROCESSED' || call.status === 'processed') {
                                      console.log(`⏱️ Call ${call.id} (${call.filename}): duration missing, status: ${call.status}`);
                                    }
                                  }
                                  
                                  // Handle both number and string types
                                  const durationNum = typeof duration === 'string' ? parseInt(duration) : duration;
                                  if (durationNum && durationNum > 0 && !isNaN(durationNum)) {
                                    const minutes = Math.floor(durationNum / 60);
                                    const seconds = durationNum % 60;
                                    return (
                                      <span className="text-sm font-semibold text-blue-600 bg-blue-50 px-3 py-1.5 rounded-lg">
                                        {minutes}:{seconds.toString().padStart(2, '0')}
                                      </span>
                                    );
                                  }
                                  return <span className="text-sm text-gray-400 font-medium bg-gray-100 px-3 py-1.5 rounded-lg">N/A</span>;
                                })()}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap">
                                {call.score ? (
                                  <div className="flex items-center space-x-2">
                                    <span className={`text-sm font-bold px-3 py-1.5 rounded-lg ${getScoreColor(call.score)}`}>
                                      {call.score}%
                                    </span>
                                  </div>
                                ) : (
                                  <span className="text-sm text-gray-400 font-medium bg-gray-100 px-3 py-1.5 rounded-lg">N/A</span>
                                )}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap">
                                {(() => {
                                  const insights = insightsData[call.id];
                                  const sentiment = insights?.sentiment || call.sentiment || null;
                                  return sentiment ? (
                                    <span className={`inline-flex px-3 py-1.5 text-xs font-bold rounded-lg ${getSentimentColor(sentiment)}`}>
                                      {String(sentiment).charAt(0).toUpperCase() + String(sentiment).slice(1).toLowerCase()}
                                    </span>
                                  ) : (
                                    <span className="inline-flex px-3 py-1.5 text-xs font-bold rounded-lg bg-gray-100 text-gray-600">
                                      N/A
                                    </span>
                                  );
                                })()}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap">
                                <span className={`inline-flex px-3 py-1.5 text-xs font-bold rounded-lg ${getStatusColor(call.status)}`}>
                                  {String(call.status).charAt(0).toUpperCase() + String(call.status).slice(1).toLowerCase()}
                                </span>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                                <div className="flex space-x-3">
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleViewDetails(call.id);
                                    }}
                                    className="p-2 text-indigo-600 bg-indigo-50 rounded-lg hover:bg-indigo-100 hover:text-indigo-700 transition-all duration-200 transform hover:scale-110"
                                    title="View Details"
                                  >
                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                                    </svg>
                                  </button>
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleDeleteCall(call.id);
                                    }}
                                    disabled={deletingCall === call.id}
                                    className={`p-2 rounded-lg transition-all duration-200 transform hover:scale-110 ${
                                      deletingCall === call.id
                                        ? 'text-gray-400 bg-gray-100 cursor-not-allowed'
                                        : 'text-red-600 bg-red-50 hover:bg-red-100 hover:text-red-700'
                                    }`}
                                    title="Delete Call"
                                  >
                                    {deletingCall === call.id ? (
                                      <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                      </svg>
                                    ) : (
                                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                      </svg>
                                    )}
                                  </button>
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    
                    {/* Pagination Controls */}
                    {totalPages > 1 && (
                      <div className="px-6 py-4 bg-gray-50 border-t border-gray-200 flex items-center justify-between">
                        <div className="text-sm text-gray-600">
                          Showing {(currentPage - 1) * itemsPerPage + 1} to {Math.min(currentPage * itemsPerPage, totalCalls)} of {totalCalls} calls
                        </div>
                        <div className="flex items-center space-x-2">
                          <button
                            onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                            disabled={currentPage === 1}
                            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                          >
                            Previous
                          </button>
                          <div className="flex items-center space-x-1">
                            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                              let pageNum;
                              if (totalPages <= 5) {
                                pageNum = i + 1;
                              } else if (currentPage <= 3) {
                                pageNum = i + 1;
                              } else if (currentPage >= totalPages - 2) {
                                pageNum = totalPages - 4 + i;
                              } else {
                                pageNum = currentPage - 2 + i;
                              }
                              return (
                                <button
                                  key={pageNum}
                                  onClick={() => setCurrentPage(pageNum)}
                                  className={`px-3 py-2 text-sm font-medium rounded-lg transition-colors ${
                                    currentPage === pageNum
                                      ? 'bg-gradient-to-r from-purple-600 to-blue-600 text-white'
                                      : 'text-gray-700 bg-white border border-gray-300 hover:bg-gray-50'
                                  }`}
                                >
                                  {pageNum}
                                </button>
                              );
                            })}
                          </div>
                          <button
                            onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                            disabled={currentPage === totalPages}
                            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                          >
                            Next
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Empty State (if no calls) */}
                {!loading && !error && paginatedCalls.length === 0 && totalCalls === 0 && (
                  <div className="text-center py-12">
                    <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                    </svg>
                    <h3 className="mt-2 text-sm font-medium text-gray-900">No calls found</h3>
                    <p className="mt-1 text-sm text-gray-500">Get started by uploading your first call recording.</p>
                    <div className="mt-6">
                      <Link
                        to="/uploadcall"
                        className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                      >
                        <svg className="-ml-1 mr-2 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6H16a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                        </svg>
                        Upload Call
                      </Link>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </main>
        </div>
      </div>

      {/* Confirmation Dialog */}
      <ConfirmDialog
        isOpen={confirmDialog.isOpen}
        onClose={() => setConfirmDialog({ isOpen: false, onConfirm: null, title: '', message: '' })}
        onConfirm={confirmDialog.onConfirm || (() => {})}
        title={confirmDialog.title}
        message={confirmDialog.message}
        confirmText={confirmDialog.confirmText || 'Delete'}
        cancelText={confirmDialog.cancelText || 'Cancel'}
        type="danger"
      />
    </div>
  );
};

export default MyCalls;
