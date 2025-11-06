import React, { useEffect, useState } from 'react';

const SuccessToast = ({ message, username, onClose, duration = 3000 }) => {
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

  return (
    <div
      className={`fixed bottom-4 left-4 z-50 transform transition-all duration-300 ease-out ${
        isVisible ? 'translate-x-0 opacity-100' : '-translate-x-full opacity-0'
      }`}
      style={{ maxWidth: '380px', width: 'auto' }}
    >
      <div className="bg-white rounded-lg shadow-xl border border-green-200 overflow-hidden">
        {/* Progress Bar */}
        <div className="h-1 bg-gray-100">
          <div
            className="h-full bg-green-500 transition-all duration-50 ease-linear"
            style={{ width: `${progress}%` }}
          />
        </div>

        {/* Content */}
        <div className="flex items-center p-3.5">
          {/* Green Check Icon */}
          <div className="flex-shrink-0">
            <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center">
              <svg
                className="w-5 h-5 text-green-600"
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
            </div>
          </div>

          {/* Message */}
          <div className="ml-3 flex-1">
            <p className="text-sm">
              <span className="text-gray-500 font-normal">{message || 'Welcome back'}</span>
              {username && (
                <span className="text-black font-bold">, {username}</span>
              )}
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

export default SuccessToast;

