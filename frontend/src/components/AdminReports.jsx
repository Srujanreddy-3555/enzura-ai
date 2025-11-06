import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import apiService from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import Sidebar from './Sidebar';
import UserHeader from './UserHeader';

const AdminReports = () => {
  const { user } = useAuth();
  const [activeItem, setActiveItem] = useState('Reports');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [clients, setClients] = useState([]);
  const [selectedClientId, setSelectedClientId] = useState('');
  const [rows, setRows] = useState([]);
  // OPTIMIZED: No loading spinner - show UI immediately!
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
    const fetchClients = async () => {
      try {
        const data = await apiService.getClients();
        setClients(data || []);
        if (data && data.length > 0) {
          setSelectedClientId(String(data[0].id));
        }
      } catch (e) {
        setError('Failed to load clients');
      }
    };
    fetchClients();
  }, []);

  const loadReport = useCallback(async (showLoading = false) => {
    if (!selectedClientId) return;
    setError('');
    if (showLoading) {
      setLoading(true);
    }
    try {
      const res = await apiService.getRepPerformance(Number(selectedClientId));
      setRows(res?.results || []);
    } catch (e) {
      if (showLoading) {
        setError(e.message || 'Failed to load report');
      }
      // Don't show error on auto-refresh to avoid interrupting user
    } finally {
      if (showLoading) {
        setLoading(false);
      }
    }
  }, [selectedClientId]);

  useEffect(() => {
    // OPTIMIZED: Load immediately in background - no spinner!
    loadReport(false);

    // Set up auto-refresh every 5 seconds when a client is selected (silent, no loading spinner)
    if (selectedClientId) {
      const refreshInterval = setInterval(() => {
        loadReport(false);
      }, 5000);

      // Cleanup interval on unmount or when client changes
      return () => clearInterval(refreshInterval);
    }
  }, [selectedClientId, loadReport]);

  if (user?.role?.toLowerCase() !== 'admin') {
    return (
      <div className="min-h-screen flex items-center justify-center">Access denied</div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Mobile Header */}
      <div className="lg:hidden bg-white shadow-sm border-b border-gray-200">
        <div className="flex items-center justify-between px-4 py-3">
          <h1 className="text-lg font-semibold text-gray-900">Reports</h1>
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
              <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="mb-6">
                  <h1 className="text-2xl font-bold text-gray-900">Admin Reports</h1>
                </div>

                <div className="bg-white rounded-xl shadow p-4 mb-6">
                  <div className="flex items-center gap-4">
                    <label className="text-sm text-gray-700">Client</label>
                    <select
                      value={selectedClientId}
                      onChange={e => setSelectedClientId(e.target.value)}
                      className="border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    >
                      {clients.map(c => (
                        <option key={c.id} value={c.id}>{c.name}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="bg-white rounded-xl shadow p-4">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-semibold text-gray-800">Per-Rep Performance</h2>
                    <button
                      onClick={loadReport}
                      disabled={loading}
                      className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-indigo-700 disabled:opacity-50"
                    >
                      {loading ? 'Loading...' : 'Refresh'}
                    </button>
                  </div>

                  {error && (
                    <div className="bg-red-50 text-red-700 px-3 py-2 rounded-lg mb-3 text-sm">{error}</div>
                  )}

                  <div className="overflow-x-auto">
                    <table className="min-w-full text-sm">
                      <thead>
                        <tr className="text-left text-gray-600 border-b">
                          <th className="py-2 pr-4">Rep</th>
                          <th className="py-2 pr-4">Email</th>
                          <th className="py-2 pr-4">Total Calls</th>
                          <th className="py-2 pr-4">Avg Overall Score</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rows.length === 0 ? (
                          <tr><td colSpan={4} className="py-6 text-center text-gray-500">No data</td></tr>
                        ) : rows.map(r => (
                          <tr key={r.user_id} className="border-b last:border-0">
                            <td className="py-2 pr-4">{r.rep_name || '-'}</td>
                            <td className="py-2 pr-4">{r.rep_email}</td>
                            <td className="py-2 pr-4">{r.total_calls}</td>
                            <td className="py-2 pr-4">{r.avg_overall_score}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
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

export default AdminReports;


