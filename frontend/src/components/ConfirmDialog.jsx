import React from 'react';

const ConfirmDialog = ({ isOpen, onClose, onConfirm, title, message, confirmText = 'Delete', cancelText = 'Cancel', type = 'danger' }) => {
  if (!isOpen) return null;

  const typeStyles = {
    danger: {
      iconBg: 'bg-red-100',
      iconColor: 'text-red-600',
      iconSvg: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
      ),
      buttonBg: 'bg-red-600 hover:bg-red-700 focus:ring-red-500',
      borderColor: 'border-red-200'
    },
    warning: {
      iconBg: 'bg-yellow-100',
      iconColor: 'text-yellow-600',
      iconSvg: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
      ),
      buttonBg: 'bg-yellow-600 hover:bg-yellow-700 focus:ring-yellow-500',
      borderColor: 'border-yellow-200'
    },
    info: {
      iconBg: 'bg-blue-100',
      iconColor: 'text-blue-600',
      iconSvg: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
      buttonBg: 'bg-blue-600 hover:bg-blue-700 focus:ring-blue-500',
      borderColor: 'border-blue-200'
    }
  };

  const styles = typeStyles[type] || typeStyles.danger;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/50 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />
      
      {/* Modal Container */}
      <div className="flex min-h-screen items-center justify-center p-4">
        <div className="relative bg-white rounded-xl shadow-2xl max-w-sm w-full transform transition-all">
          {/* Animation wrapper */}
          <div className="px-5 py-5">
            {/* Icon and Title in one row */}
            <div className="flex items-start gap-3 mb-3">
              <div className={`${styles.iconBg} ${styles.iconColor} rounded-full p-2.5 flex-shrink-0`}>
                {styles.iconSvg}
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-bold text-gray-900 mb-2">
                  {title || 'Confirm Action'}
                </h3>
                {/* Message */}
                <p className="text-sm text-gray-600 leading-relaxed">
                  {message || 'Are you sure you want to proceed?'}
                </p>
              </div>
            </div>

            {/* Buttons */}
            <div className="flex items-center justify-end gap-3 mt-5 pt-4 border-t border-gray-100">
              <button
                onClick={onClose}
                className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 text-sm font-medium rounded-lg transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-gray-300 focus:ring-offset-1"
              >
                {cancelText}
              </button>
              <button
                onClick={() => {
                  onConfirm();
                  onClose();
                }}
                className={`px-4 py-2 ${styles.buttonBg} text-white text-sm font-medium rounded-lg transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-1 shadow-sm hover:shadow`}
              >
                {confirmText}
              </button>
            </div>
          </div>

          {/* Decorative border */}
          <div className={`absolute top-0 left-0 right-0 h-1 ${styles.borderColor.replace('border-', 'bg-').replace('-200', '-500')} rounded-t-xl`} />
        </div>
      </div>
    </div>
  );
};

export default ConfirmDialog;

