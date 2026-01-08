import React from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import LanguageSelector from './LanguageSelector';

const UserHeader = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { t } = useTranslation();

  const handleLogout = async () => {
    try {
      await logout();
      navigate('/login');
    } catch (error) {
      console.error('Logout failed:', error);
      navigate('/login');
    }
  };

  // Get user role display name
  const getRoleDisplay = (role) => {
    if (!role) return t('common.user');
    const roleLower = role.toLowerCase();
    if (roleLower === 'admin') return t('common.admin');
    if (roleLower === 'client') return t('common.client');
    if (roleLower === 'rep') return t('common.rep');
    return role.charAt(0).toUpperCase() + role.slice(1).toLowerCase();
  };

  if (!user) return null;

  return (
    <div className="fixed top-4 right-4 z-50 flex items-center space-x-3">
      {/* Language Selector */}
      <LanguageSelector />

      {/* User Role Button - Gradient */}
      <div className="bg-gradient-to-r from-purple-600 to-blue-600 rounded-lg px-4 py-2 flex items-center space-x-2 shadow-lg hover:shadow-xl transition-all duration-200">
        <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
        </svg>
        <span className="text-white font-medium text-sm">{getRoleDisplay(user.role)}</span>
      </div>

      {/* Logout Button - Red */}
      <button
        onClick={handleLogout}
        className="p-2 rounded-lg bg-red-50 hover:bg-red-100 border border-red-200 transition-all duration-200 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
        title={t('common.logout')}
      >
        <svg className="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
        </svg>
      </button>
    </div>
  );
};

export default UserHeader;

