import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import apiService from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { SkeletonCard, SkeletonTableRow } from './SkeletonLoader';
import Sidebar from './Sidebar';
import UserHeader from './UserHeader';

const S3MonitoringDashboard = () => {
  const { user } = useAuth();
  const [activeItem, setActiveItem] = useState('S3 Monitoring');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [monitoringStatus, setMonitoringStatus] = useState(null);
  const [monitoredClients, setMonitoredClients] = useState([]);
  // OPTIMIZED: Start with loading = false so UI shows immediately!
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

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

  useEffect(() => {
    fetchMonitoringData(false); // OPTIMIZED: No loading spinner!
    // Refresh data every 30 seconds (silent, no loading spinner)
    const interval = setInterval(() => {
      fetchMonitoringData(false);
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  const fetchMonitoringData = async (showLoading = false) => {
    try {
      if (showLoading) {
        setLoading(true);
      }
      const [status, clients] = await Promise.all([
        apiService.getS3MonitoringStatus(),
        apiService.getMonitoredClients()
      ]);
      
      setMonitoringStatus(status);
      setMonitoredClients(clients.clients || []);
    } catch (error) {
      if (showLoading) {
        setError('Failed to fetch monitoring data');
      }
      console.error('Error fetching monitoring data:', error);
    } finally {
      if (showLoading) {
        setLoading(false);
      }
    }
  };

  const handleStartMonitoring = async () => {
    try {
      await apiService.startS3Monitoring();
      fetchMonitoringData(false); // Silent refresh after action
    } catch (error) {
      setError('Failed to start monitoring');
      console.error('Error starting monitoring:', error);
    }
  };

  const handleStopMonitoring = async () => {
    try {
      await apiService.stopS3Monitoring();
      fetchMonitoringData(false); // Silent refresh after action
    } catch (error) {
      setError('Failed to stop monitoring');
      console.error('Error stopping monitoring:', error);
    }
  };

  const handleManualScan = async (clientId) => {
    try {
      await apiService.manualScanClient(clientId);
      alert('Manual scan initiated successfully!');
    } catch (error) {
      alert(`Manual scan failed: ${error.message}`);
    }
  };

  const handleTestConnection = async (clientId) => {
    try {
      const result = await apiService.testClientConnection(clientId);
      alert(`Connection test successful!\nBucket: ${result.bucket_name}\nObjects: ${result.object_count}`);
    } catch (error) {
      alert(`Connection test failed: ${error.message}`);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'active': return 'bg-green-500';
      case 'inactive': return 'bg-gray-400';
      case 'error': return 'bg-red-500';
      default: return 'bg-gray-400';
    }
  };

  const getScheduleIcon = (schedule) => {
    switch (schedule) {
      case 'hourly': return '🕐';
      case 'daily': return '📅';
      case 'twice_daily': return '🔄';
      case 'every_6_hours': return '⏰';
      case 'every_2_hours': return '⏱️';
      default: return '📅';
    }
  };

  // Skeleton loader for initial load
  if (loading && monitoredClients.length === 0 && !monitoringStatus) {
    return (
      <div className="min-h-screen bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header Skeleton */}
        <div className="mb-8">
          <div className="h-8 bg-gray-300 rounded w-64 mb-4 animate-pulse"></div>
          <div className="h-4 bg-gray-300 rounded w-96 animate-pulse"></div>
        </div>
        
        {/* Status Card Skeleton */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          {[1, 2, 3].map((i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
        
        {/* Clients Table Skeleton */}
        <div className="bg-white shadow rounded-xl overflow-hidden">
          <div className="px-4 py-5 sm:p-6">
            <div className="h-6 bg-gray-300 rounded w-48 mb-6 animate-pulse"></div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    {['Client', 'Bucket', 'Schedule', 'Status', 'Last Scan', 'Actions'].map((header) => (
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
      </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Mobile Header */}
      <div className="lg:hidden bg-white shadow-sm border-b border-gray-200">
        <div className="flex items-center justify-between px-4 py-3">
          <h1 className="text-lg font-semibold text-gray-900">S3 Monitoring</h1>
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
                {/* Header */}
                <div className="bg-white rounded-2xl shadow-xl p-8 mb-8">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-4xl font-bold text-gray-900 mb-2">S3 Monitoring Dashboard</h1>
              <p className="text-gray-600">Monitor and manage S3 bucket processing</p>
            </div>
            <div className="flex space-x-4">
              {monitoringStatus?.is_running ? (
                <button
                  onClick={handleStopMonitoring}
                  className="bg-gradient-to-r from-red-600 to-red-700 text-white px-6 py-3 rounded-xl font-semibold hover:from-red-700 hover:to-red-800 transition-all duration-200 shadow-lg hover:shadow-xl"
                >
                  Stop Monitoring
                </button>
              ) : (
                <button
                  onClick={handleStartMonitoring}
                  className="bg-gradient-to-r from-green-600 to-green-700 text-white px-6 py-3 rounded-xl font-semibold hover:from-green-700 hover:to-green-800 transition-all duration-200 shadow-lg hover:shadow-xl"
                >
                  Start Monitoring
                </button>
              )}
            </div>
          </div>

          {/* Monitoring Status */}
          {monitoringStatus && (
            <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl p-6 border border-blue-200">
                <div className="flex items-center space-x-3">
                  <div className={`w-4 h-4 rounded-full ${monitoringStatus.is_running ? 'bg-green-500' : 'bg-red-500'}`}></div>
                  <div>
                    <h3 className="text-lg font-semibold text-gray-800">Service Status</h3>
                    <p className="text-sm text-gray-600">
                      {monitoringStatus.is_running ? 'Active' : 'Inactive'}
                    </p>
                  </div>
                </div>
              </div>

              <div className="bg-gradient-to-r from-purple-50 to-pink-50 rounded-xl p-6 border border-purple-200">
                <div className="flex items-center space-x-3">
                  <div className="text-2xl">👥</div>
                  <div>
                    <h3 className="text-lg font-semibold text-gray-800">Monitored Clients</h3>
                    <p className="text-sm text-gray-600">
                      {monitoringStatus.monitored_clients.length} clients
                    </p>
                  </div>
                </div>
              </div>

              <div className="bg-gradient-to-r from-green-50 to-emerald-50 rounded-xl p-6 border border-green-200">
                <div className="flex items-center space-x-3">
                  <div className="text-2xl">📋</div>
                  <div>
                    <h3 className="text-lg font-semibold text-gray-800">Processing Queue</h3>
                    <p className="text-sm text-gray-600">
                      {monitoringStatus.queue_size} files pending
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Error Message */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl mb-6">
            {error}
          </div>
        )}

        {/* Clients Overview */}
        <div className="bg-white rounded-2xl shadow-xl p-8 mb-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-6">Client Overview</h2>
          
          {monitoredClients.length === 0 ? (
            <div className="text-center py-12">
              <div className="text-6xl mb-4">📁</div>
              <h3 className="text-xl font-semibold text-gray-600 mb-2">No Clients Configured</h3>
              <p className="text-gray-500">Add clients to start monitoring their S3 buckets</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
              {monitoredClients.map((client) => (
                <div key={client.id} className="bg-gradient-to-br from-gray-50 to-blue-50 rounded-xl p-6 border border-gray-200 hover:shadow-lg transition-all duration-300">
                  <div className="flex justify-between items-start mb-4">
                    <div>
                      <h3 className="text-lg font-bold text-gray-900">{client.name}</h3>
                      <p className="text-sm text-gray-600">Bucket: {client.s3_bucket_name}</p>
                      <p className="text-sm text-gray-600">Region: {client.s3_region}</p>
                    </div>
                    <div className={`w-3 h-3 rounded-full ${getStatusColor(client.status)}`}></div>
                  </div>

                  {/* Client Status */}
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center space-x-2">
                      <span className="text-lg">{getScheduleIcon(client.processing_schedule)}</span>
                      <span className="text-sm font-medium text-gray-700 capitalize">
                        {client.processing_schedule.replace('_', ' ')}
                      </span>
                    </div>
                    <div className="text-sm text-gray-600">
                      {client.call_count} calls
                    </div>
                  </div>

                  {/* Monitoring Status */}
                  <div className="flex items-center justify-between mb-4 p-3 bg-white rounded-lg border border-gray-200">
                    <span className="text-sm font-medium text-gray-700">Monitoring</span>
                    <div className="flex items-center space-x-2">
                      <div className={`w-2 h-2 rounded-full ${client.is_monitored ? 'bg-green-500' : 'bg-gray-400'}`}></div>
                      <span className="text-sm text-gray-600">
                        {client.is_monitored ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                  </div>

                  {/* Action Buttons */}
                  <div className="flex space-x-2">
                    <button
                      onClick={() => handleTestConnection(client.id)}
                      className="flex-1 bg-blue-100 text-blue-700 px-3 py-2 rounded-lg text-sm font-medium hover:bg-blue-200 transition-colors"
                    >
                      Test Connection
                    </button>
                    <button
                      onClick={() => handleManualScan(client.id)}
                      className="flex-1 bg-yellow-100 text-yellow-700 px-3 py-2 rounded-lg text-sm font-medium hover:bg-yellow-200 transition-colors"
                    >
                      Manual Scan
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent Activity */}
        <div className="bg-white rounded-2xl shadow-xl p-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-6">Recent Activity</h2>
          
          <div className="space-y-4">
            <div className="text-center py-8">
              <div className="text-4xl mb-4">📊</div>
              <h3 className="text-lg font-semibold text-gray-600 mb-2">Activity Monitoring</h3>
              <p className="text-gray-500">Real-time activity logs will appear here once monitoring is active</p>
            </div>
          </div>
        </div>

        {/* System Information */}
        <div className="mt-8 bg-white rounded-2xl shadow-xl p-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-6">System Information</h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <div className="text-center">
              <div className="text-3xl mb-2">🔧</div>
              <h3 className="font-semibold text-gray-800">Processing Engine</h3>
              <p className="text-sm text-gray-600">AI-Powered</p>
            </div>
            
            <div className="text-center">
              <div className="text-3xl mb-2">☁️</div>
              <h3 className="font-semibold text-gray-800">Cloud Storage</h3>
              <p className="text-sm text-gray-600">AWS S3</p>
            </div>
            
            <div className="text-center">
              <div className="text-3xl mb-2">🔄</div>
              <h3 className="font-semibold text-gray-800">Auto Processing</h3>
              <p className="text-sm text-gray-600">Real-time</p>
            </div>
            
            <div className="text-center">
              <div className="text-3xl mb-2">📈</div>
              <h3 className="font-semibold text-gray-800">Analytics</h3>
              <p className="text-sm text-gray-600">Advanced</p>
            </div>
          </div>
        </div>
              </div>
            </div>
          </main>
        </div>
      </div>
    </div>
  );
};

export default S3MonitoringDashboard;
