import React, { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import ErrorBoundary from './components/ErrorBoundary';
import './i18n/config'; // Initialize i18n

// OPTIMIZED: Lazy load all components for code splitting (smaller initial bundle!)
const LandingPage = lazy(() => import('./components/LandingPage'));
const Login = lazy(() => import('./components/Login'));
const Dashboard = lazy(() => import('./components/Dashboard'));
const Leaderboard = lazy(() => import('./components/Leaderboard'));
const MyCalls = lazy(() => import('./components/MyCalls'));
const CallDetail = lazy(() => import('./components/CallDetail'));
const UploadCall = lazy(() => import('./components/UploadCall'));
const ClientManagement = lazy(() => import('./components/ClientManagement'));
const S3MonitoringDashboard = lazy(() => import('./components/S3MonitoringDashboard'));
const AdminReports = lazy(() => import('./components/AdminReports'));

// Optimized loading component with skeleton
const LoadingSkeleton = () => (
  <div className="min-h-screen bg-gray-50 flex items-center justify-center">
    <div className="text-center">
      <div className="animate-pulse space-y-4">
        <div className="h-12 w-12 bg-gray-300 rounded-full mx-auto"></div>
        <div className="h-4 w-32 bg-gray-300 rounded mx-auto"></div>
        <div className="h-4 w-24 bg-gray-300 rounded mx-auto"></div>
      </div>
    </div>
  </div>
);

// OPTIMIZED: Memoized Protected Route to prevent unnecessary re-renders
const ProtectedRoute = React.memo(({ children }) => {
  const { isAuthenticated, loading } = useAuth();
  
  if (loading) {
    return <LoadingSkeleton />;
  }
  
  return isAuthenticated ? children : <Navigate to="/login" replace />;
});
ProtectedRoute.displayName = 'ProtectedRoute';

// OPTIMIZED: Memoized Admin Protected Route
const AdminProtectedRoute = React.memo(({ children }) => {
  const { isAuthenticated, loading, user } = useAuth();
  
  if (loading) {
    return <LoadingSkeleton />;
  }
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  
  if (user?.role?.toLowerCase() !== 'admin') {
    return <Navigate to="/dashboard" replace />;
  }
  
  return children;
});
AdminProtectedRoute.displayName = 'AdminProtectedRoute';

function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <Router>
          <div className="App bg-gray-100 min-h-screen">
            <Suspense fallback={<LoadingSkeleton />}>
              <Routes>
              <Route path="/" element={<LandingPage />} />
              <Route path="/login" element={<Login />} />
              {/* Signup disabled - admin creates users */}
              <Route path="/dashboard" element={
                <ProtectedRoute>
                  <Dashboard />
                </ProtectedRoute>
              } />
              <Route path="/leaderboard" element={
                <ProtectedRoute>
                  <Leaderboard />
                </ProtectedRoute>
              } />
              <Route path="/mycalls" element={
                <ProtectedRoute>
                  <MyCalls />
                </ProtectedRoute>
              } />
              <Route path="/calldetail/:id" element={
                <ProtectedRoute>
                  <CallDetail />
                </ProtectedRoute>
              } />
              <Route path="/uploadcall" element={
                <ProtectedRoute>
                  <UploadCall />
                </ProtectedRoute>
              } />
              {/* Admin-only routes */}
              <Route path="/client-management" element={
                <AdminProtectedRoute>
                  <ClientManagement />
                </AdminProtectedRoute>
              } />
              <Route path="/s3-monitoring" element={
                <AdminProtectedRoute>
                  <S3MonitoringDashboard />
                </AdminProtectedRoute>
              } />
              <Route path="/reports" element={
                <AdminProtectedRoute>
                  <AdminReports />
                </AdminProtectedRoute>
              } />
            </Routes>
          </Suspense>
        </div>
      </Router>
    </AuthProvider>
    </ErrorBoundary>
  );
}

export default App;


