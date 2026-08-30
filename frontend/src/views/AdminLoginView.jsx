import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { NexusIcon, EyeIcon, EyeOffIcon, ArrowUpRightIcon, ShieldIcon } from '../components/Icons';

/**
 * AdminLoginView — Administrator authentication screen.
 */
export const AdminLoginView = ({ showToast }) => {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(email, password, 'admin');
      showToast('Signed in as administrator', 'success');
      navigate('/admin/overview', { replace: true });
    } catch (err) {
      setError(err.message || 'Sign in failed. Check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  const handleDemoSignIn = async () => {
    setError('');
    setLoading(true);
    try {
      await login('admin@platform.internal', 'admin123', 'admin');
      showToast('Signed in as demo administrator', 'success');
      navigate('/admin/overview', { replace: true });
    } catch (err) {
      setError(err.message || 'Demo sign in failed.');
    } finally {
      setLoading(false);
    }
  };

  const fillDemoCredentials = () => {
    setEmail('admin@platform.internal');
    setPassword('admin123');
  };

  return (
    <div className="min-h-screen w-full grid grid-cols-1 lg:grid-cols-2 bg-nexus-bg">
      {/* Left: branding panel */}
      <div className="relative hidden lg:flex flex-col items-center justify-center bg-[#071330] border-r border-[#1a2b52] p-12">
        <div className="relative z-10 flex flex-col items-center gap-8">
          <div className="w-16 h-16 bg-nexus-brand rounded-sm flex items-center justify-center text-white border border-[#23426e]">
            <NexusIcon className="w-8 h-8" />
          </div>
          <div className="text-center flex flex-col gap-2">
            <div className="text-xs font-mono font-bold tracking-widest text-blue-300 uppercase">
              Administrator Portal
            </div>
            <div className="text-2xl font-display font-medium text-white">
              Nexus Data Platform
            </div>
            <p className="text-xs text-blue-200/60 max-w-xs leading-relaxed">
              Full administrative access to connectors, ingestion pipelines, and audit records.
            </p>
          </div>
        </div>
      </div>

      {/* Right: form */}
      <div className="flex flex-col justify-center items-center p-8 sm:p-12 lg:p-16 bg-nexus-surface">
        <div className="w-full max-w-md flex flex-col gap-6">
          {/* Brand mark on mobile */}
          <div className="flex items-center gap-2.5 lg:hidden">
            <div className="w-7 h-7 bg-nexus-brand rounded-sm flex items-center justify-center text-white shrink-0 border border-[#23426e]">
              <NexusIcon className="w-4 h-4" />
            </div>
            <span className="text-base font-bold text-nexus-textPrimary tracking-tight">Nexus</span>
          </div>

          {/* Headline */}
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <h1 className="text-2xl font-display font-medium text-nexus-textPrimary">
                Administrator sign in
              </h1>
              <span className="text-[10px] font-mono text-nexus-brandText bg-nexus-brandSubtle border border-[#284470] px-2 py-0.5 rounded-xs">
                Admin Role
              </span>
            </div>
            <p className="text-xs text-nexus-textMuted leading-relaxed">
              Sign in with your credentials or use instant 1-click demo access below.
            </p>
          </div>

          {/* 1-Click Instant Demo Login Banner */}
          <div className="p-3.5 bg-nexus-elevated border border-nexus-borderStrong rounded-sm flex flex-col gap-2.5">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-mono font-bold uppercase text-nexus-brandText flex items-center gap-1.5">
                <ShieldIcon className="w-3.5 h-3.5" />
                <span>Instant Demo Access</span>
              </span>
              <button
                type="button"
                onClick={fillDemoCredentials}
                className="text-[10px] text-nexus-brandText hover:underline font-mono"
              >
                Auto-fill inputs
              </button>
            </div>
            <button
              type="button"
              disabled={loading}
              onClick={handleDemoSignIn}
              className="w-full h-9 bg-nexus-brand/20 hover:bg-nexus-brand/30 border border-[#284470] text-nexus-brandText text-xs font-semibold rounded-xs flex items-center justify-center gap-2 transition-colors"
            >
              <span>Sign In as Demo Admin (1-Click)</span>
              <ArrowUpRightIcon className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Error */}
          {error && (
            <div className="text-xs text-red-400 bg-red-400/10 border border-red-400/20 rounded-sm px-3 py-2">
              {error}
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-semibold text-nexus-textSecondary" htmlFor="admin-email">
                Email address
              </label>
              <input
                id="admin-email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="admin@platform.internal"
                className="h-10 px-3 bg-nexus-input border border-nexus-border focus:border-nexus-brandText rounded-sm text-xs text-nexus-textPrimary outline-none transition-colors"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-semibold text-nexus-textSecondary" htmlFor="admin-password">
                Password
              </label>
              <div className="relative flex items-center">
                <input
                  id="admin-password"
                  type={showPassword ? 'text' : 'password'}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  className="w-full h-10 pl-3 pr-9 bg-nexus-input border border-nexus-border focus:border-nexus-brandText rounded-sm text-xs text-nexus-textPrimary outline-none transition-colors"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-2.5 p-1 text-nexus-textMuted hover:text-nexus-textPrimary transition-colors"
                >
                  {showPassword ? <EyeOffIcon className="w-4 h-4" /> : <EyeIcon className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="mt-2 h-11 bg-nexus-brand hover:bg-nexus-brandHover active:bg-blue-900 disabled:opacity-50 text-white text-xs font-semibold rounded-sm flex items-center justify-center gap-1.5 border border-nexus-brand transition-colors"
            >
              <span>{loading ? 'Signing in...' : 'Sign in as Administrator'}</span>
              {!loading && <ArrowUpRightIcon className="w-4 h-4" />}
            </button>
          </form>

          {/* Links / Navigation */}
          <div className="flex flex-col gap-2.5 text-center text-[11px] text-nexus-textMuted border-t border-nexus-borderSubtle pt-4">
            <div className="flex items-center justify-center gap-3">
              <span>Don't have an account?</span>
              <button
                onClick={() => navigate('/register?role=admin')}
                className="text-nexus-brandText hover:underline font-semibold"
              >
                Register New Account
              </button>
            </div>
            <div>
              Not an administrator?{' '}
              <button
                onClick={() => navigate('/login/user')}
                className="text-nexus-brandText hover:underline"
              >
                User sign in
              </button>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
};
