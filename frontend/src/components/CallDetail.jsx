import React, { useState, useEffect, useCallback } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import apiService from '../services/api';
import { SkeletonCallDetailCard } from './SkeletonLoader';
import Sidebar from './Sidebar';
import UserHeader from './UserHeader';

const CallDetail = () => {
  const { id } = useParams();
  const [activeItem, setActiveItem] = useState('Call Detail');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  // OPTIMIZED: Start with empty data instead of null, show UI immediately!
  const [callData, setCallData] = useState(null);
  const [transcript, setTranscript] = useState(null);
  const [insights, setInsights] = useState(null);
  
  // DEBUG: Log whenever insights state changes
  useEffect(() => {
    console.log('🔄 INSIGHTS STATE CHANGED:', {
      value: insights,
      type: typeof insights,
      isNull: insights === null,
      isUndefined: insights === undefined,
      keys: insights ? Object.keys(insights) : 'none',
      keyCount: insights ? Object.keys(insights).length : 0
    });
  }, [insights]);
  // OPTIMIZED: No loading state - show UI immediately!
  const [error, setError] = useState('');
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastRefreshTime, setLastRefreshTime] = useState(null);
  const [audioUrl, setAudioUrl] = useState(null);
  const [isLoadingPlay, setIsLoadingPlay] = useState(false);
  const [isLoadingDownload, setIsLoadingDownload] = useState(false);
  const { t } = useTranslation();

  // Mobile navigation items (for mobile menu only)
  const navigationItems = [
    { name: 'Dashboard', path: '/dashboard' },
    { name: 'My Calls', path: '/mycalls' },
    { name: 'Upload Call', path: '/uploadcall' },
    { name: 'Leaderboard', path: '/leaderboard' }
  ];


  // OPTIMIZED: Fetch call data - NO LOADING SPINNER! Show UI immediately, update in background
  const fetchCallData = useCallback(async (showLoading = false) => {
      try {
      // Don't show loading spinner - data loads in background
        setError('');
        
      // OPTIMIZED: Fetch call details, transcript, and insights in parallel (faster!)
        console.log('🚀 Starting to fetch call data for ID:', id);
        const [callResponse, transcriptResponse, insightsResponse] = await Promise.allSettled([
          apiService.getCallById(id),
          apiService.getTranscriptByCallId(id),
          apiService.getInsightByCallId(id)
        ]);
        
        console.log('📦 All API calls completed:');
        console.log('   Call:', callResponse.status);
        console.log('   Transcript:', transcriptResponse.status);
        console.log('   Insights:', insightsResponse.status);
        console.log('   Insights response VALUE:', insightsResponse.status === 'fulfilled' ? insightsResponse.value : 'FAILED');
        console.log('   Insights response TYPE:', insightsResponse.status === 'fulfilled' ? typeof insightsResponse.value : 'N/A');
        console.log('   Insights response is NULL?', insightsResponse.status === 'fulfilled' ? (insightsResponse.value === null) : 'N/A');
        console.log('   Insights response is UNDEFINED?', insightsResponse.status === 'fulfilled' ? (insightsResponse.value === undefined) : 'N/A');
        if (insightsResponse.status === 'fulfilled' && insightsResponse.value) {
          console.log('   Insights response KEYS:', Object.keys(insightsResponse.value));
          console.log('   Insights response FIRST 5 KEYS:', Object.keys(insightsResponse.value).slice(0, 5));
        }
        
        if (callResponse.status === 'fulfilled') {
          setCallData(callResponse.value);
        // Update last refresh time
        setLastRefreshTime(new Date());
        
        // Auto-disable refresh if call is fully processed
        if (callResponse.value.status === 'processed' && 
            transcriptResponse.status === 'fulfilled' && 
            insightsResponse.status === 'fulfilled') {
          setAutoRefresh(false);
        }
        } else {
          console.error('Failed to fetch call:', callResponse.reason);
        if (showLoading) {
          setError('Failed to load call details');
        }
        }
        
        if (transcriptResponse.status === 'fulfilled') {
          setTranscript(transcriptResponse.value);
        } else {
          console.error('Failed to fetch transcript:', transcriptResponse.reason);
        }
        
      if (insightsResponse.status === 'fulfilled') {
        const insightsData = insightsResponse.value;
        console.log('✅✅✅ INSIGHTS API RESPONSE RECEIVED ✅✅✅');
        console.log('   Status: fulfilled');
        console.log('   Data:', insightsData);
        console.log('   Type:', typeof insightsData);
        console.log('   Is null:', insightsData === null);
        console.log('   Is undefined:', insightsData === undefined);
        console.log('   Is object:', typeof insightsData === 'object');
        console.log('   Keys:', insightsData ? Object.keys(insightsData) : 'N/A');
        console.log('   Key count:', insightsData ? Object.keys(insightsData).length : 0);
        console.log('   Has summary:', insightsData?.summary ? 'YES' : 'NO');
        console.log('   Has overall_score:', insightsData?.overall_score !== undefined ? 'YES' : 'NO');
        console.log('   Has sentiment:', insightsData?.sentiment ? 'YES' : 'NO');
        
        // EXACT SAME PATTERN AS TRANSCRIPT - Just set it!
        if (insightsData) {
          console.log('✅✅✅ [INSIGHTS] GOT DATA! Setting state now...');
          console.log('   Full response:', JSON.stringify(insightsData, null, 2));
          console.log('   Keys:', Object.keys(insightsData));
          console.log('   Overall score:', insightsData.overall_score);
          console.log('   Sentiment:', insightsData.sentiment);
          console.log('   Interest indicators:', insightsData.interest_indicators);
          console.log('   Concern indicators:', insightsData.concern_indicators);
          console.log('   BANT:', insightsData.bant_qualification);
          
          // SET STATE IMMEDIATELY - SAME AS TRANSCRIPT
          setInsights(insightsData);
          console.log('✅✅✅ [INSIGHTS] STATE SET! Check React DevTools!');
        } else {
          console.warn('❌ [INSIGHTS] Response is NULL - API returned null');
          console.warn('   This means either:');
          console.warn('   1. Insights are still processing (202 response)');
          console.warn('   2. API error (check Network tab)');
          console.warn('   3. Authentication issue');
        }
      } else {
        console.error('❌❌❌ INSIGHTS API REQUEST FAILED ❌❌❌');
        console.error('   Status: rejected');
        console.error('   Reason:', insightsResponse.reason);
        console.error('   Error message:', insightsResponse.reason?.message);
        console.error('   Error stack:', insightsResponse.reason?.stack);
        // Don't set insights to null if error - let it retry on auto-refresh
        // setInsights(null);
      }
        
      } catch (err) {
        console.error('Error fetching call data:', err);
        setError('Failed to load call data');
      }
  }, [id]);
    
  // PRIMARY INSIGHTS FETCHER: Fetch insights directly and set state immediately
  useEffect(() => {
    if (!id) return;
    
    const fetchInsightsDirectly = async () => {
      try {
        console.log('═══════════════════════════════════════════════════════════');
        console.log('🔍 [DIRECT FETCH] Starting insights fetch for call:', id);
        console.log('═══════════════════════════════════════════════════════════');
        
        const insightsData = await apiService.getInsightByCallId(id);
        
        console.log('═══════════════════════════════════════════════════════════');
        console.log('📥 [DIRECT FETCH] API Response Received:');
        console.log('   Type:', typeof insightsData);
        console.log('   Is null?', insightsData === null);
        console.log('   Is undefined?', insightsData === undefined);
        console.log('   Value:', insightsData);
        
        if (insightsData && typeof insightsData === 'object' && !Array.isArray(insightsData)) {
          console.log('✅ Valid insights data received! Setting state...');
          console.log('   Keys:', Object.keys(insightsData));
          console.log('   Overall score:', insightsData.overall_score);
          console.log('   Sentiment:', insightsData.sentiment);
          
          // SET STATE IMMEDIATELY
          setInsights(insightsData);
          console.log('✅ State set successfully!');
        } else if (insightsData === null) {
          console.log('⏳ Insights are still being generated (202 response)');
          // Don't set to null - keep existing state or leave as null
        } else {
          console.warn('⚠️ Invalid insights data format:', insightsData);
        }
      } catch (error) {
        console.error('❌ Error fetching insights:', error);
      }
    };
    
    // Fetch immediately
    fetchInsightsDirectly();
    
    // Also set up polling if needed
    const pollInterval = setInterval(() => {
      fetchInsightsDirectly();
    }, 5000); // Poll every 5 seconds
    
    return () => clearInterval(pollInterval);
  }, [id]);
  
  // OPTIMIZED: Initial load - fetch immediately in background, no spinner!
  useEffect(() => {
    if (id) {
      fetchCallData(false); // No loading spinner!
    }
  }, [id, fetchCallData]);

  // Auto-refresh when call is processing
  useEffect(() => {
    if (!id || !autoRefresh) return;

    // Refresh every 10 seconds if call is still processing
    const refreshInterval = setInterval(() => {
      // Check if insights actually exist and have data
      const hasInsights = insights !== null && insights !== undefined && typeof insights === 'object';
      
      // Only refresh if:
      // 1. Call is still processing
      // 2. Transcript is missing
      // 3. Insights are missing (but NOT if they're being loaded)
      if (callData && (callData.status === 'processing' || !transcript || (!hasInsights && callData.status === 'processed'))) {
        console.log('🔄 Auto-refreshing call data...', {
          status: callData.status,
          hasTranscript: !!transcript,
          hasInsights: hasInsights,
          insightsType: typeof insights,
          insightsValue: insights
        });
        fetchCallData(false);
      } else if (callData && callData.status === 'processed' && transcript && hasInsights) {
        // Call is fully processed, stop auto-refresh
        console.log('✅ Call fully processed with all data, stopping auto-refresh');
        setAutoRefresh(false);
      }
    }, 10000); // Refresh every 10 seconds

    return () => clearInterval(refreshInterval);
  }, [id, autoRefresh, callData, transcript, insights, fetchCallData]);

  // Cleanup blob URL when component unmounts or audio URL changes
  useEffect(() => {
    return () => {
      // Clean up blob URL on unmount
      if (audioUrl && audioUrl.startsWith('blob:')) {
        window.URL.revokeObjectURL(audioUrl);
      }
    };
  }, [audioUrl]);

  const getStatusColor = (status) => {
    switch (status) {
      case 'processed':
        return 'bg-emerald-100 text-emerald-800 border-emerald-200';
      case 'processing':
        return 'bg-amber-100 text-amber-800 border-amber-200';
      case 'failed':
        return 'bg-red-100 text-red-800 border-red-200';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getScoreColor = (score) => {
    if (score >= 90) return 'bg-emerald-100 text-emerald-800 border-emerald-200';
    if (score >= 70) return 'bg-amber-100 text-amber-800 border-amber-200';
    return 'bg-red-100 text-red-800 border-red-200';
  };

  const getSentimentColor = (sentiment) => {
    switch (sentiment) {
      case 'positive':
        return 'bg-emerald-100 text-emerald-800 border-emerald-200';
      case 'negative':
        return 'bg-red-100 text-red-800 border-red-200';
      case 'neutral':
        return 'bg-gray-100 text-gray-800 border-gray-200';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  // CRITICAL: Show error state if we have an error AND no data at all
  if (error && !callData) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-red-50 to-pink-100 flex items-center justify-center">
        <div className="text-center max-w-md mx-auto px-4">
          <div className="w-20 h-20 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-6">
            <svg className="w-10 h-10 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
        </div>
          <h2 className="text-2xl font-bold text-slate-900 mb-3">{t('callDetail.somethingWentWrong')}</h2>
          <p className="text-slate-600 mb-6">{error || t('callDetail.callNotFound')}</p>
          <Link
            to="/mycalls"
            className="inline-flex items-center px-6 py-3 border border-transparent text-base font-medium rounded-xl text-white bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 transition-all duration-200"
          >
            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7" />
            </svg>
            {t('callDetail.backToMyCalls')}
          </Link>
        </div>
      </div>
    );
  }

  // CRITICAL: Show skeleton loader if callData is null (data is still fetching)
  if (!callData && !error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100">
        <div className="container mx-auto px-4 py-8">
          <div className="max-w-7xl mx-auto space-y-6">
            {/* Header Skeleton */}
            <div className="bg-white rounded-xl shadow-lg p-6 animate-pulse">
              <div className="h-8 bg-gray-300 rounded w-48 mb-4"></div>
              <div className="h-4 bg-gray-300 rounded w-64"></div>
            </div>
            
            {/* Stats Cards Skeleton */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {[1, 2, 3].map((i) => (
                <SkeletonCallDetailCard key={i} />
              ))}
            </div>
            
            {/* Transcript Skeleton */}
            <SkeletonCallDetailCard />
            
            {/* Insights Skeleton */}
            <SkeletonCallDetailCard />
          </div>
        </div>
      </div>
    );
  }

  // Format the title from filename
  const formatTitle = (filename) => {
    if (!filename) return 'Call Details';
    // Remove file extension and format nicely
    return filename.replace(/\.[^/.]+$/, "").replace(/[-_]/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  };

  // Format duration from seconds
  const formatDuration = (seconds) => {
    if (!seconds) return 'N/A';
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
  };

  // Format date
  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString();
  };

  // Parse transcript into speaker segments for diarization
  const parseTranscriptForDiarization = (transcriptText) => {
    if (!transcriptText) return [];
    
    // Check if it's a fallback message
    if (transcriptText.includes('Transcription failed due to technical issues') || 
        transcriptText.includes('Transcription not available')) {
      return [{ speaker: 'System', text: transcriptText }];
    }
    
    // Check if it has **Speaker** format
    if (transcriptText.includes('**System**') || transcriptText.includes('**Sales Rep**') || 
        transcriptText.includes('**Customer**') || transcriptText.includes('**Client**')) {
      // Handle **Speaker** format
      const parts = transcriptText.split(/(\*\*(?:System|Sales Rep|Customer|Client)\*\*)/);
      const segments = [];
      let currentSpeaker = null;
      let currentText = '';
      
      parts.forEach((part) => {
        if (part.match(/\*\*(?:System|Sales Rep|Customer|Client)\*\*/)) {
          // Save previous segment if exists
          if (currentSpeaker && currentText.trim()) {
            segments.push({ speaker: currentSpeaker, text: currentText.trim() });
          }
          // Set new speaker
          currentSpeaker = part.replace(/\*\*/g, '').trim();
          currentText = '';
        } else if (part.trim() && currentSpeaker) {
          currentText += part;
        }
      });
      
      // Add final segment
      if (currentSpeaker && currentText.trim()) {
        segments.push({ speaker: currentSpeaker, text: currentText.trim() });
      }
      
      return segments;
    }
    
    // Handle continuous text format (like call ID 25)
    // Split by sentence patterns and identify speaker changes
    const sentences = transcriptText.split(/([.!?]+\s+)/).filter(s => s.trim());
    const segments = [];
    let currentSpeaker = 'Sales Rep'; // Start with sales rep
    let currentText = '';
    
    sentences.forEach((sentence, index) => {
      const trimmedSentence = sentence.trim();
      if (!trimmedSentence) return;
      
      // Detect speaker changes based on content patterns
      let speakerChange = null;
      
      // Customer responses (questions, agreements, concerns)
      if (trimmedSentence.match(/^(Yes|No|That's|Well|Honestly|I see|That sounds|What about|You know what|Sounds great|Thank you)/i) ||
          (trimmedSentence.includes('?') && !trimmedSentence.includes('Can you tell me')) ||
          trimmedSentence.match(/^\d+/)) { // Starts with numbers (like "About 25 people")
        speakerChange = 'Customer';
      }
      // Sales rep responses (questions, explanations, offers)
      else if (trimmedSentence.match(/^(Perfect|Great|That's|Our|We|Would you like|What kind|For a team|Excellent|I'll)/i) ||
               trimmedSentence.includes('platform') || 
               trimmedSentence.includes('training') ||
               trimmedSentence.includes('pricing') ||
               trimmedSentence.includes('trial') ||
               trimmedSentence.includes('onboarding')) {
        speakerChange = 'Sales Rep';
      }
      
      // Add sentence to current text
      currentText += sentence;
      
      // If speaker changed or this is the last sentence, create segment
      if (speakerChange && speakerChange !== currentSpeaker && currentText.trim()) {
        segments.push({ speaker: currentSpeaker, text: currentText.trim() });
        currentSpeaker = speakerChange;
        currentText = '';
      }
    });
    
    // Add final segment
    if (currentText.trim()) {
      segments.push({ speaker: currentSpeaker, text: currentText.trim() });
    }
    
    // If no segments were created, treat as single segment
    if (segments.length === 0) {
      return [{ speaker: 'Sales Rep', text: transcriptText }];
    }
    
    return segments;
  };

  // Parse insights for display
  const getInsightsList = () => {
    if (!insights) return [];
    
    const insightsList = [];
    
    // Add summary as first insight
    if (insights.summary) {
      insightsList.push(insights.summary);
    }
    
    // Add key topics
    if (insights.key_topics) {
      try {
        const topics = typeof insights.key_topics === 'string' ? JSON.parse(insights.key_topics) : insights.key_topics;
        if (Array.isArray(topics)) {
          topics.forEach(topic => insightsList.push(`Key topic: ${topic}`));
        }
      } catch (e) {
        console.error('Error parsing key topics:', e);
      }
    }
    
    // Add improvement areas
    if (insights.improvement_areas) {
      try {
        const areas = typeof insights.improvement_areas === 'string' ? JSON.parse(insights.improvement_areas) : insights.improvement_areas;
        if (Array.isArray(areas)) {
          areas.forEach(area => insightsList.push(`Improvement area: ${area}`));
        }
      } catch (e) {
        console.error('Error parsing improvement areas:', e);
      }
    }
    
    // Add action items
    if (insights.action_items) {
      try {
        const items = typeof insights.action_items === 'string' ? JSON.parse(insights.action_items) : insights.action_items;
        if (Array.isArray(items)) {
          items.forEach(item => insightsList.push(`Action item: ${item}`));
        }
      } catch (e) {
        console.error('Error parsing action items:', e);
      }
    }
    
    return insightsList;
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100">
      {/* Mobile Header */}
        <div className="lg:hidden bg-white/80 backdrop-blur-sm shadow-sm border-b border-gray-200">
        <div className="flex items-center justify-between px-4 py-3">
          <h1 className="text-lg font-semibold text-gray-900">{t('callDetail.title')}</h1>
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
                {/* Back Button and Auto-Refresh Controls */}
                <div className="mb-6 flex items-center justify-between">
                  <Link
                    to="/mycalls"
                    className="inline-flex items-center text-sm font-medium text-slate-600 hover:text-slate-800 transition-colors group"
                  >
                    <svg className="w-4 h-4 mr-2 group-hover:-translate-x-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7" />
                    </svg>
                    {t('callDetail.backToMyCalls')}
                  </Link>
                  
                  {/* Auto-Refresh Status */}
                  <div className="flex items-center space-x-3">
                    {autoRefresh && (
                      <div className="flex items-center space-x-2 text-sm text-slate-600">
                        <div className="relative">
                          <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                          <div className="absolute inset-0 w-2 h-2 bg-green-500 rounded-full animate-ping opacity-75"></div>
                </div>
                        <span className="hidden sm:inline">{t('callDetail.autoRefreshing')}</span>
                        {lastRefreshTime && (
                          <span className="hidden md:inline text-xs text-slate-500">
                            {t('callDetail.last')}: {new Date(lastRefreshTime).toLocaleTimeString()}
                          </span>
                        )}
                      </div>
                    )}
                    
                    {/* Manual Refresh Button */}
                    <button
                      onClick={() => {
                        console.log('🔄 Manual refresh triggered');
                        fetchCallData(false);
                      }}
                      className="inline-flex items-center px-3 py-1.5 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-colors"
                      title={t('callDetail.refreshNow')}
                    >
                      <svg 
                        className="w-4 h-4 mr-1.5" 
                        fill="none" 
                        stroke="currentColor" 
                        viewBox="0 0 24 24"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                      </svg>
                      {t('callDetail.refresh')}
                    </button>
                    
                    {/* Toggle Auto-Refresh */}
                    <button
                      onClick={() => setAutoRefresh(!autoRefresh)}
                      className={`inline-flex items-center px-3 py-1.5 text-sm font-medium rounded-lg border transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                        autoRefresh 
                          ? 'bg-indigo-50 text-indigo-700 border-indigo-200 hover:bg-indigo-100' 
                          : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-50'
                      }`}
                      title={autoRefresh ? t('callDetail.disableAutoRefresh') : t('callDetail.enableAutoRefresh')}
                    >
                      <svg 
                        className={`w-4 h-4 mr-1.5 ${autoRefresh ? 'animate-spin' : ''}`} 
                        fill="none" 
                        stroke="currentColor" 
                        viewBox="0 0 24 24"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                      </svg>
                      <span className="hidden sm:inline">{autoRefresh ? t('callDetail.autoOn') : t('callDetail.autoOff')}</span>
                    </button>
                  </div>
                </div>

                {/* Hero Header Section */}
                <div className="relative bg-gradient-to-r from-indigo-600 via-purple-600 to-blue-600 rounded-2xl shadow-2xl mb-8 overflow-hidden">
                  <div className="absolute inset-0 bg-black/10"></div>
                  <div className="absolute inset-0 bg-gradient-to-r from-indigo-600/90 via-purple-600/90 to-blue-600/90"></div>
                  <div className="relative px-8 py-10">
                    <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between">
                      <div className="flex-1 text-white">
                        <div className="flex items-center mb-4">
                          <div className="w-12 h-12 bg-white/20 rounded-xl flex items-center justify-center mr-4">
                            <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                            </svg>
                          </div>
                          <h1 className="text-3xl font-bold">{callData ? formatTitle(callData.filename) : t('callDetail.title')}</h1>
                        </div>
                        
                        <div className="flex flex-wrap items-center gap-3 mb-6">
                          {callData && (
                            <>
                              <span className={`inline-flex items-center px-4 py-2 text-sm font-semibold rounded-full border ${getStatusColor(callData.status)} bg-white/90`}>
                                <div className={`w-2 h-2 rounded-full mr-2 ${callData.status === 'processed' ? 'bg-emerald-500' : callData.status === 'processing' ? 'bg-amber-500' : 'bg-red-500'}`}></div>
                            {callData.status}
                          </span>
                          {callData.score && (
                                <span className={`inline-flex items-center px-4 py-2 text-sm font-semibold rounded-full border ${getScoreColor(callData.score)} bg-white/90`}>
                                  <svg className="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20">
                                    <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                                  </svg>
                            Score: {callData.score}
                          </span>
                              )}
                            </>
                          )}
                          {insights && insights.sentiment && (
                            <span className={`inline-flex items-center px-4 py-2 text-sm font-semibold rounded-full border ${getSentimentColor(insights.sentiment)} bg-white/90`}>
                              {insights.sentiment === 'positive' && <span className="mr-2">😊</span>}
                              {insights.sentiment === 'negative' && <span className="mr-2">😔</span>}
                              {insights.sentiment === 'neutral' && <span className="mr-2">😐</span>}
                              {insights.sentiment.charAt(0).toUpperCase() + insights.sentiment.slice(1)}
                          </span>
                          )}
                        </div>
                        
                        {callData && (
                          <div className="flex flex-wrap items-center gap-6 text-white/90">
                            <div className="flex items-center">
                              <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                              <span className="font-medium">{t('callDetail.duration')}: {formatDuration(callData.duration)}</span>
                            </div>
                            <div className="flex items-center">
                              <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                          </svg>
                              <span className="font-medium">{t('callDetail.uploadDate')}: {formatDate(callData.upload_date)}</span>
                        </div>
                          </div>
                        )}
                      </div>
                      
                      {/* Action Buttons */}
                      <div className="flex items-center space-x-3 mt-6 lg:mt-0">
                        <button
                          onClick={async () => {
                            if (!callData) return;
                            setIsLoadingPlay(true);
                            try {
                              const url = await apiService.getCallAudio(callData.id, false);
                              setAudioUrl(url);
                            } catch (error) {
                              console.error('Error loading audio:', error);
                              alert('Failed to load audio. Please try again.');
                            } finally {
                              setIsLoadingPlay(false);
                            }
                          }}
                          disabled={isLoadingPlay || !callData}
                          className="inline-flex items-center px-6 py-3 bg-white/20 backdrop-blur-sm border border-white/30 rounded-xl text-white font-medium hover:bg-white/30 focus:outline-none focus:ring-2 focus:ring-white/50 transition-all duration-200 transform hover:-translate-y-0.5 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
                        >
                          {isLoadingPlay ? (
                            <>
                              <svg className="w-5 h-5 mr-2 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                              </svg>
                              Loading...
                            </>
                          ) : (
                            <>
                              <svg className="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clipRule="evenodd" />
                              </svg>
                              {t('callDetail.play')}
                            </>
                          )}
                        </button>
                        <button
                          onClick={async () => {
                            if (!callData) return;
                            setIsLoadingDownload(true);
                            try {
                              const blobUrl = await apiService.getCallAudio(callData.id, true);
                              // Create a temporary anchor element to trigger download
                              const link = document.createElement('a');
                              link.href = blobUrl;
                              link.download = callData.filename || `call_${callData.id}_audio.mp3`;
                              document.body.appendChild(link);
                              link.click();
                              document.body.removeChild(link);
                              // Clean up the blob URL after a delay
                              setTimeout(() => {
                                window.URL.revokeObjectURL(blobUrl);
                              }, 100);
                            } catch (error) {
                              console.error('Error downloading audio:', error);
                              alert('Failed to download audio. Please try again.');
                            } finally {
                              setIsLoadingDownload(false);
                            }
                          }}
                          disabled={isLoadingDownload || !callData}
                          className="inline-flex items-center px-6 py-3 bg-white/20 backdrop-blur-sm border border-white/30 rounded-xl text-white font-medium hover:bg-white/30 focus:outline-none focus:ring-2 focus:ring-white/50 transition-all duration-200 transform hover:-translate-y-0.5 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
                        >
                          <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                          </svg>
                          {t('callDetail.download')}
                        </button>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Inline Audio Player - Shows below buttons when audio is loaded */}
                {audioUrl && (
                  <div className="mt-6 bg-white/80 backdrop-blur-sm shadow-xl rounded-2xl border border-white/20 overflow-hidden">
                    <div className="px-6 py-4 bg-gradient-to-r from-indigo-50 to-purple-50 border-b border-gray-200">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center">
                          <div className="w-10 h-10 bg-gradient-to-r from-indigo-500 to-purple-600 rounded-xl flex items-center justify-center mr-4">
                            <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clipRule="evenodd" />
                            </svg>
                          </div>
                          <div>
                            <h3 className="text-lg font-bold text-gray-900">Audio Player</h3>
                            <p className="text-sm text-gray-600">{callData?.filename || 'Call Audio'}</p>
                          </div>
                        </div>
                        <button
                          onClick={() => {
                            // Clean up blob URL if it's a blob URL (for downloads)
                            // Note: Pre-signed URLs don't need cleanup
                            if (audioUrl && audioUrl.startsWith('blob:')) {
                              window.URL.revokeObjectURL(audioUrl);
                            }
                            setAudioUrl(null);
                          }}
                          className="text-gray-400 hover:text-gray-600 focus:outline-none transition-colors p-2 rounded-lg hover:bg-gray-100"
                          title="Close player"
                        >
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      </div>
                    </div>
                    <div className="p-6">
                      <div className="bg-gradient-to-r from-gray-50 to-blue-50 rounded-xl p-6 border border-gray-200">
                        <audio
                          controls
                          autoPlay
                          className="w-full h-14"
                          src={audioUrl}
                          onError={(e) => {
                            console.error('Audio playback error:', e);
                            alert('Failed to play audio. Please try again.');
                            // Clean up blob URL if it's a blob URL (for downloads)
                            // Note: Pre-signed URLs don't need cleanup
                            if (audioUrl && audioUrl.startsWith('blob:')) {
                              window.URL.revokeObjectURL(audioUrl);
                            }
                            setAudioUrl(null);
                          }}
                        >
                          Your browser does not support the audio element.
                        </audio>
                        {callData?.duration && (
                          <p className="text-xs text-gray-500 mt-3 text-center">
                            Duration: {formatDuration(callData.duration)}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                )}

                <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
                  {/* Transcript Section - Takes 2 columns on XL screens */}
                  <div className="xl:col-span-2">
                    <div className="bg-white/80 backdrop-blur-sm shadow-xl rounded-2xl border border-white/20 overflow-hidden">
                      <div className="px-8 py-6 bg-gradient-to-r from-slate-50 to-blue-50 border-b border-gray-200">
                        <div className="flex items-center">
                          <div className="w-10 h-10 bg-gradient-to-r from-blue-500 to-indigo-600 rounded-xl flex items-center justify-center mr-4">
                            <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                            </svg>
                          </div>
                          <h2 className="text-xl font-bold text-gray-900">{t('callDetail.callTranscript')}</h2>
                        </div>
                    </div>
                    <div className="p-6">
                        <div className="bg-gradient-to-br from-gray-50 to-blue-50 rounded-xl p-6 max-h-[600px] overflow-y-auto border border-gray-200">
                        {transcript ? (
                            <div className="space-y-4">
                            {parseTranscriptForDiarization(transcript.text).map((segment, index) => {
                              const isRep = segment.speaker === 'Sales Rep' || segment.speaker === 'System';
                              const isCustomer = segment.speaker === 'Customer' || segment.speaker === 'Client';
                            
                            return (
                              <div
                                key={index}
                                  className={`flex items-start space-x-4 ${
                                    isRep 
                                      ? 'flex-row' 
                                      : isCustomer 
                                      ? 'flex-row-reverse space-x-reverse' 
                                      : 'flex-row'
                                  }`}
                                >
                                  <div className={`flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold shadow-lg ${
                                    isRep 
                                      ? 'bg-gradient-to-r from-blue-500 to-indigo-600 text-white' 
                                      : isCustomer 
                                      ? 'bg-gradient-to-r from-emerald-500 to-green-600 text-white' 
                                      : 'bg-gradient-to-r from-gray-500 to-slate-600 text-white'
                                  }`}>
                                    {isRep ? 'SR' : isCustomer ? 'C' : 'S'}
                                  </div>
                                  <div className={`flex-1 max-w-lg ${
                                  isRep 
                                    ? 'bg-white border-l-4 border-blue-500 shadow-md' 
                                    : isCustomer 
                                      ? 'bg-white border-r-4 border-emerald-500 shadow-md' 
                                      : 'bg-white border-l-4 border-gray-500 shadow-md'
                                  } p-4 rounded-xl`}>
                                    <div className="text-sm font-semibold text-gray-600 mb-2 flex items-center">
                                      {isRep && <span className="mr-2">👨‍💼</span>}
                                      {isCustomer && <span className="mr-2">👤</span>}
                                      {segment.speaker}
                                </div>
                                    <div className="text-gray-800 leading-relaxed">
                                      {segment.text}
                                    </div>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                        ) : (
                            <div className="text-center py-12">
                              <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
                                <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                </svg>
                              </div>
                              <p className="text-gray-500 text-lg">{t('callDetail.noTranscriptAvailable')}</p>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                    </div>

                  {/* Insights Section - Takes 1 column on XL screens */}
                  <div className="xl:col-span-1">
                    <div className="bg-white/80 backdrop-blur-sm shadow-xl rounded-2xl border border-white/20 overflow-hidden">
                      <div className="px-6 py-4 bg-gradient-to-r from-purple-50 to-pink-50 border-b border-gray-200">
                                  <div className="flex items-center">
                          <div className="w-8 h-8 bg-gradient-to-r from-purple-500 to-pink-600 rounded-lg flex items-center justify-center mr-3">
                            <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                                      </svg>
                                    </div>
                          <h2 className="text-lg font-bold text-gray-900">{t('callDetail.callAnalysis')}</h2>
                                      </div>
                                    </div>
                      <div className="p-6">
                        {/* DEBUG: Log insights state */}
                        {console.log('🔍 Insights state check:', {
                          insights,
                          type: typeof insights,
                          isNull: insights === null,
                          isUndefined: insights === undefined,
                          keys: insights ? Object.keys(insights) : 'N/A',
                          length: insights ? Object.keys(insights).length : 0,
                          hasSummary: insights?.summary ? 'YES' : 'NO',
                          hasTalkTime: insights?.talk_time_ratio !== null && insights?.talk_time_ratio !== undefined ? 'YES' : 'NO',
                          overallScore: insights?.overall_score
                        })}
                        {/* COMPLETELY DIFFERENT APPROACH: ALWAYS RENDER STRUCTURE, CHECK DATA INSIDE */}
                        <div className="space-y-6">
                          {/* DEBUG INFO */}
                          {(() => {
                            console.log('🎨 RENDERING INSIGHTS SECTION - Always render approach');
                            console.log('   insights state:', insights);
                            console.log('   Type:', typeof insights);
                            console.log('   Is null:', insights === null);
                            console.log('   Keys:', insights ? Object.keys(insights) : 'none');
                            return null;
                          })()}
                          
                          {/* SUCCESS INDICATOR - Show when we have data */}
                          {insights && insights !== null && insights !== undefined ? (
                            <div className="mb-4 p-3 bg-green-100 border-2 border-green-500 rounded-lg">
                              <div className="flex items-center">
                                <span className="text-2xl mr-2">✅</span>
                                <div>
                                  <strong className="text-green-900">Insights Loaded Successfully!</strong>
                                  <p className="text-sm text-green-700">
                                    {Object.keys(insights || {}).length} fields loaded • 
                                    Score: {insights?.overall_score || 'N/A'} • 
                                    Sentiment: {insights?.sentiment || 'N/A'}
                                  </p>
                                </div>
                              </div>
                            </div>
                          ) : (
                            <div className="mb-4 p-3 bg-amber-100 border-2 border-amber-500 rounded-lg">
                              <div className="flex items-center">
                                <span className="text-2xl mr-2">⏳</span>
                                <div>
                                  <strong className="text-amber-900">Waiting for insights...</strong>
                                  <p className="text-sm text-amber-700">Insights state: {insights === null ? 'null' : insights === undefined ? 'undefined' : typeof insights}</p>
                                </div>
                              </div>
                            </div>
                          )}
                            
                            {/* Summary Section - Show data if available */}
                            {insights?.summary ? (
                              <div className="bg-gradient-to-r from-indigo-50 to-blue-50 rounded-xl p-4 border border-indigo-200">
                                <h3 className="text-sm font-bold text-indigo-900 mb-2 flex items-center">
                                  <span className="mr-2">📋</span>
                                  Call Summary
                                </h3>
                                <p className="text-sm text-indigo-700 leading-relaxed">{insights.summary}</p>
                              </div>
                            ) : null}
                            
                            {/* Overall Score - Show data if available */}
                            {insights?.overall_score !== null && insights?.overall_score !== undefined ? (
                              <div className="bg-gradient-to-r from-green-50 to-emerald-50 rounded-xl p-4 border border-green-200">
                                <div className="flex items-center justify-between">
                                  <div className="flex items-center">
                                    <div className="w-8 h-8 bg-green-500 rounded-lg flex items-center justify-center mr-3">
                                      <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                      </svg>
                                    </div>
                                    <div>
                                      <p className="text-sm font-semibold text-green-900">Overall Score</p>
                                    </div>
                                  </div>
                                  <div className="text-2xl font-bold text-green-600">
                                    {insights.overall_score}/100
                                  </div>
                                </div>
                              </div>
                            ) : null}
                            
                            {/* Sentiment - Show data if available */}
                            {insights?.sentiment ? (
                              <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl p-4 border border-blue-200">
                                <div className="flex items-center justify-between">
                                  <div className="flex items-center">
                                    <div className="w-8 h-8 bg-blue-500 rounded-lg flex items-center justify-center mr-3">
                                      <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14.828 14.828a4 4 0 01-5.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                      </svg>
                                    </div>
                                    <div>
                                      <p className="text-sm font-semibold text-blue-900">Sentiment</p>
                                    </div>
                                  </div>
                                  <div className={`text-lg font-bold ${
                                    insights.sentiment === 'positive' ? 'text-green-600' :
                                    insights.sentiment === 'negative' ? 'text-red-600' : 'text-gray-600'
                                  }`}>
                                    {insights.sentiment.charAt(0).toUpperCase() + insights.sentiment.slice(1)}
                                  </div>
                                </div>
                              </div>
                            ) : null}
                            {/* Performance Metrics - ALWAYS SHOW SECTION */}
                            <div className="space-y-4">
                              <h3 className="text-sm font-bold text-gray-900 mb-3 flex items-center">
                                <span className="mr-2">📊</span>
                                Performance Metrics
                              </h3>
                              
                              {/* Talk Time Ratio */}
                              {insights && insights.talk_time_ratio !== null && insights.talk_time_ratio !== undefined ? (
                                <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl p-4 border border-blue-200">
                                  <div className="flex items-center justify-between mb-2">
                                    <div className="flex items-center">
                                      <div className="w-8 h-8 bg-blue-500 rounded-lg flex items-center justify-center mr-3">
                                        <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                                        </svg>
                                      </div>
                                      <div>
                                        <p className="text-sm font-semibold text-blue-900">Talk Time Ratio</p>
                                        <p className="text-xs text-blue-600">
                                          {insights.talk_time_ratio > 0.6 ? 'Sales Rep Dominated' : 
                                           insights.talk_time_ratio < 0.4 ? 'Customer Dominated' : 'Balanced'}
                                        </p>
                                      </div>
                                    </div>
                                    <div className="text-xl font-bold text-blue-600">
                                      {Math.round(insights.talk_time_ratio * 100)}%
                                    </div>
                                  </div>
                                  <div className="w-full bg-blue-200 rounded-full h-2">
                                    <div 
                                      className="bg-blue-600 h-2 rounded-full transition-all duration-500" 
                                      style={{width: `${insights.talk_time_ratio * 100}%`}}
                                    ></div>
                                  </div>
                                </div>
                              ) : null}

                              {/* Question Effectiveness */}
                              {insights && insights.question_effectiveness !== null && insights.question_effectiveness !== undefined ? (
                                <div className="bg-gradient-to-r from-emerald-50 to-green-50 rounded-xl p-4 border border-emerald-200">
                                  <div className="flex items-center justify-between mb-2">
                                    <div className="flex items-center">
                                      <div className="w-8 h-8 bg-emerald-500 rounded-lg flex items-center justify-center mr-3">
                                        <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                        </svg>
                                      </div>
                                      <div>
                                        <p className="text-sm font-semibold text-emerald-900">Question Quality</p>
                                        <p className="text-xs text-emerald-600">
                                          {insights.question_effectiveness >= 80 ? 'Excellent' :
                                           insights.question_effectiveness >= 60 ? 'Good' : 'Needs Improvement'}
                                        </p>
                                      </div>
                                    </div>
                                    <div className="text-xl font-bold text-emerald-600">
                                      {insights.question_effectiveness}/100
                                    </div>
                                  </div>
                                  <div className="w-full bg-emerald-200 rounded-full h-2">
                                    <div 
                                      className="bg-emerald-600 h-2 rounded-full transition-all duration-500" 
                                      style={{width: `${insights.question_effectiveness}%`}}
                                    ></div>
                                  </div>
                                </div>
                              ) : null}

                              {/* Engagement Score */}
                              {insights && insights.engagement_score !== null && insights.engagement_score !== undefined ? (
                                <div className="bg-gradient-to-r from-purple-50 to-violet-50 rounded-xl p-4 border border-purple-200">
                                  <div className="flex items-center justify-between mb-2">
                                    <div className="flex items-center">
                                      <div className="w-8 h-8 bg-purple-500 rounded-lg flex items-center justify-center mr-3">
                                        <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
                                        </svg>
                                      </div>
                                      <div>
                                        <p className="text-sm font-semibold text-purple-900">Engagement</p>
                                        <p className="text-xs text-purple-600">
                                          {insights.engagement_score >= 80 ? 'Highly Engaged' :
                                           insights.engagement_score >= 60 ? 'Moderately Engaged' : 'Low Engagement'}
                                        </p>
                                      </div>
                                    </div>
                                    <div className="text-xl font-bold text-purple-600">
                                      {insights.engagement_score}/100
                                    </div>
                                  </div>
                                  <div className="w-full bg-purple-200 rounded-full h-2">
                                    <div 
                                      className="bg-purple-600 h-2 rounded-full transition-all duration-500" 
                                      style={{width: `${insights.engagement_score}%`}}
                                    ></div>
                                  </div>
                                </div>
                              ) : null}

                              {/* Deal Probability */}
                              {insights && insights.deal_probability !== null && insights.deal_probability !== undefined ? (
                                <div className="bg-gradient-to-r from-orange-50 to-amber-50 rounded-xl p-4 border border-orange-200">
                                  <div className="flex items-center justify-between mb-2">
                                    <div className="flex items-center">
                                      <div className="w-8 h-8 bg-orange-500 rounded-lg flex items-center justify-center mr-3">
                                        <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                                        </svg>
                                      </div>
                                      <div>
                                        <p className="text-sm font-semibold text-orange-900">Deal Probability</p>
                                        <p className="text-xs text-orange-600">
                                          {insights.deal_probability >= 80 ? 'High Probability' :
                                           insights.deal_probability >= 60 ? 'Medium Probability' : 'Low Probability'}
                                        </p>
                                      </div>
                                    </div>
                                    <div className="text-xl font-bold text-orange-600">
                                      {insights.deal_probability}%
                                    </div>
                                  </div>
                                  <div className="w-full bg-orange-200 rounded-full h-2">
                                    <div 
                                      className="bg-orange-600 h-2 rounded-full transition-all duration-500" 
                                      style={{width: `${insights.deal_probability}%`}}
                                    ></div>
                                  </div>
                                </div>
                              ) : null}
                            </div>

                          {/* BANT Qualification - ALWAYS SHOW */}
                          <div className="bg-gradient-to-r from-slate-50 to-gray-50 rounded-xl p-4 border border-slate-200">
                            <h3 className="text-sm font-bold text-gray-900 mb-3 flex items-center">
                              <span className="mr-2">🎯</span>
                              BANT Qualification
                            </h3>
                            {insights && insights.bant_qualification ? (
                              <div className="grid grid-cols-2 gap-3">
                                {(() => {
                                  try {
                                    const bant = typeof insights.bant_qualification === 'string' 
                                      ? JSON.parse(insights.bant_qualification) 
                                      : insights.bant_qualification;
                                    if (bant && typeof bant === 'object' && Object.keys(bant).length > 0) {
                                      return Object.entries(bant).map(([key, score]) => (
                                        <div key={key} className="text-center bg-white rounded-lg p-3 border border-gray-200">
                                          <div className="text-sm font-bold text-gray-700 capitalize">{key}</div>
                                          <div className={`text-lg font-bold ${
                                            score >= 80 ? 'text-emerald-600' :
                                            score >= 60 ? 'text-amber-600' : 'text-red-600'
                                          }`}>
                                            {score}/100
                                          </div>
                                        </div>
                                      ));
                                    }
                                    return <p className="text-sm text-gray-500 col-span-2 text-center">BANT data is being processed...</p>;
                                  } catch (e) {
                                    console.error('Error parsing BANT:', e);
                                    return <p className="text-sm text-gray-500 col-span-2 text-center">BANT data is being processed...</p>;
                                  }
                                })()}
                              </div>
                            ) : (
                              <p className="text-sm text-gray-500 text-center py-4">BANT data is being processed...</p>
                            )}
                          </div>

                          {/* Interest & Concern Indicators - ALWAYS SHOW */}
                          <div className="space-y-4">
                            {/* Interest Indicators */}
                            <div className="bg-gradient-to-r from-emerald-50 to-green-50 rounded-xl p-4 border border-emerald-200">
                              <h3 className="text-sm font-bold text-emerald-900 mb-3 flex items-center">
                                <span className="mr-2">✅</span>
                                Interest Indicators
                              </h3>
                              {(() => {
                                if (!insights || !insights.interest_indicators) {
                                  return <p className="text-sm text-gray-500 italic">No interest indicators available</p>;
                                }
                                
                                try {
                                  const indicators = typeof insights.interest_indicators === 'string' 
                                    ? JSON.parse(insights.interest_indicators) 
                                    : insights.interest_indicators;
                                  
                                  console.log('🔍 Interest indicators parsed:', indicators);
                                  console.log('🔍 Is array?', Array.isArray(indicators));
                                  console.log('🔍 Length:', Array.isArray(indicators) ? indicators.length : 'N/A');
                                  
                                  if (Array.isArray(indicators) && indicators.length > 0) {
                                    return (
                                      <ul className="space-y-2">
                                        {indicators.map((indicator, index) => (
                                          <li key={index} className="text-sm text-emerald-700 flex items-start">
                                            <span className="mr-2 text-emerald-500">•</span>
                                            {indicator}
                                          </li>
                                        ))}
                                      </ul>
                                    );
                                  }
                                } catch (e) {
                                  console.error('❌ Error parsing interest indicators:', e);
                                  console.error('   Raw value:', insights.interest_indicators);
                                  console.error('   Type:', typeof insights.interest_indicators);
                                }
                                
                                return <p className="text-sm text-gray-500 italic">No interest indicators available</p>;
                              })()}
                            </div>

                            {/* Concern Indicators */}
                            <div className="bg-gradient-to-r from-red-50 to-pink-50 rounded-xl p-4 border border-red-200">
                              <h3 className="text-sm font-bold text-red-900 mb-3 flex items-center">
                                <span className="mr-2">⚠️</span>
                                Concern Indicators
                              </h3>
                              {(() => {
                                if (!insights || !insights.concern_indicators) {
                                  return <p className="text-sm text-gray-500 italic">No concern indicators available</p>;
                                }
                                
                                try {
                                  const concerns = typeof insights.concern_indicators === 'string' 
                                    ? JSON.parse(insights.concern_indicators) 
                                    : insights.concern_indicators;
                                  
                                  console.log('🔍 Concern indicators parsed:', concerns);
                                  console.log('🔍 Is array?', Array.isArray(concerns));
                                  console.log('🔍 Length:', Array.isArray(concerns) ? concerns.length : 'N/A');
                                  
                                  if (Array.isArray(concerns) && concerns.length > 0) {
                                    return (
                                      <ul className="space-y-2">
                                        {concerns.map((concern, index) => (
                                          <li key={index} className="text-sm text-red-700 flex items-start">
                                            <span className="mr-2 text-red-500">•</span>
                                            {concern}
                                          </li>
                                        ))}
                                      </ul>
                                    );
                                  }
                                } catch (e) {
                                  console.error('❌ Error parsing concern indicators:', e);
                                  console.error('   Raw value:', insights.concern_indicators);
                                  console.error('   Type:', typeof insights.concern_indicators);
                                }
                                
                                return <p className="text-sm text-gray-500 italic">No concern indicators available</p>;
                              })()}
                            </div>
                          </div>

                          {/* Additional Insights - ALWAYS SHOW */}
                          <div className="border-t pt-4">
                            <h3 className="text-sm font-bold text-gray-900 mb-3 flex items-center">
                              <span className="mr-2">📋</span>
                              Additional Insights
                            </h3>
                            <div className="space-y-2">
                              {insights && getInsightsList().length > 0 ? (
                                getInsightsList().map((insight, index) => (
                                  <div key={index} className="flex items-start">
                                    <div className="flex-shrink-0">
                                      <div className="w-2 h-2 bg-gradient-to-r from-indigo-500 to-purple-600 rounded-full mt-2"></div>
                                    </div>
                                    <div className="ml-3">
                                      <p className="text-sm text-gray-700">{insight}</p>
                                    </div>
                                  </div>
                                ))
                              ) : (
                                <p className="text-sm text-gray-500 italic">No additional insights available</p>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Score Visualization */}
                {callData.score && (
                  <div className="mt-8 bg-white/80 backdrop-blur-sm shadow-xl rounded-2xl border border-white/20 overflow-hidden">
                    <div className="px-8 py-6 bg-gradient-to-r from-indigo-50 to-purple-50 border-b border-gray-200">
                      <div className="flex items-center">
                        <div className="w-10 h-10 bg-gradient-to-r from-indigo-500 to-purple-600 rounded-xl flex items-center justify-center mr-4">
                          <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                          </svg>
                  </div>
                        <h2 className="text-xl font-bold text-gray-900">Call Quality Score</h2>
                      </div>
                    </div>
                    <div className="p-8">
                      <div className="flex flex-col items-center">
                        <div className="relative w-40 h-40 mb-6">
                          <svg className="w-40 h-40 transform -rotate-90" viewBox="0 0 100 100">
                          <circle
                            cx="50"
                            cy="50"
                              r="45"
                            stroke="currentColor"
                              strokeWidth="6"
                            fill="none"
                            className="text-gray-200"
                          />
                          <circle
                            cx="50"
                            cy="50"
                              r="45"
                            stroke="currentColor"
                              strokeWidth="6"
                            fill="none"
                              strokeDasharray={`${2 * Math.PI * 45}`}
                              strokeDashoffset={`${2 * Math.PI * 45 * (1 - (callData.score || 0) / 100)}`}
                              className={(callData.score || 0) >= 90 ? 'text-emerald-500' : (callData.score || 0) >= 70 ? 'text-amber-500' : 'text-red-500'}
                            strokeLinecap="round"
                              style={{transition: 'all 0.5s ease-in-out'}}
                          />
                        </svg>
                        <div className="absolute inset-0 flex items-center justify-center">
                            <div className="text-center">
                              <span className="text-4xl font-bold text-gray-900">{callData.score || 'N/A'}</span>
                              <div className="text-sm text-gray-500">/ 100</div>
                        </div>
                      </div>
                    </div>
                        <div className="text-center">
                          <p className="text-lg font-medium text-gray-900 mb-2">
                        {(callData.score || 0) >= 90 
                              ? '🎉 Excellent call performance!' 
                          : (callData.score || 0) >= 70 
                              ? '👍 Good call with room for improvement' 
                              : '📈 Call needs attention and improvement'
                            }
                          </p>
                          <p className="text-sm text-gray-600 max-w-md">
                            {(callData.score || 0) >= 90 
                              ? 'Outstanding communication skills and customer engagement demonstrated throughout the call.'
                              : (callData.score || 0) >= 70 
                              ? 'Solid performance with opportunities to enhance customer interaction and closing techniques.'
                              : 'Focus on improving communication flow, customer engagement, and sales techniques for better results.'
                        }
                      </p>
                    </div>
                  </div>
                </div>
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

export default CallDetail;