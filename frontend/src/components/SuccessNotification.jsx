import React, { useEffect, useState } from 'react';

const SuccessNotification = ({ message, onClose, duration = 3000, type = 'success' }) => {
  const [progress, setProgress] = useState(100);
  const [isVisible, setIsVisible] = useState(true);

  useEffect(() => {
    // Start progress bar animation
    const progressInterval = setInterval(() => {
      setProgress((prev) => {
        if (prev <= 0) {
          clearInterval(progressInterval);
          return 0;
        }
        return prev - (100 / (duration / 50)); // Decrease every 50ms
      });
    }, 50);

    // Auto-hide after duration
    const hideTimeout = setTimeout(() => {
      setIsVisible(false);
      setTimeout(() => {
        onClose();
      }, 300); // Wait for slide-out animation
    }, duration);

    return () => {
      clearInterval(progressInterval);
      clearTimeout(hideTimeout);
    };
  }, [duration, onClose]);

  const handleClose = () => {
    setIsVisible(false);
    setTimeout(() => {
      onClose();
    }, 300); // Wait for slide-out animation
  };

  if (!isVisible && progress === 0) {
    return null;
  }

  const typeStyles = {
    success: {
      bg: 'bg-green-100',
      iconBg: 'bg-green-100',
      iconColor: 'text-green-600',
      borderColor: 'border-green-200',
      progressColor: 'bg-green-500',
      textColor: 'text-green-800'
    },
    info: {
      bg: 'bg-blue-100',
      iconBg: 'bg-blue-100',
      iconColor: 'text-blue-600',
      borderColor: 'border-blue-200',
      progressColor: 'bg-blue-500',
      textColor: 'text-blue-800'
    }
  };

  const styles = typeStyles[type] || typeStyles.success;

  return (
    <div
      className={`fixed top-4 right-4 z-50 transform transition-all duration-300 ease-out ${
        isVisible ? 'translate-x-0 opacity-100' : 'translate-x-full opacity-0'
      }`}
      style={{ maxWidth: '400px', width: 'auto' }}
    >
      <div className={`bg-white rounded-lg shadow-xl border ${styles.borderColor} overflow-hidden`}>
        {/* Progress Bar */}
        <div className="h-1 bg-gray-100">
          <div
            className={`h-full ${styles.progressColor} transition-all duration-50 ease-linear`}
            style={{ width: `${progress}%` }}
          />
        </div>

        {/* Content */}
        <div className="flex items-center p-4">
          {/* Icon */}
          <div className="flex-shrink-0">
            <div className={`w-10 h-10 rounded-full ${styles.iconBg} flex items-center justify-center`}>
              {type === 'success' ? (
                <svg
                  className={`w-5 h-5 ${styles.iconColor}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={3}
                    d="M5 13l4 4L19 7"
                  />
                </svg>
              ) : (
                <svg
                  className={`w-5 h-5 ${styles.iconColor}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
              )}
            </div>
          </div>

          {/* Message */}
          <div className="ml-3 flex-1">
            <p className={`text-sm font-medium ${styles.textColor}`}>
              {message}
            </p>
          </div>

          {/* Close Button */}
          <button
            onClick={handleClose}
            className="ml-3 flex-shrink-0 text-gray-400 hover:text-gray-600 focus:outline-none transition-colors"
            aria-label="Close"
          >
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
};

export default SuccessNotification;

