"use client";
import React, { useState, useEffect, useMemo } from 'react';
import { Eye, EyeOff, Mail, Lock, User, Building, Check, X } from 'lucide-react';
import { useRouter } from 'next/navigation';
import Header from './components/Header';
import Image from 'next/image';
import { getCurrentUser } from './lib/auth';

export default function AuthPage() {
  const [isLogin, setIsLogin] = useState(true);
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [currentImageIndex, setCurrentImageIndex] = useState(0);
  const [isChecking, setIsChecking] = useState(true);
  const router = useRouter();

  // Redirect if already authenticated (check once on mount)
  useEffect(() => {
    getCurrentUser().then((user) => {
      if (user) {
        router.replace('/dashboard');
      } else {
        setIsChecking(false);
      }
    });
  }, []); // Empty dependency - run only once on mount
  
  // Add your images here
  const images = [
    '/Cover_images/image_1.JPG',
    '/Cover_images/image_2.JPG',
    '/Cover_images/image_3.JPG',
    '/Cover_images/image_4.JPG',
    '/Cover_images/image_5.JPG',
  ];

  // Automatic slideshow effect
  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentImageIndex((prevIndex) => 
        prevIndex === images.length - 1 ? 0 : prevIndex + 1
      );
    }, 5000); // Change image every 5 seconds

    return () => clearInterval(interval);
  }, [images.length]);
  
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    firstName: '',
    lastName: '',
    organization: ''
  });

  const passwordRequirements = useMemo(() => [
    { label: 'At least 8 characters', met: formData.password.length >= 8 },
    { label: 'One uppercase letter', met: /[A-Z]/.test(formData.password) },
    { label: 'One lowercase letter', met: /[a-z]/.test(formData.password) },
    { label: 'One digit', met: /[0-9]/.test(formData.password) },
    { label: 'One special character', met: /[^A-Za-z0-9]/.test(formData.password) },
  ], [formData.password]);

  const isPasswordValid = passwordRequirements.every(r => r.met);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
    setError('');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const { API_URL, API_ENDPOINTS } = await import('./lib/api');

      const url = isLogin
        ? `${API_URL}${API_ENDPOINTS.AUTH.LOGIN}`
        : `${API_URL}${API_ENDPOINTS.AUTH.REGISTER}`;

      const payload = isLogin
        ? { email: formData.email, password: formData.password }
        : {
            email: formData.email,
            password: formData.password,
            first_name: formData.firstName,
            last_name: formData.lastName,
            organization: formData.organization
          };

      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(payload)
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Authentication failed');
      }

      if (isLogin) {
        window.location.href = '/dashboard';
      } else {
        setIsLogin(true);
        setError(data.message || 'Check your email for a verification link.');
      }

    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  // Show loading while checking authentication
  if (isChecking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-red-800 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="font-header shrink-0">
        <Header />
      </header>

      {/* Main Content */}
      <div className="flex-1 flex">
        {/* Left Side - Slideshow */}
        <div className="hidden lg:block lg:w-1/2 relative">
          {images.map((image, index) => (
            <Image
              key={index}
              src={image}
              alt={`Gravel Road ${index + 1}`}
              fill
              sizes="(max-width: 768px) 100vw, 50vw"  // Responsive sizes
              quality={85}  // Good balance
              className={`object-cover transition-opacity duration-1000 ${
                index === currentImageIndex ? 'opacity-100' : 'opacity-0'
              }`}
              priority={index === 0}  // Only prioritize first image
              loading={index === 0 ? undefined : 'lazy'}  // Lazy load others
            />
          ))}
                    
          {/* Dot indicators */}
          <div className="absolute bottom-4 left-1/2 transform -translate-x-1/2 flex gap-2 z-10">
            {images.map((_, index) => (
              <button
                key={index}
                onClick={() => setCurrentImageIndex(index)}
                className={`w-3 h-3 rounded-full transition-colors ${
                  index === currentImageIndex ? 'bg-white' : 'bg-white/50'
                }`}
                aria-label={`Go to slide ${index + 1}`}
              />
            ))}
          </div>
        </div>

        {/* Right Side - Auth Form */}
        <div className="w-full lg:w-1/2 flex items-center justify-center p-6 bg-linear-to-br from-gray-50 to-red-50">
          <div className="w-full max-w-md">
            <div className="bg-white rounded-2xl shadow-xl p-8">
              
              <div className="text-center mb-8">
                <h2 className="text-3xl font-bold text-red-900 mb-2">
                  {isLogin ? 'Welcome Back' : 'Create Account'}
                </h2>
                <p className="text-gray-700">
                  {isLogin 
                    ? 'Sign in to access your dashboard' 
                    : 'Sign up to start analyzing gravel roads'}
                </p>
              </div>

              {error && (
                <div className={`mb-6 p-3 rounded-lg text-sm ${
                  error.includes('successful') 
                    ? 'bg-green-50 text-green-800 border border-green-200'
                    : 'bg-red-50 text-red-800 border border-red-200'
                }`}>
                  {error}
                </div>
              )}

              <div className="space-y-4">
                
                {!isLogin && (
                  <>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          First Name
                        </label>
                        <div className="relative">
                          <User className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={18} />
                          <input
                            type="text"
                            name="firstName"
                            value={formData.firstName}
                            onChange={handleChange}
                            className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                            placeholder="John"
                          />
                        </div>
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          Last Name
                        </label>
                        <div className="relative">
                          <User className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={18} />
                          <input
                            type="text"
                            name="lastName"
                            value={formData.lastName}
                            onChange={handleChange}
                            className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                            placeholder="Doe"
                          />
                        </div>
                      </div>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Organization
                      </label>
                      <div className="relative">
                        <Building className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={18} />
                        <input
                          type="text"
                          name="organization"
                          value={formData.organization}
                          onChange={handleChange}
                          className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                          placeholder="Iowa State University"
                        />
                      </div>
                    </div>
                  </>
                )}

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Email Address
                  </label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={18} />
                    <input
                      type="email"
                      name="email"
                      value={formData.email}
                      onChange={handleChange}
                      className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                      placeholder="you@example.com"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Password
                  </label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={18} />
                    <input
                      type={showPassword ? 'text' : 'password'}
                      name="password"
                      value={formData.password}
                      onChange={handleChange}
                      className="w-full pl-10 pr-12 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                      placeholder="••••••••"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600"
                    >
                      {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                    </button>
                  </div>
                  {!isLogin && formData.password.length > 0 && (
                    <ul className="mt-2 space-y-1">
                      {passwordRequirements.map((req) => (
                        <li key={req.label} className="flex items-center gap-1.5 text-xs">
                          {req.met ? (
                            <Check size={14} className="text-green-600 shrink-0" />
                          ) : (
                            <X size={14} className="text-gray-400 shrink-0" />
                          )}
                          <span className={req.met ? 'text-green-700' : 'text-gray-500'}>
                            {req.label}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                <button
                  onClick={handleSubmit}
                  disabled={loading || (!isLogin && !isPasswordValid)}
                  className="w-full py-3 px-4 bg-red-800 text-white font-semibold rounded-lg hover:bg-red-900 focus:ring-4 focus:ring-red-300 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
                >
                  {loading ? 'Please wait...' : (isLogin ? 'Sign In' : 'Create Account')}
                </button>
              </div>

              <div className="mt-6 text-center">
                <button
                  type="button"
                  onClick={() => {
                    setIsLogin(!isLogin);
                    setError('');
                    setFormData({
                      email: '',
                      password: '',
                      firstName: '',
                      lastName: '',
                      organization: ''
                    });
                  }}
                  className="text-red-800 hover:text-red-900 font-medium underline"
                >
                  {isLogin 
                    ? "Don't have an account? Sign up" 
                    : 'Already have an account? Sign in'}
                </button>
              </div>
            </div>

            <div className="text-center mt-6 text-sm text-gray-600">
              <p>By continuing, you agree to our Terms of Service and Privacy Policy</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}