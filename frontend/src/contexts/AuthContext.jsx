import React, { createContext, useContext, useState, useEffect, useMemo, useCallback } from 'react';
import apiService from '../services/api';

const AuthContext = createContext();

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  // OPTIMIZED: Check if user is logged in on app start (only once)
  // Added timeout to prevent hanging
  useEffect(() => {
    let mounted = true;
    let timeoutId = null;
    
    const checkAuth = async () => {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        if (mounted) {
          setLoading(false);
        }
        return;
      }
      
      try {
        // OPTIMIZED: Add timeout to prevent hanging (3 seconds max - faster!)
        const timeoutPromise = new Promise((_, reject) => {
          timeoutId = setTimeout(() => reject(new Error('Auth check timeout')), 3000);
        });
        
        // OPTIMIZED: Clear cache before auth check to ensure fresh data
        if (apiService.cache) {
          apiService.cache.clear();
        }
        
        const userDataPromise = apiService.getCurrentUser();
        
        const userData = await Promise.race([userDataPromise, timeoutPromise]);
        
        if (mounted) {
          setUser(userData);
          setIsAuthenticated(true);
        }
      } catch (error) {
        console.error('Auth check failed:', error);
        // Clear invalid token and cache immediately
        apiService.clearToken();
        localStorage.removeItem('auth_token');
        // Clear all cached data
        if (apiService.cache) {
          apiService.cache.clear();
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
        if (timeoutId) {
          clearTimeout(timeoutId);
        }
      }
    };

    checkAuth();
    
    return () => {
      mounted = false;
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    };
  }, []);

  // OPTIMIZED: Memoized login function to prevent unnecessary re-renders
  const login = useCallback(async (email, password) => {
    try {
      const response = await apiService.login(email, password);
      setUser(response.user);
      setIsAuthenticated(true);
      return response;
    } catch (error) {
      throw error;
    }
  }, []);

  const register = useCallback(async (userData) => {
    try {
      const response = await apiService.register(userData);
      return response;
    } catch (error) {
      throw error;
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiService.logout();
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      // OPTIMIZED: Clear ALL cached data on logout for clean slate
      setUser(null);
      setIsAuthenticated(false);
      apiService.clearToken();
      
      // Clear all localStorage cache
      try {
        localStorage.removeItem('auth_token');
        localStorage.removeItem('user_data');
        localStorage.removeItem('dashboard_cache');
        localStorage.removeItem('calls_cache');
        // Clear any other cached data
        Object.keys(localStorage).forEach(key => {
          if (key.startsWith('cache_') || key.startsWith('app_')) {
            localStorage.removeItem(key);
          }
        });
      } catch (e) {
        console.warn('Error clearing localStorage:', e);
      }
    }
  }, []);

  // OPTIMIZED: Memoized context value to prevent unnecessary re-renders
  const value = useMemo(() => ({
    user,
    isAuthenticated,
    loading,
    login,
    register,
    logout,
  }), [user, isAuthenticated, loading, login, register, logout]);

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};
