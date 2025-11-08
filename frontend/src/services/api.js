// API service for communicating with the Enzura AI backend
// OPTIMIZED: Use environment variable for API URL (supports production deployment)
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

class ApiService {
  constructor() {
    this.baseURL = API_BASE_URL;
    this.token = localStorage.getItem('auth_token');
    this.cache = new Map(); // Cache for API responses
    this.pendingRequests = new Map(); // OPTIMIZED: Deduplicate simultaneous requests
    this.cacheTimestamps = new Map(); // Track cache age
    // OPTIMIZED: Increased cache TTL for better performance with large datasets (200+ calls, 20+ clients)
    // 5 seconds provides good balance between freshness and performance
    this.CACHE_TTL = 5000; // Cache time-to-live: 5 seconds
  }

  // Set authentication token
  setToken(token) {
    this.token = token;
    localStorage.setItem('auth_token', token);
  }

  // Clear authentication token
  clearToken() {
    this.token = null;
    localStorage.removeItem('auth_token');
    // OPTIMIZED: Clear all cached API responses
    if (this.cache) {
      this.cache.clear();
    }
  }

  // Get headers for API requests
  getHeaders(includeAuth = true) {
    const headers = {
      'Content-Type': 'application/json',
    };

    if (includeAuth) {
      // Always read fresh token from localStorage (in case it was updated)
      const token = localStorage.getItem('auth_token');
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
        // Update instance token as well
        this.token = token;
      }
    }

    return headers;
  }

  // Get headers for file upload requests
  getUploadHeaders() {
    const headers = {};

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    return headers;
  }

  // Generic API request method with caching and deduplication
  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;
    const cacheKey = `${options.method || 'GET'}:${url}`;
    
    // OPTIMIZED: Check cache first (for GET requests only)
    if ((!options.method || options.method === 'GET') && !options.skipCache) {
      const cached = this.cache.get(cacheKey);
      const cacheTime = this.cacheTimestamps.get(cacheKey);
      
      if (cached && cacheTime && (Date.now() - cacheTime) < this.CACHE_TTL) {
        // Return cached data immediately
        return Promise.resolve(JSON.parse(JSON.stringify(cached))); // Deep clone
      }
    }
    
    // OPTIMIZED: Deduplicate simultaneous requests
    if (this.pendingRequests.has(cacheKey)) {
      // If same request is already in progress, return the existing promise
      return this.pendingRequests.get(cacheKey);
    }
    
    const config = {
      headers: this.getHeaders(options.includeAuth !== false),
      ...options,
    };

    // Create request promise
    const requestPromise = (async () => {
      try {
        const response = await fetch(url, config);
      
        // Handle 401 Unauthorized - token expired or invalid
        if (response.status === 401) {
          console.warn('401 Unauthorized - Token may be expired. Clearing auth token.');
          this.clearToken();
          // Redirect to login if not already there
          if (window.location.pathname !== '/login' && window.location.pathname !== '/') {
            window.location.href = '/login';
          }
          throw new Error('Authentication failed. Please log in again.');
        }
        
        // Handle 202 Accepted (processing in progress)
        if (response.status === 202) {
          const errorData = await response.json().catch(() => ({}));
          // Return null for insights if still processing (not an error)
          if (url.includes('/insights/')) {
            return null;
          }
          throw new Error(errorData.detail || `Processing in progress: ${response.status}`);
        }
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          console.error('❌ API ERROR:', response.status, errorData);
          throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
        }

        // Handle empty responses (204 No Content is also a success)
        if (response.status === 204) {
          return { message: 'Operation completed successfully' };
        }
        
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
          const jsonData = await response.json();
          
          // OPTIMIZED: Cache successful GET responses
          if ((!options.method || options.method === 'GET') && response.ok && !options.skipCache) {
            this.cache.set(cacheKey, jsonData);
            this.cacheTimestamps.set(cacheKey, Date.now());
          }
          
          return jsonData;
        }
        
        return response;
      } catch (error) {
        console.error('API request failed:', error);
        throw error;
      } finally {
        // Remove from pending requests
        this.pendingRequests.delete(cacheKey);
      }
    })();
    
    // Store pending request for deduplication
    this.pendingRequests.set(cacheKey, requestPromise);
    
    return requestPromise;
  }
  
  // OPTIMIZED: Clear cache for specific endpoint (useful after mutations)
  clearCache(endpoint) {
    const patterns = Array.isArray(endpoint) ? endpoint : [endpoint];
    for (const pattern of patterns) {
      for (const key of this.cache.keys()) {
        if (key.includes(pattern)) {
          this.cache.delete(key);
          this.cacheTimestamps.delete(key);
        }
      }
    }
  }

  // Authentication endpoints
  async login(email, password) {
    const formData = new FormData();
    formData.append('username', email);
    formData.append('password', password);

    const response = await fetch(`${this.baseURL}/auth/login`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || 'Login failed');
    }

    const data = await response.json();
    this.setToken(data.access_token);
    return data;
  }

  async register(userData) {
    return this.request('/auth/register', {
      method: 'POST',
      body: JSON.stringify(userData),
    });
  }

  async getCurrentUser() {
    return this.request('/auth/me');
  }

  async logout() {
    this.clearToken();
    return this.request('/auth/logout', { method: 'POST' });
  }

  // File upload endpoints
  async uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);
    // English only - no language or translation parameters needed

    const response = await fetch(`${this.baseURL}/uploads/upload`, {
      method: 'POST',
      headers: this.getUploadHeaders(),
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || 'Upload failed');
    }

    return await response.json();
  }

  async uploadMultipleFiles(files) {
    const formData = new FormData();
    files.forEach(file => {
      formData.append('files', file);
    });
    // English only - no language or translation parameters needed

    const response = await fetch(`${this.baseURL}/uploads/upload-multiple`, {
      method: 'POST',
      headers: this.getUploadHeaders(),
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || 'Upload failed');
    }

    return await response.json();
  }

  async getUploadProgress(callId) {
    return this.request(`/uploads/progress/${callId}`);
  }

  async deleteUploadedFile(callId) {
    return this.request(`/uploads/${callId}`, { method: 'DELETE' });
  }

  async getSupportedFormats() {
    return this.request('/uploads/supported-formats', { includeAuth: false });
  }

  // Calls endpoints
  // OPTIMIZED: Get dashboard statistics without fetching all calls
  async getDashboardStats(options = {}) {
    return this.request('/calls/stats', options);
  }

  // OPTIMIZED: Server-side pagination for better performance with 200+ calls
  async getCalls(statusFilter = null, searchTerm = null, skip = 0, limit = 50) {
    const params = new URLSearchParams();
    if (statusFilter) params.append('status_filter', statusFilter);
    if (searchTerm) params.append('search_term', searchTerm);
    // OPTIMIZED: Add pagination parameters
    params.append('skip', skip.toString());
    params.append('limit', limit.toString());
    
    const queryString = params.toString();
    const endpoint = `/calls/?${queryString}`;
    
    // Returns: { calls: [...], total: number, skip: number, limit: number }
    return this.request(endpoint);
  }

  async getCallById(callId) {
    return this.request(`/calls/${callId}`);
  }

  async getCallAudio(callId, download = false) {
    const url = `${this.baseURL}/calls/${callId}/audio${download ? '?download=true' : ''}`;
    
    try {
      const response = await fetch(url, {
        method: 'GET',
        headers: this.getHeaders(),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(errorData.detail || `Failed to get audio: ${response.status}`);
      }

      if (download) {
        // For download, get blob and return blob URL
        const blob = await response.blob();
        const blobUrl = window.URL.createObjectURL(blob);
        return blobUrl;
      } else {
        // For streaming: Get pre-signed URL from JSON response (FAST!)
        const data = await response.json();
        // Return the pre-signed S3 URL directly - browser can stream immediately!
        return data.url;
      }
    } catch (error) {
      console.error(`❌ Error getting audio for call ${callId}:`, error);
      throw error;
    }
  }

  async extractCallDuration(callId) {
    // Call backend endpoint to manually extract duration for a call
    return this.request(`/calls/${callId}/extract-duration`, {
      method: 'POST'
    });
  }

  async updateCallStatus(callId, statusData) {
    return this.request(`/calls/${callId}/status`, {
      method: 'PUT',
      body: JSON.stringify(statusData),
    });
  }

  async deleteCall(callId) {
    // OPTIMIZED: Targeted cache invalidation (more efficient than clearing all)
    // Only clear cache entries related to calls, not the entire cache
    if (this.cache) {
      const cacheKeysToDelete = [];
      for (const [key] of this.cache.entries()) {
        // Cache keys are in format: "GET:http://localhost:8000/api/calls?..."
        if (typeof key === 'string') {
          // Delete any cache entry related to calls
          if (key.includes('/calls') || key.includes('/calls/') || key.includes('/calls?') || key.includes('/calls/stats')) {
            cacheKeysToDelete.push(key);
          }
          // Delete batch insights cache (includes call insights)
          if (key.includes('/insights/batch')) {
            cacheKeysToDelete.push(key);
          }
        }
      }
      // Delete only relevant cache entries
      cacheKeysToDelete.forEach(key => {
        this.cache.delete(key);
        this.cacheTimestamps.delete(key);
      });
    }
    
    // Perform the delete operation
    const result = await this.request(`/calls/${callId}`, { method: 'DELETE' });
    
    // OPTIMIZED: Don't clear entire cache - only invalidate related entries
    // This preserves other cached data (clients, users, etc.)
    
    return result;
  }

  async getAudioUrl(callId) {
    return this.request(`/calls/${callId}/audio-url`);
  }

  async getCallSummary() {
    return this.request('/calls/stats/summary');
  }

  // Users endpoints
  async getUsers() {
    return this.request('/users/');
  }

  async deleteUser(userId) {
    return this.request(`/users/${userId}`, { method: 'DELETE' });
  }

  async getUserById(userId) {
    return this.request(`/users/${userId}`);
  }

  async getLeaderboard(options = {}) {
    return this.request('/calls/stats/leaderboard', options);
  }

  // Transcripts endpoints
  async getTranscriptByCallId(callId) {
    return this.request(`/transcripts/call/${callId}`);
  }

  async createTranscript(transcriptData) {
    return this.request('/transcripts/', {
      method: 'POST',
      body: JSON.stringify(transcriptData),
    });
  }

  async updateTranscript(callId, transcriptData) {
    return this.request(`/transcripts/call/${callId}`, {
      method: 'PUT',
      body: JSON.stringify(transcriptData),
    });
  }

  async deleteTranscript(callId) {
    return this.request(`/transcripts/call/${callId}`, { method: 'DELETE' });
  }

  async searchTranscripts(query) {
    return this.request(`/transcripts/search?query=${encodeURIComponent(query)}`);
  }

  // Insights endpoints
  async getInsightByCallId(callId) {
    // OPTIMIZED: Removed verbose console.log for production performance
    // Only log errors in production
    try {
      const result = await this.request(`/insights/call/${callId}`);
      return result;
    } catch (error) {
      console.error('Error fetching insight:', error);
      throw error;
    }
  }

  // Batch insights endpoint (optimized - fetches multiple insights in one request)
  async getBatchInsights(callIds) {
    // callIds should be an array like [1, 2, 3] or comma-separated string "1,2,3"
    const idsString = Array.isArray(callIds) ? callIds.join(',') : callIds;
    return this.request(`/insights/batch?call_ids=${idsString}`);
  }

  async createInsight(insightData) {
    return this.request('/insights/', {
      method: 'POST',
      body: JSON.stringify(insightData),
    });
  }

  async updateInsight(callId, insightData) {
    return this.request(`/insights/call/${callId}`, {
      method: 'PUT',
      body: JSON.stringify(insightData),
    });
  }

  async deleteInsight(callId) {
    return this.request(`/insights/call/${callId}`, { method: 'DELETE' });
  }

  async getSentimentAnalytics() {
    return this.request('/insights/analytics/sentiment');
  }

  async getKeywordAnalytics(limit = 10) {
    return this.request(`/insights/analytics/keywords?limit=${limit}`);
  }

  // Multi-tenant Client Management endpoints
  async getClients() {
    return this.request('/clients/');
  }

  async getClientById(clientId) {
    return this.request(`/clients/${clientId}`);
  }

  async createClient(clientData) {
    const result = await this.request('/clients/', {
      method: 'POST',
      body: JSON.stringify(clientData),
    });
    this.clearCache(['/clients']);
    return result;
  }

  async updateClient(clientId, clientData) {
    const result = await this.request(`/clients/${clientId}`, {
      method: 'PUT',
      body: JSON.stringify(clientData),
    });
    this.clearCache(['/clients']);
    return result;
  }

  async deleteClient(clientId) {
    const result = await this.request(`/clients/${clientId}`, { method: 'DELETE' });
    this.clearCache(['/clients']);
    return result;
  }

  async getClientStats(clientId) {
    return this.request(`/clients/${clientId}/stats`);
  }

  // Sales Rep Management endpoints
  async getSalesReps(clientId) {
    return this.request(`/clients/${clientId}/sales-reps`);
  }

  async getSalesRepById(clientId, salesRepId) {
    return this.request(`/clients/${clientId}/sales-reps/${salesRepId}`);
  }

  async createSalesRep(clientId, salesRepData) {
    return this.request(`/clients/${clientId}/sales-reps`, {
      method: 'POST',
      body: JSON.stringify(salesRepData),
    });
  }

  async updateSalesRep(clientId, salesRepId, salesRepData) {
    return this.request(`/clients/${clientId}/sales-reps/${salesRepId}`, {
      method: 'PUT',
      body: JSON.stringify(salesRepData),
    });
  }

  async deleteSalesRep(clientId, salesRepId) {
    return this.request(`/clients/${clientId}/sales-reps/${salesRepId}`, { method: 'DELETE' });
  }

  // User Management endpoints
  async getUnassignedUsers() {
    return this.request('/auth/unassigned-users');
  }

  async assignUserToClient(userId, clientId) {
    return this.request(`/auth/assign-client/${userId}?client_id=${clientId}`, {
      method: 'PUT',
    });
  }

  async adminCreateUser({ name, email, password, client_id, role = 'rep' }) {
    const normalizedRole = (role || 'rep').toUpperCase();
    return this.request('/auth/admin-create-user', {
      method: 'POST',
      body: JSON.stringify({ name, email, password, client_id, role: normalizedRole }),
    });
  }

  // S3 Monitoring endpoints
  async startS3Monitoring() {
    return this.request('/s3-monitoring/start', { method: 'POST' });
  }

  async stopS3Monitoring() {
    return this.request('/s3-monitoring/stop', { method: 'POST' });
  }

  async getS3MonitoringStatus() {
    return this.request('/s3-monitoring/status');
  }

  async addClientToMonitoring(clientId) {
    return this.request(`/s3-monitoring/add-client/${clientId}`, { method: 'POST' });
  }

  async removeClientFromMonitoring(clientId) {
    return this.request(`/s3-monitoring/remove-client/${clientId}`, { method: 'DELETE' });
  }

  async manualScanClient(clientId) {
    return this.request(`/s3-monitoring/scan-client/${clientId}`, { method: 'POST' });
  }

  async getMonitoredClients() {
    return this.request('/s3-monitoring/clients');
  }

  async testClientConnection(clientId) {
    return this.request(`/s3-monitoring/test-connection/${clientId}`);
  }

  // Enhanced Calls endpoints with multi-tenant support
  async getCallsWithFilters(statusFilter = null, salesRepFilter = null, uploadMethodFilter = null) {
    const params = new URLSearchParams();
    if (statusFilter) params.append('status_filter', statusFilter);
    if (salesRepFilter) params.append('sales_rep_filter', salesRepFilter);
    if (uploadMethodFilter) params.append('upload_method_filter', uploadMethodFilter);
    
    const queryString = params.toString();
    const endpoint = queryString ? `/calls?${queryString}` : '/calls';
    
    return this.request(endpoint);
  }

  // Admin endpoints
  async getAllCallsAdmin(clientIdFilter = null, statusFilter = null, salesRepFilter = null, uploadMethodFilter = null) {
    const params = new URLSearchParams();
    if (clientIdFilter) params.append('client_id_filter', clientIdFilter);
    if (statusFilter) params.append('status_filter', statusFilter);
    if (salesRepFilter) params.append('sales_rep_filter', salesRepFilter);
    if (uploadMethodFilter) params.append('upload_method_filter', uploadMethodFilter);
    
    const queryString = params.toString();
    const endpoint = queryString ? `/calls/admin/all-calls?${queryString}` : '/calls/admin/all-calls';
    
    return this.request(endpoint);
  }

  async getAdminOverviewStats() {
    return this.request('/calls/admin/stats/overview');
  }

  // Reports endpoints (Admin)
  async getRepPerformance(clientId) {
    return this.request(`/reports/client/${clientId}/rep-performance`);
  }
}

// Create and export a singleton instance
const apiService = new ApiService();
export default apiService;
