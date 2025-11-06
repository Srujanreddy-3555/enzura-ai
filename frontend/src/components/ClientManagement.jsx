import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import apiService from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { SkeletonCard, SkeletonTableRow } from './SkeletonLoader';
import ConfirmDialog from './ConfirmDialog';
import Sidebar from './Sidebar';
import UserHeader from './UserHeader';
import SuccessNotification from './SuccessNotification';

const ClientManagement = () => {
  const { user } = useAuth();
  const [activeItem, setActiveItem] = useState('Client Management');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [clients, setClients] = useState([]);
  const [salesReps, setSalesReps] = useState({});
  const [clientUsers, setClientUsers] = useState({});
  const [connectionStatus, setConnectionStatus] = useState({}); // { [clientId]: { ok: boolean, msg: string } }
  // OPTIMIZED: Start with loading = false so UI shows immediately!
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [successToast, setSuccessToast] = useState(null); // { message: string, type: 'success' | 'info' }
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [showSalesRepForm, setShowSalesRepForm] = useState(false);
  const [showClientUserForm, setShowClientUserForm] = useState(false);
  const [selectedClient, setSelectedClient] = useState(null);
  const [monitoringStatus, setMonitoringStatus] = useState(null);
  const [confirmDialog, setConfirmDialog] = useState({ isOpen: false, onConfirm: null, title: '', message: '' });
  
  // Pagination state for sales reps and client users (per client)
  const [salesRepPage, setSalesRepPage] = useState({}); // { [clientId]: pageNumber }
  const [clientUserPage, setClientUserPage] = useState({}); // { [clientId]: pageNumber }
  const ITEMS_PER_PAGE = 5;

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

  // Form states
  const [clientForm, setClientForm] = useState({
    name: '',
    s3_bucket_name: '',
    s3_region: 'ap-south-1',
    aws_access_key: '',
    aws_secret_key: '',
    processing_schedule: 'realtime',
    timezone: 'UTC'
  });

  const [salesRepForm, setSalesRepForm] = useState({
    name: '',
    email: '',
    phone: '',
    password: '' // optional: create login for rep now
  });

  const [clientUserForm, setClientUserForm] = useState({
    name: '',
    email: '',
    password: ''
  });

  useEffect(() => {
    fetchClients(true);
    fetchMonitoringStatus();

    // Set up auto-refresh every 5 seconds (silent, no loading spinner)
    const refreshInterval = setInterval(() => {
      fetchClients(false);
      fetchMonitoringStatus();
    }, 5000);

    return () => clearInterval(refreshInterval);
  }, []);

  // Adjust pagination when data changes (e.g., after deletion)
  useEffect(() => {
    clients.forEach(client => {
      // Adjust sales rep pagination
      const reps = salesReps[client.id] || [];
      const totalRepPages = Math.ceil(reps.length / ITEMS_PER_PAGE);
      setSalesRepPage(prev => {
        const currentPage = prev[client.id] || 1;
        if (currentPage > totalRepPages && totalRepPages > 0) {
          return { ...prev, [client.id]: totalRepPages };
        } else if (totalRepPages === 0 && currentPage > 1) {
          return { ...prev, [client.id]: 1 };
        }
        return prev; // No change needed
      });

      // Adjust client user pagination
      const users = clientUsers[client.id] || [];
      const totalUserPages = Math.ceil(users.length / ITEMS_PER_PAGE);
      setClientUserPage(prev => {
        const currentPage = prev[client.id] || 1;
        if (currentPage > totalUserPages && totalUserPages > 0) {
          return { ...prev, [client.id]: totalUserPages };
        } else if (totalUserPages === 0 && currentPage > 1) {
          return { ...prev, [client.id]: 1 };
        }
        return prev; // No change needed
      });
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clients, salesReps, clientUsers]);

  const fetchClients = async (showLoading = false) => {
    try {
      if (showLoading) {
        setLoading(true);
      }
      const clientsData = await apiService.getClients();
      setClients(clientsData || []);
      // Always clear error on successful response (even if empty)
      setError('');
      
      // OPTIMIZED: Fetch all users once (instead of per client)
      let allUsers = [];
      try {
        allUsers = await apiService.getUsers();
      } catch (error) {
        console.error('Error fetching users:', error);
      }
      
      // OPTIMIZED: Parallel fetch sales reps for all clients at once!
      const salesRepsData = {};
      const clientUsersData = {};
      
      // Fetch all sales reps in parallel
      const repPromises = clientsData.map(async (client) => {
        try {
          const reps = await apiService.getSalesReps(client.id);
          return { clientId: client.id, reps };
        } catch (error) {
          console.error(`Error fetching sales reps for client ${client.id}:`, error);
          return { clientId: client.id, reps: [] };
        }
      });
      
      const repResults = await Promise.allSettled(repPromises);
      repResults.forEach((result) => {
        if (result.status === 'fulfilled') {
          salesRepsData[result.value.clientId] = result.value.reps;
        }
      });
      
      // OPTIMIZED: Build client users map from single users fetch
      clientsData.forEach((client) => {
        clientUsersData[client.id] = allUsers.filter(u => 
          u.client_id === client.id && (u.role === 'CLIENT' || String(u.role).toLowerCase() === 'client')
        );
      });
      setSalesReps(salesRepsData);
      setClientUsers(clientUsersData);
    } catch (error) {
      // Only show error for actual failures (network errors, 500, etc.), not for empty data
      if (showLoading) {
        const isRealError = error.message && (
          error.message.includes('Failed to fetch') ||
          error.message.includes('Network') ||
          error.message.includes('500') ||
          error.message.includes('503') ||
          error.message.includes('Authentication')
        );
        
        if (isRealError) {
          setError('Failed to fetch clients');
        } else {
          // Successful response with empty data - clear error, show empty state
          setError('');
        }
      }
      console.error('Error fetching clients:', error);
    } finally {
      if (showLoading) {
        setLoading(false);
      }
    }
  };

  const fetchMonitoringStatus = async () => {
    try {
      const status = await apiService.getS3MonitoringStatus();
      setMonitoringStatus(status);
    } catch (error) {
      console.error('Error fetching monitoring status:', error);
    }
  };

  const handleCreateClient = async (e) => {
    e.preventDefault();
    try {
      await apiService.createClient(clientForm);
      const clientName = clientForm.name;
      const bucketName = clientForm.s3_bucket_name;
      setShowCreateForm(false);
      setClientForm({
        name: '',
        s3_bucket_name: '',
        s3_region: 'ap-south-1',
        aws_access_key: '',
        aws_secret_key: '',
        processing_schedule: 'realtime',
        timezone: 'UTC'
      });
      // Show success notification
      setSuccessToast({ message: `Client "${clientName}" created successfully!`, type: 'success' });
      fetchClients(false); // Silent refresh after action
      // Auto test connection for immediate feedback
      setTimeout(async () => {
        try {
          const clientsNow = await apiService.getClients();
          const created = clientsNow.find(c => c.name === clientName && c.s3_bucket_name === bucketName);
          if (created) {
            const res = await apiService.testClientConnection(created.id);
            setConnectionStatus(prev => ({ ...prev, [created.id]: { ok: true, msg: `Connected (${res.region})` } }));
          }
        } catch (err) {
          const detail = err?.message || 'Connection failed';
          const clientsNow = await apiService.getClients();
          const created = clientsNow.find(c => c.name === clientName && c.s3_bucket_name === bucketName);
          if (created) {
            setConnectionStatus(prev => ({ ...prev, [created.id]: { ok: false, msg: detail } }));
          }
        }
      }, 250);
    } catch (error) {
      setError('Failed to create client');
      console.error('Error creating client:', error);
    }
  };

  const handleCreateSalesRep = async (e) => {
    e.preventDefault();
    try {
      await apiService.createSalesRep(selectedClient.id, {
        name: salesRepForm.name,
        email: salesRepForm.email || undefined,
        phone: salesRepForm.phone || undefined,
      });

      const repName = salesRepForm.name;
      const clientName = selectedClient.name;

      // If email and password provided, also create a login user assigned to this client
      if (salesRepForm.email && salesRepForm.password) {
        try {
          await apiService.adminCreateUser({
            name: salesRepForm.name,
            email: salesRepForm.email,
            password: salesRepForm.password,
            client_id: selectedClient.id,
            role: 'REP',
          });
        } catch (err) {
          console.error('Error creating rep user login:', err);
          // continue; do not block rep creation if user creation fails
        }
      }
      setShowSalesRepForm(false);
      setSalesRepForm({ name: '', email: '', phone: '', password: '' });
      const clientId = selectedClient.id;
      setSelectedClient(null);
      // Reset pagination to page 1 to show newly added rep
      setSalesRepPage(prev => ({ ...prev, [clientId]: 1 }));
      // Show success notification
      setSuccessToast({ message: `Sales rep "${repName}" added to "${clientName}" successfully!`, type: 'success' });
      fetchClients(false); // Silent refresh after action
    } catch (error) {
      setError('Failed to create sales rep');
      console.error('Error creating sales rep:', error);
    }
  };

  const handleCreateClientUser = async (e) => {
    e.preventDefault();
    try {
      await apiService.adminCreateUser({
        name: clientUserForm.name,
        email: clientUserForm.email,
        password: clientUserForm.password,
        client_id: selectedClient.id,
        role: 'CLIENT',
      });
      const userName = clientUserForm.name;
      const clientName = selectedClient.name;
      setShowClientUserForm(false);
      setClientUserForm({ name: '', email: '', password: '' });
      const clientId = selectedClient.id;
      setSelectedClient(null);
      // Reset pagination to page 1 to show newly added client user
      setClientUserPage(prev => ({ ...prev, [clientId]: 1 }));
      // Show success notification
      setSuccessToast({ message: `Client user "${userName}" added to "${clientName}" successfully!`, type: 'success' });
      fetchClients(false); // Silent refresh after action
    } catch (error) {
      setError('Failed to create client user');
      console.error('Error creating client user:', error);
    }
  };

  const [deletingClientId, setDeletingClientId] = useState(null);
  const [deletingRepId, setDeletingRepId] = useState(null);

  const handleDeleteClient = (clientId) => {
    setConfirmDialog({
      isOpen: true,
      title: 'Delete Client',
      message: 'Are you sure you want to delete this client? This action cannot be undone.',
      confirmText: 'Delete',
      cancelText: 'Cancel',
      onConfirm: async () => {
        try {
          setDeletingClientId(clientId);
          await apiService.deleteClient(clientId);
          fetchClients(false); // Silent refresh after action
        } catch (error) {
          setError('Failed to delete client');
          console.error('Error deleting client:', error);
        } finally {
          setDeletingClientId(null);
        }
      }
    });
  };

  const handleDeleteSalesRep = (clientId, salesRepId, repName) => {
    setConfirmDialog({
      isOpen: true,
      title: 'Delete Sales Representative',
      message: `Are you sure you want to delete "${repName}"? This action cannot be undone.`,
      confirmText: 'Delete',
      cancelText: 'Cancel',
      onConfirm: async () => {
        try {
          setDeletingRepId(salesRepId);
          const response = await apiService.deleteSalesRep(clientId, salesRepId);
          // Show success message with rep name
          const successMessage = response?.message || response?.rep_name 
            ? `Sales rep "${response.rep_name || repName}" deleted successfully`
            : `Sales rep "${repName}" deleted successfully`;
          setSuccess(successMessage);
          setError(''); // Clear any previous errors
          fetchClients(false); // Silent refresh after action
          // Clear success message after 3 seconds
          setTimeout(() => setSuccess(''), 3000);
        } catch (error) {
          setError('Failed to delete sales rep');
          setSuccess(''); // Clear success message on error
          console.error('Error deleting sales rep:', error);
        } finally {
          setDeletingRepId(null);
        }
      }
    });
  };

  const handleDeleteClientUser = (userId) => {
    setConfirmDialog({
      isOpen: true,
      title: 'Delete Client User',
      message: 'Are you sure you want to delete this client user? This action cannot be undone.',
      confirmText: 'Delete',
      cancelText: 'Cancel',
      onConfirm: async () => {
        try {
          await apiService.deleteUser(userId);
          fetchClients(false); // Silent refresh after action
        } catch (error) {
          setError('Failed to delete client user');
          console.error('Error deleting client user:', error);
        }
      }
    });
  };

  const handleTestConnection = async (clientId) => {
    try {
      const result = await apiService.testClientConnection(clientId);
      setConnectionStatus(prev => ({ ...prev, [clientId]: { ok: true, msg: `Connected (${result.region})` } }));
      alert(`Connection test successful!\nBucket: ${result.bucket_name}\nObjects: ${result.object_count}`);
    } catch (error) {
      const msg = error?.message || 'Connection failed';
      setConnectionStatus(prev => ({ ...prev, [clientId]: { ok: false, msg } }));
      alert(`Connection test failed: ${msg}`);
    }
  };

  const handleToggleMonitoring = async (clientId, isMonitored) => {
    try {
      if (isMonitored) {
        await apiService.removeClientFromMonitoring(clientId);
      } else {
        await apiService.addClientToMonitoring(clientId);
      }
      fetchMonitoringStatus();
    } catch (error) {
      setError('Failed to toggle monitoring');
      console.error('Error toggling monitoring:', error);
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

  // Pagination helper functions
  const getPaginatedSalesReps = (clientId) => {
    const reps = salesReps[clientId] || [];
    const currentPage = salesRepPage[clientId] || 1;
    const startIndex = (currentPage - 1) * ITEMS_PER_PAGE;
    const endIndex = startIndex + ITEMS_PER_PAGE;
    return {
      items: reps.slice(startIndex, endIndex),
      totalPages: Math.ceil(reps.length / ITEMS_PER_PAGE),
      currentPage,
      totalItems: reps.length
    };
  };

  const getPaginatedClientUsers = (clientId) => {
    const users = clientUsers[clientId] || [];
    const currentPage = clientUserPage[clientId] || 1;
    const startIndex = (currentPage - 1) * ITEMS_PER_PAGE;
    const endIndex = startIndex + ITEMS_PER_PAGE;
    return {
      items: users.slice(startIndex, endIndex),
      totalPages: Math.ceil(users.length / ITEMS_PER_PAGE),
      currentPage,
      totalItems: users.length
    };
  };

  const handleSalesRepPageChange = (clientId, newPage) => {
    setSalesRepPage(prev => ({ ...prev, [clientId]: newPage }));
  };

  const handleClientUserPageChange = (clientId, newPage) => {
    setClientUserPage(prev => ({ ...prev, [clientId]: newPage }));
  };

  // Skeleton loader for initial load
  if (loading && clients.length === 0) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header Skeleton */}
        <div className="mb-8">
          <div className="h-8 bg-gray-300 rounded w-64 mb-4 animate-pulse"></div>
          <div className="h-4 bg-gray-300 rounded w-96 animate-pulse"></div>
        </div>
        
        {/* Clients Grid Skeleton */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
          {[1, 2, 3].map((i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
        
        {/* Table Skeleton */}
        <div className="bg-white shadow rounded-xl overflow-hidden">
          <div className="px-4 py-5 sm:p-6">
            <div className="h-6 bg-gray-300 rounded w-48 mb-6 animate-pulse"></div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    {['Client', 'Bucket', 'Region', 'Status', 'Actions'].map((header) => (
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
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Mobile Header */}
      <div className="lg:hidden bg-white shadow-sm border-b border-gray-200">
        <div className="flex items-center justify-between px-4 py-3">
          <h1 className="text-lg font-semibold text-gray-900">Client Management</h1>
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
              <h1 className="text-4xl font-bold text-gray-900 mb-2">Client Management</h1>
              <p className="text-gray-600">Manage clients, sales reps, and S3 monitoring</p>
            </div>
            <div className="flex space-x-4">
              <button
                onClick={() => setShowCreateForm(true)}
                className="bg-gradient-to-r from-indigo-600 to-purple-600 text-white px-6 py-3 rounded-xl font-semibold hover:from-indigo-700 hover:to-purple-700 transition-all duration-200 shadow-lg hover:shadow-xl"
              >
                + Add Client
              </button>
            </div>
          </div>

          {/* Monitoring Status */}
          {monitoringStatus && (
            <div className="mt-6 p-4 bg-gradient-to-r from-green-50 to-emerald-50 rounded-xl border border-green-200">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className={`w-3 h-3 rounded-full ${monitoringStatus.is_running ? 'bg-green-500' : 'bg-red-500'}`}></div>
                  <span className="font-semibold text-gray-800">
                    S3 Monitoring: {monitoringStatus.is_running ? 'Active' : 'Inactive'}
                  </span>
                </div>
                <div className="text-sm text-gray-600">
                  Monitored Clients: {monitoringStatus.monitored_clients.length} | 
                  Queue Size: {monitoringStatus.queue_size}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Success Message */}
        {success && (
          <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-xl mb-6 flex items-center justify-between">
            <span>{success}</span>
            <button
              onClick={() => setSuccess('')}
              className="text-green-700 hover:text-green-900 font-bold text-lg leading-none"
              title="Dismiss"
            >
              ×
            </button>
          </div>
        )}
        
        {/* Error Message - Only show for real errors, not empty data */}
        {error && !loading && clients.length === 0 && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl mb-6 flex items-center justify-between">
            <span>{error}</span>
            <button
              onClick={() => setError('')}
              className="text-red-700 hover:text-red-900 font-bold text-lg leading-none"
              title="Dismiss"
            >
              ×
            </button>
          </div>
        )}

        {/* Empty State - No clients */}
        {!loading && !error && clients.length === 0 && (
          <div className="text-center py-12 bg-white rounded-2xl shadow-xl">
            <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
            </svg>
            <h3 className="mt-2 text-sm font-medium text-gray-900">No clients yet</h3>
            <p className="mt-1 text-sm text-gray-500">Get started by creating your first client.</p>
            <div className="mt-6">
              <button
                onClick={() => setShowCreateForm(true)}
                className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-purple-500"
              >
                <svg className="-ml-1 mr-2 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
                </svg>
                Create Client
              </button>
            </div>
          </div>
        )}

        {/* Clients Grid */}
        {!loading && clients.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
          {clients.map((client) => (
            <div key={client.id} className="bg-white rounded-2xl shadow-xl p-6 hover:shadow-2xl transition-all duration-300">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h3 className="text-xl font-bold text-gray-900">{client.name}</h3>
                  <p className="text-gray-600 text-sm">Bucket: {client.s3_bucket_name}</p>
                  <p className="text-gray-600 text-sm">Region: {client.s3_region}</p>
                </div>
                <div className="flex space-x-2">
                  <button
                    onClick={() => handleTestConnection(client.id)}
                    disabled={deletingClientId === client.id}
                    className={`bg-blue-100 text-blue-700 px-3 py-1 rounded-lg text-sm font-medium transition-colors ${deletingClientId===client.id ? 'opacity-50 cursor-not-allowed' : 'hover:bg-blue-200'}`}
                  >
                    Test
                  </button>
                  <button
                    onClick={() => handleDeleteClient(client.id)}
                    disabled={deletingClientId === client.id}
                    className={`bg-red-100 text-red-700 px-3 py-1 rounded-lg text-sm font-medium transition-colors ${deletingClientId===client.id ? 'opacity-50 cursor-not-allowed' : 'hover:bg-red-200'}`}
                  >
                    {deletingClientId===client.id ? 'Deleting...' : 'Delete'}
                  </button>
                </div>
              </div>

              {/* Client Status */}
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center space-x-2">
                  <div className={`w-2 h-2 rounded-full ${client.status === 'active' ? 'bg-green-500' : 'bg-gray-400'}`}></div>
                  <span className="text-sm font-medium text-gray-700">{client.status}</span>
                  {connectionStatus[client.id] && (
                    <span className={`ml-2 text-xs px-2 py-0.5 rounded-full ${connectionStatus[client.id].ok ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`} title={connectionStatus[client.id].msg}>
                      {connectionStatus[client.id].ok ? 'S3 Connected' : 'S3 Error'}
                    </span>
                  )}
                </div>
                <div className="text-sm text-gray-600">
                  Schedule: {client.processing_schedule}
                </div>
              </div>

              {/* Monitoring Controls */}
              <div className="flex items-center justify-between mb-4 p-3 bg-gray-50 rounded-lg">
                <span className="text-sm font-medium text-gray-700">S3 Monitoring (Start begins background scans; Scan triggers one-time pickup)</span>
                <div className="flex space-x-2">
                  <button
                    onClick={() => handleManualScan(client.id)}
                    className="bg-yellow-100 text-yellow-700 px-2 py-1 rounded text-xs font-medium hover:bg-yellow-200 transition-colors"
                  >
                    Manual Scan
                  </button>
                  <button
                    onClick={() => handleToggleMonitoring(client.id, monitoringStatus?.monitored_clients.includes(client.id))}
                    className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
                      monitoringStatus?.monitored_clients.includes(client.id)
                        ? 'bg-red-100 text-red-700 hover:bg-red-200'
                        : 'bg-green-100 text-green-700 hover:bg-green-200'
                    }`}
                  >
                    {monitoringStatus?.monitored_clients.includes(client.id) ? 'Stop Monitoring' : 'Start Monitoring'}
                  </button>
                </div>
              </div>

              {/* Sales Reps */}
              <div className="border-t pt-4">
                <div className="flex justify-between items-center mb-3">
                  <h4 className="font-semibold text-gray-800">Sales Reps</h4>
                  <button
                    onClick={() => {
                      setSelectedClient(client);
                      setShowSalesRepForm(true);
                    }}
                    className="bg-indigo-100 text-indigo-700 px-3 py-1 rounded-lg text-sm font-medium hover:bg-indigo-200 transition-colors"
                  >
                    + Add Rep
                  </button>
                </div>
                
                {(() => {
                  const paginated = getPaginatedSalesReps(client.id);
                  return (
                    <>
                      <div className="space-y-2 max-h-48 overflow-y-auto pr-2 scrollbar-thin">
                        {paginated.items.map((rep) => (
                          <div key={rep.id} className="flex justify-between items-center p-2 bg-gray-50 rounded-lg">
                            <div>
                              <div className="font-medium text-gray-800">{rep.name}</div>
                              {rep.email && <div className="text-sm text-gray-600">{rep.email}</div>}
                            </div>
                            <button
                              onClick={() => handleDeleteSalesRep(client.id, rep.id, rep.name)}
                              disabled={deletingRepId === rep.id}
                              className={`text-sm font-medium ${deletingRepId===rep.id ? 'text-red-400 cursor-not-allowed' : 'text-red-600 hover:text-red-800'}`}
                            >
                              {deletingRepId===rep.id ? 'Deleting...' : 'Delete'}
                            </button>
                          </div>
                        ))}
                        
                        {paginated.totalItems === 0 && (
                          <div className="text-sm text-gray-500 italic">No sales reps added yet</div>
                        )}
                      </div>
                      
                      {/* Pagination Controls for Sales Reps */}
                      {paginated.totalPages > 1 && (
                        <div className="mt-4 flex items-center justify-between border-t pt-3">
                          <div className="text-sm text-gray-600">
                            Showing {((paginated.currentPage - 1) * ITEMS_PER_PAGE) + 1} to {Math.min(paginated.currentPage * ITEMS_PER_PAGE, paginated.totalItems)} of {paginated.totalItems}
                          </div>
                          <div className="flex items-center space-x-2">
                            <button
                              onClick={() => handleSalesRepPageChange(client.id, paginated.currentPage - 1)}
                              disabled={paginated.currentPage === 1}
                              className={`px-3 py-1 rounded-lg text-sm font-medium transition-colors ${
                                paginated.currentPage === 1
                                  ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                                  : 'bg-indigo-100 text-indigo-700 hover:bg-indigo-200'
                              }`}
                            >
                              Previous
                            </button>
                            <span className="text-sm text-gray-600">
                              Page {paginated.currentPage} of {paginated.totalPages}
                            </span>
                            <button
                              onClick={() => handleSalesRepPageChange(client.id, paginated.currentPage + 1)}
                              disabled={paginated.currentPage === paginated.totalPages}
                              className={`px-3 py-1 rounded-lg text-sm font-medium transition-colors ${
                                paginated.currentPage === paginated.totalPages
                                  ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                                  : 'bg-indigo-100 text-indigo-700 hover:bg-indigo-200'
                              }`}
                            >
                              Next
                            </button>
                          </div>
                        </div>
                      )}
                    </>
                  );
                })()}
              </div>

              {/* Client Users */}
              <div className="border-t pt-4 mt-4">
                <div className="flex justify-between items-center mb-3">
                  <h4 className="font-semibold text-gray-800">Client Users</h4>
                  <button
                    onClick={() => {
                      setSelectedClient(client);
                      setShowClientUserForm(true);
                    }}
                    className="bg-purple-100 text-purple-700 px-3 py-1 rounded-lg text-sm font-medium hover:bg-purple-200 transition-colors"
                  >
                    + Add Client User
                  </button>
                </div>
                
                {(() => {
                  const paginated = getPaginatedClientUsers(client.id);
                  return (
                    <>
                      <div className="space-y-2 max-h-48 overflow-y-auto pr-2 scrollbar-thin">
                        {paginated.items.map((cu) => (
                          <div key={cu.id} className="flex justify-between items-center p-2 bg-gray-50 rounded-lg">
                            <div>
                              <div className="font-medium text-gray-800">{cu.name}</div>
                              <div className="text-sm text-gray-600">{cu.email}</div>
                            </div>
                            <button
                              onClick={() => handleDeleteClientUser(cu.id)}
                              className="text-red-600 hover:text-red-800 text-sm font-medium"
                            >
                              Delete
                            </button>
                          </div>
                        ))}

                        {paginated.totalItems === 0 && (
                          <div className="text-sm text-gray-500 italic">No client users added yet</div>
                        )}
                      </div>
                      
                      {/* Pagination Controls for Client Users */}
                      {paginated.totalPages > 1 && (
                        <div className="mt-4 flex items-center justify-between border-t pt-3">
                          <div className="text-sm text-gray-600">
                            Showing {((paginated.currentPage - 1) * ITEMS_PER_PAGE) + 1} to {Math.min(paginated.currentPage * ITEMS_PER_PAGE, paginated.totalItems)} of {paginated.totalItems}
                          </div>
                          <div className="flex items-center space-x-2">
                            <button
                              onClick={() => handleClientUserPageChange(client.id, paginated.currentPage - 1)}
                              disabled={paginated.currentPage === 1}
                              className={`px-3 py-1 rounded-lg text-sm font-medium transition-colors ${
                                paginated.currentPage === 1
                                  ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                                  : 'bg-purple-100 text-purple-700 hover:bg-purple-200'
                              }`}
                            >
                              Previous
                            </button>
                            <span className="text-sm text-gray-600">
                              Page {paginated.currentPage} of {paginated.totalPages}
                            </span>
                            <button
                              onClick={() => handleClientUserPageChange(client.id, paginated.currentPage + 1)}
                              disabled={paginated.currentPage === paginated.totalPages}
                              className={`px-3 py-1 rounded-lg text-sm font-medium transition-colors ${
                                paginated.currentPage === paginated.totalPages
                                  ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                                  : 'bg-purple-100 text-purple-700 hover:bg-purple-200'
                              }`}
                            >
                              Next
                            </button>
                          </div>
                        </div>
                      )}
                    </>
                  );
                })()}
              </div>
            </div>
          ))}
        </div>
        )}

        {/* Create Client Modal */}
        {showCreateForm && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-2xl p-8 max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
              <h2 className="text-2xl font-bold text-gray-900 mb-6">Create New Client</h2>
              
              <form onSubmit={handleCreateClient} className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Client Name</label>
                    <input
                      type="text"
                      value={clientForm.name}
                      onChange={(e) => setClientForm({...clientForm, name: e.target.value})}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                      required
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">S3 Bucket Name</label>
                    <input
                      type="text"
                      value={clientForm.s3_bucket_name}
                      onChange={(e) => setClientForm({...clientForm, s3_bucket_name: e.target.value})}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                      required
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">S3 Region</label>
                    <select
                      value={clientForm.s3_region}
                      onChange={(e) => setClientForm({...clientForm, s3_region: e.target.value})}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                      required
                    >
                      <option value="ap-south-1">Asia Pacific (Mumbai) ap-south-1</option>
                      <option value="us-east-1">US East (N. Virginia)</option>
                      <option value="us-west-2">US West (Oregon)</option>
                      <option value="eu-west-1">Europe (Ireland)</option>
                      <option value="ap-southeast-1">Asia Pacific (Singapore)</option>
                      <option value="ap-southeast-2">Asia Pacific (Sydney)</option>
                      <option value="eu-central-1">Europe (Frankfurt)</option>
                      <option value="eu-west-2">Europe (London)</option>
                    </select>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Processing Schedule</label>
                    <select
                      value={clientForm.processing_schedule}
                      onChange={(e) => setClientForm({...clientForm, processing_schedule: e.target.value})}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    >
                      <option value="hourly">Hourly</option>
                      <option value="daily">Daily</option>
                      <option value="twice_daily">Twice Daily</option>
                      <option value="every_6_hours">Every 6 Hours</option>
                      <option value="every_2_hours">Every 2 Hours</option>
                    </select>
                  </div>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">AWS Access Key</label>
                  <input
                    type="text"
                    value={clientForm.aws_access_key}
                    onChange={(e) => setClientForm({...clientForm, aws_access_key: e.target.value})}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    required
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">AWS Secret Key</label>
                  <input
                    type="password"
                    value={clientForm.aws_secret_key}
                    onChange={(e) => setClientForm({...clientForm, aws_secret_key: e.target.value})}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    required
                  />
                </div>
                
                <div className="flex justify-end space-x-4 pt-4">
                  <button
                    type="button"
                    onClick={() => setShowCreateForm(false)}
                    className="px-6 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
                  >
                    Create Client
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Create Sales Rep Modal */}
        {showSalesRepForm && selectedClient && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-2xl p-8 max-w-md w-full mx-4">
              <h2 className="text-2xl font-bold text-gray-900 mb-6">
                Add Sales Rep to {selectedClient.name}
              </h2>
              
              <form onSubmit={handleCreateSalesRep} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Sales Rep Name</label>
                  <input
                    type="text"
                    value={salesRepForm.name}
                    onChange={(e) => setSalesRepForm({...salesRepForm, name: e.target.value})}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    required
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Email (Optional)</label>
                  <input
                    type="email"
                    value={salesRepForm.email}
                    onChange={(e) => setSalesRepForm({...salesRepForm, email: e.target.value})}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Set Rep Login Password (Optional)</label>
                  <input
                    type="password"
                    value={salesRepForm.password}
                    onChange={(e) => setSalesRepForm({...salesRepForm, password: e.target.value})}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    placeholder="Set a temporary password"
                  />
                  <p className="text-xs text-gray-500 mt-1">If provided with Email, a login user will be created and assigned to this client.</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Phone (Optional)</label>
                  <input
                    type="tel"
                    value={salesRepForm.phone}
                    onChange={(e) => setSalesRepForm({...salesRepForm, phone: e.target.value})}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  />
                </div>
                
                <div className="flex justify-end space-x-4 pt-4">
                  <button
                    type="button"
                    onClick={() => {
                      setShowSalesRepForm(false);
                      setSelectedClient(null);
                    }}
                    className="px-6 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
                  >
                    Add Sales Rep
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Create Client User Modal */}
        {showClientUserForm && selectedClient && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-2xl p-8 max-w-md w-full mx-4">
              <h2 className="text-2xl font-bold text-gray-900 mb-6">
                Add Client User for {selectedClient.name}
              </h2>

              <form onSubmit={handleCreateClientUser} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Name</label>
                  <input
                    type="text"
                    value={clientUserForm.name}
                    onChange={(e) => setClientUserForm({ ...clientUserForm, name: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    required
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Email</label>
                  <input
                    type="email"
                    value={clientUserForm.email}
                    onChange={(e) => setClientUserForm({ ...clientUserForm, email: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Password</label>
                  <input
                    type="password"
                    value={clientUserForm.password}
                    onChange={(e) => setClientUserForm({ ...clientUserForm, password: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    required
                  />
                </div>

                <div className="flex justify-end space-x-4 pt-4">
                  <button
                    type="button"
                    onClick={() => {
                      setShowClientUserForm(false);
                      setSelectedClient(null);
                    }}
                    className="px-6 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-6 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
                  >
                    Add Client User
                  </button>
                </div>
              </form>
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

      {/* Success Notification Toast */}
      {successToast && (
        <SuccessNotification
          message={successToast.message}
          type={successToast.type || 'success'}
          onClose={() => setSuccessToast(null)}
          duration={3000}
        />
      )}
    </div>
  );
};

export default ClientManagement;
