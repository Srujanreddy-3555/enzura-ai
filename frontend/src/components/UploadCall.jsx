import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import apiService from '../services/api';
import Sidebar from './Sidebar';
import UserHeader from './UserHeader';

const UploadCall = () => {
  const [activeItem, setActiveItem] = useState('Upload Call');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState({});
  const [uploadComplete, setUploadComplete] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState('');
  const [uploadedCalls, setUploadedCalls] = useState([]);
  const [supportedFormats, setSupportedFormats] = useState(null);
  const [uploadSteps, setUploadSteps] = useState({});
  const [currentStep, setCurrentStep] = useState('');
  const navigate = useNavigate();

  // Mobile navigation items (for mobile menu only)
  const navigationItems = [
    { name: 'Dashboard', path: '/dashboard' },
    { name: 'My Calls', path: '/mycalls' },
    { name: 'Upload Call', path: '/uploadcall' },
    { name: 'Leaderboard', path: '/leaderboard' }
  ];


  // Load supported formats on component mount
  useEffect(() => {
    const loadSupportedFormats = async () => {
      try {
        const formats = await apiService.getSupportedFormats();
        setSupportedFormats(formats);
      } catch (error) {
        console.error('Failed to load supported formats:', error);
      }
    };

    loadSupportedFormats();
  }, []);

  const handleFileSelect = (event) => {
    const files = Array.from(event.target.files);
    handleFiles(files);
  };

  const handleFiles = (files) => {
    const validFiles = [];
    const errors = [];

    files.forEach(file => {
      // Check file type using supported formats from API
      const allowedExtensions = supportedFormats 
        ? supportedFormats.supported_formats.map(f => f.extension)
        : ['.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac'];
      
      const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
      
      if (!allowedExtensions.includes(fileExtension)) {
        const formatList = allowedExtensions.join(', ');
        errors.push(`${file.name}: Invalid file type. Please select files with extensions: ${formatList}`);
        return;
      }
      
      // Check file size (max 100MB or from API)
      const maxSize = supportedFormats 
        ? supportedFormats.max_file_size_mb * 1024 * 1024
        : 100 * 1024 * 1024; // 100MB in bytes
      
      if (file.size > maxSize) {
        const maxSizeMB = Math.round(maxSize / (1024 * 1024));
        errors.push(`${file.name}: File size must be less than ${maxSizeMB}MB.`);
        return;
      }
      
      validFiles.push(file);
    });

    if (errors.length > 0) {
      setError(errors.join('\n'));
      return;
    }

    setError('');
    setSelectedFiles(prev => [...prev, ...validFiles]);
    setUploadComplete(false);
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const files = Array.from(e.dataTransfer.files);
      handleFiles(files);
    }
  };

  const handleUpload = async () => {
    if (selectedFiles.length === 0) {
      setError('Please select at least one file first');
      return;
    }

    setUploading(true);
    setUploadProgress({});
    setUploadComplete(false);
    setError('');
    setUploadedCalls([]);
    setUploadSteps({});
    setCurrentStep('Preparing files...');

    try {
      // Step 1: Validate files
      setCurrentStep('Validating files...');
      await new Promise(resolve => setTimeout(resolve, 500)); // Small delay for UX

      // Step 2: Upload to S3
      setCurrentStep('Uploading to cloud storage...');
      // Upload files (English only)
      const uploadResults = await apiService.uploadMultipleFiles(selectedFiles);
      
      // Step 3: Process results
      setCurrentStep('Processing upload results...');
      await new Promise(resolve => setTimeout(resolve, 300));

      let successfulUploads = [];
      let failedUploads = [];

      // Handle the response - it could be an array of successful uploads or an object with errors
      if (Array.isArray(uploadResults)) {
        // All uploads successful
        successfulUploads = uploadResults;
        setUploadedCalls(uploadResults);
        setUploadProgress(prev => {
          const newProgress = { ...prev };
          uploadResults.forEach(result => {
            newProgress[result.filename] = 100;
          });
          return newProgress;
        });
      } else if (uploadResults.successful_uploads) {
        // Some uploads successful, some failed
        successfulUploads = uploadResults.successful_uploads;
        failedUploads = uploadResults.errors || [];
        setUploadedCalls(uploadResults.successful_uploads);
        setUploadProgress(prev => {
          const newProgress = { ...prev };
          uploadResults.successful_uploads.forEach(result => {
            newProgress[result.filename] = 100;
          });
          return newProgress;
        });
      } else {
        throw new Error('Invalid response format from server');
      }

      // Step 4: Start transcription and analysis
      if (successfulUploads.length > 0) {
        setCurrentStep('Starting transcription and analysis...');
        await new Promise(resolve => setTimeout(resolve, 500));
        
        // Update steps for each successful upload
        const newSteps = {};
        successfulUploads.forEach(upload => {
          newSteps[upload.filename] = {
            uploaded: true,
            transcribing: true,
            analyzing: false,
            complete: false
          };
        });
        setUploadSteps(newSteps);
      }

      // Step 5: Show completion
      setCurrentStep('Upload complete! Processing in background...');
      setUploading(false);
      setUploadComplete(true);
      
      // Show errors for failed uploads
      if (failedUploads.length > 0) {
        const errorMessages = failedUploads.map(error => 
          `${error.filename}: ${error.error}`
        );
        setError(`Some files failed to upload:\n${errorMessages.join('\n')}`);
      }
      
      // Redirect after 3 seconds
      setTimeout(() => {
        navigate('/mycalls');
      }, 3000);

    } catch (error) {
      console.error('Upload failed:', error);
      setCurrentStep('Upload failed');
      setError(`Upload failed: ${error.message}`);
      setUploading(false);
    }
  };

  const handleReset = () => {
    setSelectedFiles([]);
    setUploading(false);
    setUploadProgress({});
    setUploadComplete(false);
    setError('');
    setUploadedCalls([]);
    setUploadSteps({});
    setCurrentStep('');
    // Reset file input
    const fileInput = document.getElementById('file-input');
    if (fileInput) {
      fileInput.value = '';
    }
  };

  const removeFile = (fileName) => {
    setSelectedFiles(prev => prev.filter(file => file.name !== fileName));
    setUploadProgress(prev => {
      const newProgress = { ...prev };
      delete newProgress[fileName];
      return newProgress;
    });
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Mobile Header */}
      <div className="lg:hidden bg-white shadow-sm border-b border-gray-200">
        <div className="flex items-center justify-between px-4 py-3">
          <h1 className="text-lg font-semibold text-gray-900">Upload Call</h1>
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
              <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
                {/* Page Header */}
                <div className="mb-8">
                  <h1 className="text-2xl font-bold text-gray-900">Upload Call</h1>
                  <p className="mt-1 text-sm text-gray-500">
                    Upload your call recordings for analysis and insights.
                  </p>
                </div>

                {/* Upload Form Card */}
                <div className="bg-white shadow-xl rounded-2xl p-8 border border-gray-100">
                  <div className="space-y-8">
                    {/* Header Section */}
                    <div className="text-center">
                      <div className="mx-auto flex items-center justify-center h-16 w-16 rounded-full bg-gradient-to-r from-indigo-500 to-purple-600 mb-4">
                        <svg className="h-8 w-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6H16a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                        </svg>
                      </div>
                      <h2 className="text-2xl font-bold text-gray-900 mb-2">Upload Call Recordings</h2>
                      <p className="text-gray-600">Drag and drop your audio files or click to browse</p>
                    </div>

                    {/* File Input Section */}
                    <div>
                      <div 
                        className={`relative flex justify-center px-8 pt-12 pb-12 border-2 border-dashed rounded-2xl transition-all duration-300 ${
                          dragActive 
                            ? 'border-indigo-400 bg-gradient-to-br from-indigo-50 to-purple-50 shadow-2xl shadow-indigo-200 scale-105' 
                            : 'border-gray-300 hover:border-indigo-300 hover:bg-gray-50'
                        }`}
                        onDragEnter={handleDrag}
                        onDragLeave={handleDrag}
                        onDragOver={handleDrag}
                        onDrop={handleDrop}
                      >
                        <div className="space-y-4 text-center">
                          <div className={`mx-auto h-20 w-20 rounded-full flex items-center justify-center transition-all duration-300 ${
                            dragActive 
                              ? 'bg-gradient-to-r from-indigo-500 to-purple-600 shadow-lg' 
                              : 'bg-gray-100'
                          }`}>
                            <svg className={`h-10 w-10 transition-colors duration-300 ${
                              dragActive ? 'text-white' : 'text-gray-400'
                            }`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6H16a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                            </svg>
                          </div>
                          
                          <div className="space-y-2">
                            <div className="flex items-center justify-center text-sm text-gray-600">
                              <label htmlFor="file-input" className="relative cursor-pointer bg-white rounded-lg font-semibold text-indigo-600 hover:text-indigo-700 focus-within:outline-none focus-within:ring-2 focus-within:ring-offset-2 focus-within:ring-indigo-500 px-4 py-2 border border-indigo-200 hover:border-indigo-300 transition-all duration-200">
                                <span>Choose Files</span>
                                <input
                                  id="file-input"
                                  name="file-input"
                                  type="file"
                                  accept={supportedFormats 
                                    ? supportedFormats.supported_formats.map(f => f.extension).join(',')
                                    : ".mp3,.wav,.m4a,.aac,.ogg,.flac"
                                  }
                                  className="sr-only"
                                  onChange={handleFileSelect}
                                  disabled={uploading}
                                  multiple
                                />
                              </label>
                              <span className="mx-3 text-gray-400">or</span>
                              <span className="text-gray-500">drag and drop</span>
                            </div>
                            <p className="text-sm text-gray-500">
                              Supports {supportedFormats 
                                ? supportedFormats.supported_formats.map(f => f.extension.toUpperCase().slice(1)).join(', ')
                                : 'MP3, WAV, M4A, AAC, OGG, FLAC'
                              } • Max {supportedFormats 
                                ? supportedFormats.max_file_size_mb
                                : 100
                              }MB per file
                            </p>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Error Display */}
                    {error && (
                      <div className="bg-gradient-to-r from-red-50 to-pink-50 border border-red-200 rounded-xl p-6 shadow-sm">
                        <div className="flex items-start">
                          <div className="flex-shrink-0">
                            <div className="h-8 w-8 rounded-full bg-red-100 flex items-center justify-center">
                              <svg className="h-5 w-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                              </svg>
                            </div>
                          </div>
                          <div className="ml-4">
                            <h3 className="text-sm font-semibold text-red-800">Upload Error</h3>
                            <p className="text-sm text-red-600 whitespace-pre-line mt-1">{error}</p>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Selected Files Display */}
                    {selectedFiles.length > 0 && (
                      <div className="space-y-4">
                        <div className="flex items-center justify-between">
                          <h3 className="text-lg font-semibold text-gray-900">Selected Files</h3>
                          <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-indigo-100 text-indigo-800">
                            {selectedFiles.length} file{selectedFiles.length > 1 ? 's' : ''}
                          </span>
                        </div>
                        
                        <div className="grid gap-3">
                          {selectedFiles.map((file, index) => (
                            <div key={index} className="bg-gradient-to-r from-gray-50 to-gray-100 rounded-xl p-4 border border-gray-200 hover:shadow-md transition-all duration-200">
                              <div className="flex items-center justify-between">
                                <div className="flex items-center space-x-4">
                                  <div className="flex-shrink-0">
                                    <div className="h-12 w-12 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
                                      <svg className="h-6 w-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
                                      </svg>
                                    </div>
                                  </div>
                                  <div className="flex-1 min-w-0">
                                    <p className="text-sm font-semibold text-gray-900 truncate">{file.name}</p>
                                    <div className="flex items-center space-x-4 mt-1">
                                      <p className="text-sm text-gray-500">
                                        {(file.size / (1024 * 1024)).toFixed(2)} MB
                                      </p>
                                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                                        Ready
                                      </span>
                                    </div>
                                  </div>
                                </div>
                                
                                {!uploading && !uploadComplete && (
                                  <button
                                    onClick={() => removeFile(file.name)}
                                    className="flex-shrink-0 p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-all duration-200"
                                    title="Remove file"
                                  >
                                    <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                                    </svg>
                                  </button>
                                )}
                              </div>
                              
                              {/* Progress Bar for each file */}
                              {uploading && uploadProgress[file.name] !== undefined && (
                                <div className="mt-4">
                                  <div className="flex justify-between text-sm mb-2">
                                    <span className="text-gray-600 font-medium">Uploading...</span>
                                    <span className="text-gray-600 font-semibold">{Math.round(uploadProgress[file.name] || 0)}%</span>
                                  </div>
                                  <div className="w-full bg-gray-200 rounded-full h-2.5 overflow-hidden">
                                    <div 
                                      className="bg-gradient-to-r from-indigo-500 to-purple-600 h-2.5 rounded-full transition-all duration-500 ease-out shadow-sm"
                                      style={{ width: `${uploadProgress[file.name] || 0}%` }}
                                    ></div>
                                  </div>
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Upload Progress with Steps */}
                    {uploading && (
                      <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-xl p-6 shadow-sm">
                        <div className="flex items-center mb-6">
                          <div className="flex-shrink-0">
                            <div className="h-10 w-10 rounded-full bg-blue-100 flex items-center justify-center">
                              <svg className="animate-spin h-6 w-6 text-blue-500" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                              </svg>
                            </div>
                          </div>
                          <div className="ml-4">
                            <h3 className="text-lg font-semibold text-blue-800">Processing Your Call</h3>
                            <p className="text-sm text-blue-600 mt-1">{currentStep}</p>
                          </div>
                        </div>

                        {/* Upload Pipeline Steps */}
                        <div className="space-y-4">
                          <div className="flex items-center space-x-4">
                            <div className="flex-shrink-0">
                              <div className="h-8 w-8 rounded-full bg-green-100 flex items-center justify-center">
                                <svg className="h-5 w-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                                </svg>
                              </div>
                            </div>
                            <div className="flex-1">
                              <p className="text-sm font-medium text-gray-900">File Validation</p>
                              <p className="text-xs text-gray-500">Checking file format and size</p>
                            </div>
                          </div>

                          <div className="flex items-center space-x-4">
                            <div className="flex-shrink-0">
                              <div className={`h-8 w-8 rounded-full flex items-center justify-center ${
                                currentStep.includes('Uploading to cloud') ? 'bg-blue-100' : 'bg-gray-100'
                              }`}>
                                {currentStep.includes('Uploading to cloud') ? (
                                  <svg className="animate-spin h-5 w-5 text-blue-500" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                  </svg>
                                ) : currentStep.includes('Upload complete') ? (
                                  <svg className="h-5 w-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                                  </svg>
                                ) : (
                                  <div className="h-3 w-3 rounded-full bg-gray-300"></div>
                                )}
                              </div>
                            </div>
                            <div className="flex-1">
                              <p className="text-sm font-medium text-gray-900">S3 Storage Upload</p>
                              <p className="text-xs text-gray-500">Securely storing your audio file</p>
                            </div>
                          </div>

                          <div className="flex items-center space-x-4">
                            <div className="flex-shrink-0">
                              <div className={`h-8 w-8 rounded-full flex items-center justify-center ${
                                currentStep.includes('Starting transcription') ? 'bg-blue-100' : 'bg-gray-100'
                              }`}>
                                {currentStep.includes('Starting transcription') ? (
                                  <svg className="animate-spin h-5 w-5 text-blue-500" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                  </svg>
                                ) : currentStep.includes('Upload complete') ? (
                                  <svg className="h-5 w-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                                  </svg>
                                ) : (
                                  <div className="h-3 w-3 rounded-full bg-gray-300"></div>
                                )}
                              </div>
                            </div>
                            <div className="flex-1">
                              <p className="text-sm font-medium text-gray-900">Transcription & Analysis</p>
                              <p className="text-xs text-gray-500">Converting speech to text and extracting insights</p>
                            </div>
                          </div>

                          <div className="flex items-center space-x-4">
                            <div className="flex-shrink-0">
                              <div className={`h-8 w-8 rounded-full flex items-center justify-center ${
                                currentStep.includes('Processing in background') ? 'bg-blue-100' : 'bg-gray-100'
                              }`}>
                                {currentStep.includes('Processing in background') ? (
                                  <svg className="animate-spin h-5 w-5 text-blue-500" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                  </svg>
                                ) : currentStep.includes('Upload complete') ? (
                                  <svg className="h-5 w-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                                  </svg>
                                ) : (
                                  <div className="h-3 w-3 rounded-full bg-gray-300"></div>
                                )}
                              </div>
                            </div>
                            <div className="flex-1">
                              <p className="text-sm font-medium text-gray-900">Background Processing</p>
                              <p className="text-xs text-gray-500">Generating detailed analytics and scores</p>
                            </div>
                          </div>
                        </div>

                        {/* Progress Bar */}
                        <div className="mt-6">
                          <div className="flex justify-between text-sm mb-2">
                            <span className="text-gray-600 font-medium">Overall Progress</span>
                            <span className="text-gray-600 font-semibold">
                              {currentStep.includes('Upload complete') ? '100%' : 
                               currentStep.includes('Starting transcription') ? '75%' :
                               currentStep.includes('Uploading to cloud') ? '50%' : '25%'}
                            </span>
                          </div>
                          <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
                            <div 
                              className="bg-gradient-to-r from-blue-500 to-indigo-600 h-3 rounded-full transition-all duration-1000 ease-out shadow-sm"
                              style={{ 
                                width: currentStep.includes('Upload complete') ? '100%' : 
                                       currentStep.includes('Starting transcription') ? '75%' :
                                       currentStep.includes('Uploading to cloud') ? '50%' : '25%'
                              }}
                            ></div>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Upload Complete */}
                    {uploadComplete && (
                      <div className="bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 rounded-xl p-6 shadow-sm">
                        <div className="flex items-center">
                          <div className="flex-shrink-0">
                            <div className="h-10 w-10 rounded-full bg-green-100 flex items-center justify-center">
                              <svg className="h-6 w-6 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                              </svg>
                            </div>
                          </div>
                          <div className="ml-4">
                            <h3 className="text-lg font-semibold text-green-800">Upload Successful!</h3>
                            <p className="text-sm text-green-600 mt-1">
                              Your calls have been uploaded to S3 and are being processed. Transcription and analysis will continue in the background. Redirecting to My Calls...
                            </p>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Action Buttons */}
                    <div className="flex flex-col sm:flex-row justify-between items-center space-y-4 sm:space-y-0 sm:space-x-4 pt-6 border-t border-gray-200">
                      <Link
                        to="/mycalls"
                        className="inline-flex items-center px-6 py-3 border border-gray-300 text-sm font-semibold rounded-xl text-gray-700 bg-white hover:bg-gray-50 hover:border-gray-400 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition-all duration-200 shadow-sm hover:shadow-md"
                      >
                        <svg className="-ml-1 mr-2 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                        </svg>
                        Back to My Calls
                      </Link>
                      
                      <div className="flex space-x-3">
                        {uploadComplete && (
                          <button
                            onClick={handleReset}
                            className="inline-flex items-center px-6 py-3 border border-gray-300 text-sm font-semibold rounded-xl text-gray-700 bg-white hover:bg-gray-50 hover:border-gray-400 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition-all duration-200 shadow-sm hover:shadow-md"
                          >
                            <svg className="-ml-1 mr-2 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                            </svg>
                            Upload Another
                          </button>
                        )}
                        
                        <button
                          onClick={handleUpload}
                          disabled={selectedFiles.length === 0 || uploading}
                          className="inline-flex items-center px-8 py-3 border border-transparent text-sm font-semibold rounded-xl text-white bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 shadow-lg hover:shadow-xl transform hover:scale-105 disabled:transform-none"
                        >
                          {uploading ? (
                            <>
                              <svg className="animate-spin -ml-1 mr-2 h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                              </svg>
                              Uploading...
                            </>
                          ) : (
                            <>
                              <svg className="-ml-1 mr-2 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6H16a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                              </svg>
                              Upload {selectedFiles.length > 0 ? `${selectedFiles.length} File${selectedFiles.length > 1 ? 's' : ''}` : 'Call'}
                            </>
                          )}
                        </button>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Help Section */}
                <div className="mt-8 bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-2xl p-8 shadow-sm">
                  <div className="flex items-start space-x-4">
                    <div className="flex-shrink-0">
                      <div className="h-12 w-12 rounded-xl bg-blue-100 flex items-center justify-center">
                        <svg className="h-6 w-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                      </div>
                    </div>
                    <div className="flex-1">
                      <h3 className="text-xl font-semibold text-blue-900 mb-4">Upload Guidelines</h3>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="space-y-3">
                          <div className="flex items-center space-x-3">
                            <div className="h-2 w-2 rounded-full bg-blue-500"></div>
                            <span className="text-sm font-medium text-blue-800">
                              Supported formats: {supportedFormats 
                                ? supportedFormats.supported_formats.map(f => f.extension.toUpperCase().slice(1)).join(', ')
                                : 'MP3, WAV, M4A, AAC, OGG, FLAC'
                              }
                            </span>
                          </div>
                          <div className="flex items-center space-x-3">
                            <div className="h-2 w-2 rounded-full bg-blue-500"></div>
                            <span className="text-sm font-medium text-blue-800">
                              Maximum file size: {supportedFormats 
                                ? supportedFormats.max_file_size_mb
                                : 100
                              }MB per file
                            </span>
                          </div>
                          <div className="flex items-center space-x-3">
                            <div className="h-2 w-2 rounded-full bg-blue-500"></div>
                            <span className="text-sm font-medium text-blue-800">
                              Maximum {supportedFormats 
                                ? supportedFormats.max_files_per_upload
                                : 10
                              } files can be uploaded simultaneously
                            </span>
                          </div>
                        </div>
                        <div className="space-y-3">
                          <div className="flex items-center space-x-3">
                            <div className="h-2 w-2 rounded-full bg-blue-500"></div>
                            <span className="text-sm font-medium text-blue-800">Clear audio quality recommended for best analysis</span>
                          </div>
                          <div className="flex items-center space-x-3">
                            <div className="h-2 w-2 rounded-full bg-blue-500"></div>
                            <span className="text-sm font-medium text-blue-800">Processing typically takes 2-3 minutes per file</span>
                          </div>
                        </div>
                      </div>
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

export default UploadCall;
