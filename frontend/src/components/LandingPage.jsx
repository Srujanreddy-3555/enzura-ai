import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import LanguageSelector from './LanguageSelector';

const LandingPage = () => {
  const [isVisible, setIsVisible] = useState({});
  const observerRef = useRef(null);

  useEffect(() => {
    // Intersection Observer for scroll animations
    observerRef.current = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setIsVisible((prev) => ({
              ...prev,
              [entry.target.id]: true,
            }));
          }
        });
      },
      { threshold: 0.1 }
    );

    const elements = document.querySelectorAll('[data-animate]');
    elements.forEach((el) => observerRef.current.observe(el));

    return () => {
      if (observerRef.current) {
        elements.forEach((el) => observerRef.current.unobserve(el));
      }
    };
  }, []);

  return (
    <div className="bg-white overflow-hidden">
      {/* Navigation Bar */}
      <nav className="fixed top-0 w-full z-50 bg-white/80 backdrop-blur-lg border-b border-gray-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <div className="text-2xl font-bold bg-gradient-to-r from-purple-600 to-blue-600 bg-clip-text text-transparent">
                ENZURA
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <LanguageSelector />
              <Link
                to="/login"
                className="px-6 py-2 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-lg font-semibold hover:from-purple-700 hover:to-blue-700 transition-all duration-200 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5"
              >
                Sign In
              </Link>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative min-h-screen flex items-center justify-center pt-16 bg-gradient-to-br from-purple-50 via-blue-50 to-indigo-100 overflow-hidden">
        {/* Animated Background Elements */}
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute top-20 left-10 w-72 h-72 bg-purple-300 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-blob"></div>
          <div className="absolute top-40 right-10 w-72 h-72 bg-blue-300 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-blob animation-delay-2000"></div>
          <div className="absolute -bottom-8 left-1/2 w-72 h-72 bg-indigo-300 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-blob animation-delay-4000"></div>
        </div>

        <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20 text-center">
          <div
            id="hero"
            data-animate
            className={`transition-all duration-1000 ${
              isVisible.hero ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'
            }`}
          >
            <h1 className="text-5xl md:text-7xl font-bold mb-6 bg-gradient-to-r from-purple-600 via-blue-600 to-indigo-600 bg-clip-text text-transparent leading-normal pb-2">
              Transform Your Sales Calls
              <br />
              Into Winning Strategies
            </h1>
            <p className="text-xl md:text-2xl text-gray-600 mb-8 max-w-3xl mx-auto">
              Enzura AI analyzes your sales calls, extracts actionable insights, and helps your team
              deliver consistent, high-performing conversations that close deals.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
              <Link
                to="/login"
                className="px-8 py-4 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-xl font-semibold text-lg hover:from-purple-700 hover:to-blue-700 transition-all duration-200 shadow-xl hover:shadow-2xl transform hover:-translate-y-1"
              >
                Get Started Free
              </Link>
              <button
                onClick={() => {
                  const featuresSection = document.getElementById('features');
                  featuresSection?.scrollIntoView({ behavior: 'smooth' });
                }}
                className="px-8 py-4 bg-white text-gray-700 rounded-xl font-semibold text-lg border-2 border-gray-300 hover:border-purple-500 hover:text-purple-600 transition-all duration-200 shadow-lg hover:shadow-xl"
              >
                Learn More
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="py-16 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
            {[
              { number: '1K+', label: 'Calls Analyzed' },
              { number: '95%', label: 'Accuracy Rate' },
              { number: 'Real-time', label: 'Analysis Speed' },
              { number: '24/7', label: 'Automated Processing' },
            ].map((stat, index) => (
              <div
                key={index}
                id={`stat-${index}`}
                data-animate
                className={`text-center transition-all duration-1000 delay-${index * 100} ${
                  isVisible[`stat-${index}`] ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'
                }`}
              >
                <div className="text-4xl md:text-5xl font-bold bg-gradient-to-r from-purple-600 to-blue-600 bg-clip-text text-transparent mb-2">
                  {stat.number}
                </div>
                <div className="text-gray-600 font-medium">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-20 bg-gradient-to-b from-white to-purple-50/30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div
            id="features-header"
            data-animate
            className={`text-center mb-16 transition-all duration-1000 ${
              isVisible['features-header'] ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'
            }`}
          >
            <h2 className="text-4xl md:text-5xl font-bold mb-4 bg-gradient-to-r from-purple-600 to-blue-600 bg-clip-text text-transparent">
              Powerful Features for Modern Sales Teams
            </h2>
            <p className="text-xl text-gray-600 max-w-3xl mx-auto">
              Everything you need to analyze, improve, and scale your sales conversations
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            {[
              {
                icon: (
                  <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
                  </svg>
                ),
                title: 'AI Call Analysis',
                description: 'Automatically transcribe and analyze sales calls with advanced AI. Extract key insights, sentiment, and actionable feedback.',
              },
              {
                icon: (
                  <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                ),
                title: 'Smart Quality Scoring',
                description: 'Get instant quality scores for every call based on your methodology. Track performance trends and identify improvement areas.',
              },
              {
                icon: (
                  <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                  </svg>
                ),
                title: 'Performance Leaderboard',
                description: 'Gamify sales performance with real-time leaderboards. Motivate your team and recognize top performers.',
              },
              {
                icon: (
                  <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                ),
                title: 'Automated S3 Processing',
                description: 'Seamlessly integrate with AWS S3. Automatically process uploaded calls in real-time with zero manual intervention.',
              },
              {
                icon: (
                  <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                ),
                title: 'Detailed Insights & Reports',
                description: 'Comprehensive call insights including sentiment analysis, key topics, and conversation flow. Export reports for coaching sessions.',
              },
              {
                icon: (
                  <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
                  </svg>
                ),
                title: 'Multi-Tenant Architecture',
                description: 'Manage multiple clients, sales teams, and reps from a single platform. Perfect for agencies and enterprises.',
              },
            ].map((feature, index) => (
              <div
                key={index}
                id={`feature-${index}`}
                data-animate
                className={`bg-white rounded-2xl p-8 shadow-lg hover:shadow-2xl transition-all duration-300 transform hover:-translate-y-2 ${
                  isVisible[`feature-${index}`] ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'
                }`}
              >
                <div className="w-16 h-16 bg-gradient-to-r from-purple-100 to-blue-100 rounded-xl flex items-center justify-center text-purple-600 mb-4">
                  {feature.icon}
                </div>
                <h3 className="text-xl font-bold text-gray-900 mb-3">{feature.title}</h3>
                <p className="text-gray-600 leading-relaxed">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Use Cases Section */}
      <section className="py-20 bg-gradient-to-b from-purple-50/30 to-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div
            id="usecases-header"
            data-animate
            className={`text-center mb-16 transition-all duration-1000 ${
              isVisible['usecases-header'] ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'
            }`}
          >
            <h2 className="text-4xl md:text-5xl font-bold mb-4 bg-gradient-to-r from-purple-600 to-blue-600 bg-clip-text text-transparent leading-normal pb-2">
              Perfect For Every Sales Scenario
            </h2>
            <p className="text-xl text-gray-600 max-w-3xl mx-auto">
              Whether you're training new reps or scaling your team, Enzura AI adapts to your needs
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-8">
            {[
              {
                title: 'Sales Rep Training & Onboarding',
                description: 'Accelerate new hire ramp time with instant feedback on call quality. Help reps learn from every conversation.',
                icon: '🎯',
              },
              {
                title: 'Performance Coaching',
                description: 'Identify skill gaps and provide personalized coaching recommendations based on actual call performance data.',
                icon: '📈',
              },
              {
                title: 'Quality Assurance',
                description: 'Ensure consistent messaging across all sales conversations. Track adherence to your sales methodology.',
                icon: '✅',
              },
              {
                title: 'Team Competition & Motivation',
                description: 'Drive engagement with leaderboards and performance metrics. Turn improvement into a competitive advantage.',
                icon: '🏆',
              },
              {
                title: 'Multi-Client Management',
                description: 'Perfect for agencies managing multiple clients. Separate data, teams, and insights for each client.',
                icon: '🏢',
              },
              {
                title: 'Automated Call Processing',
                description: 'Set it and forget it. Automatically process calls from S3 buckets with real-time transcription and analysis.',
                icon: '⚡',
              },
            ].map((useCase, index) => (
              <div
                key={index}
                id={`usecase-${index}`}
                data-animate
                className={`bg-white rounded-2xl p-8 shadow-lg hover:shadow-xl transition-all duration-300 border-l-4 border-purple-500 ${
                  isVisible[`usecase-${index}`] ? 'opacity-100 translate-x-0' : 'opacity-0 -translate-x-10'
                }`}
              >
                <div className="flex items-start space-x-4">
                  <div className="text-4xl">{useCase.icon}</div>
                  <div>
                    <h3 className="text-xl font-bold text-gray-900 mb-2">{useCase.title}</h3>
                    <p className="text-gray-600 leading-relaxed">{useCase.description}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Benefits Section */}
      <section className="py-20 bg-gradient-to-br from-purple-600 via-blue-600 to-indigo-700 text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div
            id="benefits-header"
            data-animate
            className={`text-center mb-16 transition-all duration-1000 ${
              isVisible['benefits-header'] ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'
            }`}
          >
            <h2 className="text-4xl md:text-5xl font-bold mb-4">Why Teams Choose Enzura AI</h2>
            <p className="text-xl text-purple-100 max-w-3xl mx-auto">
              Join forward-thinking sales teams that are transforming their performance
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {[
              {
                title: 'Reduce Ramp Time',
                description: 'Get new hires productive 50% faster with instant feedback and personalized coaching.',
                stat: '50% Faster',
              },
              {
                title: 'Increase Win Rates',
                description: 'Improve call quality consistently across your team and close more deals.',
                stat: '30% More Wins',
              },
              {
                title: 'Scale Efficiently',
                description: 'Coach entire teams without scaling your coaching resources. AI does the heavy lifting.',
                stat: '10x Efficiency',
              },
            ].map((benefit, index) => (
              <div
                key={index}
                id={`benefit-${index}`}
                data-animate
                className={`bg-white/10 backdrop-blur-lg rounded-2xl p-8 border border-white/20 hover:bg-white/20 transition-all duration-300 ${
                  isVisible[`benefit-${index}`] ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'
                }`}
              >
                <div className="text-4xl font-bold text-yellow-300 mb-4">{benefit.stat}</div>
                <h3 className="text-2xl font-bold mb-3">{benefit.title}</h3>
                <p className="text-purple-100 leading-relaxed">{benefit.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 bg-gradient-to-br from-purple-50 via-blue-50 to-indigo-100">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <div
            id="cta"
            data-animate
            className={`transition-all duration-1000 ${
              isVisible.cta ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'
            }`}
          >
            <h2 className="text-4xl md:text-5xl font-bold mb-6 bg-gradient-to-r from-purple-600 to-blue-600 bg-clip-text text-transparent leading-normal pb-2">
              Ready to Transform Your Sales Calls?
            </h2>
            <p className="text-xl text-gray-600 mb-8">
              Join leading sales teams using Enzura AI to improve performance and close more deals.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link
                to="/login"
                className="px-8 py-4 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-xl font-semibold text-lg hover:from-purple-700 hover:to-blue-700 transition-all duration-200 shadow-xl hover:shadow-2xl transform hover:-translate-y-1"
              >
                Get Started Free
              </Link>
              <button
                onClick={() => {
                  const featuresSection = document.getElementById('features');
                  featuresSection?.scrollIntoView({ behavior: 'smooth' });
                }}
                className="px-8 py-4 bg-white text-gray-700 rounded-xl font-semibold text-lg border-2 border-gray-300 hover:border-purple-500 hover:text-purple-600 transition-all duration-200 shadow-lg hover:shadow-xl"
              >
                Explore Features
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-gray-900 text-gray-300 py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid md:grid-cols-4 gap-8">
            <div>
              <div className="text-2xl font-bold bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent mb-4">
                ENZURA
              </div>
              <p className="text-sm text-gray-400">
                Transforming sales conversations with AI-powered insights and analytics.
              </p>
            </div>
            <div>
              <h4 className="font-semibold text-white mb-4">Product</h4>
              <ul className="space-y-2 text-sm">
                <li>
                  <button
                    onClick={() => {
                      const featuresSection = document.getElementById('features');
                      featuresSection?.scrollIntoView({ behavior: 'smooth' });
                    }}
                    className="hover:text-purple-400 transition-colors text-left"
                  >
                    Features
                  </button>
                </li>
                <li>
                  <button
                    onClick={() => {
                      const featuresSection = document.getElementById('features');
                      featuresSection?.scrollIntoView({ behavior: 'smooth' });
                    }}
                    className="hover:text-purple-400 transition-colors text-left"
                  >
                    Pricing
                  </button>
                </li>
                <li><Link to="/login" className="hover:text-purple-400 transition-colors">Sign In</Link></li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold text-white mb-4">Resources</h4>
              <ul className="space-y-2 text-sm">
                <li><span className="hover:text-purple-400 transition-colors cursor-pointer">Documentation</span></li>
                <li><span className="hover:text-purple-400 transition-colors cursor-pointer">Support</span></li>
                <li><span className="hover:text-purple-400 transition-colors cursor-pointer">API</span></li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold text-white mb-4">Company</h4>
              <ul className="space-y-2 text-sm">
                <li><span className="hover:text-purple-400 transition-colors cursor-pointer">About</span></li>
                <li><span className="hover:text-purple-400 transition-colors cursor-pointer">Contact</span></li>
                <li><span className="hover:text-purple-400 transition-colors cursor-pointer">Privacy</span></li>
              </ul>
            </div>
          </div>
          <div className="border-t border-gray-800 mt-8 pt-8 text-center text-sm text-gray-400">
            <p>&copy; 2025 Enzura AI. All rights reserved.</p>
          </div>
        </div>
      </footer>

      {/* Add custom animations */}
      <style>{`
        @keyframes blob {
          0%, 100% {
            transform: translate(0px, 0px) scale(1);
          }
          33% {
            transform: translate(30px, -50px) scale(1.1);
          }
          66% {
            transform: translate(-20px, 20px) scale(0.9);
          }
        }
        .animate-blob {
          animation: blob 7s infinite;
        }
        .animation-delay-2000 {
          animation-delay: 2s;
        }
        .animation-delay-4000 {
          animation-delay: 4s;
        }
      `}</style>
    </div>
  );
};

export default LandingPage;

