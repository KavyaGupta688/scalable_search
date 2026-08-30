import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { NexusIcon, EyeIcon, EyeOffIcon, ArrowUpRightIcon, UserIcon } from '../components/Icons';

/**
 * UserLoginView — Standard user authentication screen.
 */
export const UserLoginView = ({ showToast }) => {
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
      await login(email, password, 'user');
      showToast('Signed in successfully', 'success');
      navigate('/user/search', { replace: true });
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
      await login('user@platform.internal', 'user123', 'user');
      showToast('Signed in as demo user', 'success');
      navigate('/user/search', { replace: true });
    } catch (err) {
      setError(err.message || 'Demo sign in failed.');
    } finally {
      setLoading(false);
    }
  };

  const fillDemoCredentials = () => {
    setEmail('user@platform.internal');
    setPassword('user123');
  };

  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-nexus-bg px-6 py-12 page-transition">
      <div className="w-full max-w-sm flex flex-col gap-6 bg-nexus-surface border border-nexus-border rounded-sm p-8">
        
        {/* Brand */}
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 bg-nexus-brand rounded-sm flex items-center justify-center text-white shrink-0 border border-[#23426e]">
            <NexusIcon className="w-4 h-4" />
          </div>
          <div className="flex flex-col">
            <span className="text-sm font-bold text-nexus-textPrimary tracking-tight">Nexus</span>
            <span className="text-[10px] text-nexus-textMuted font-mono">User Access</span>
          </div>
        </div>

        {/* Headline */}
        <div className="flex flex-col gap-1.5">
          <h1 className="text-xl font-display font-medium text-nexus-textPrimary">
            User sign in
          </h1>
          <p className="text-xs text-nexus-textMuted leading-relaxed">
            Search, discover, and download from the platform catalog.
          </p>
        </div>

        {/* 1-Click Instant Demo Login Banner */}
        <div className="p-3.5 bg-nexus-elevated border border-nexus-borderStrong rounded-sm flex flex-col gap-2.5">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono font-bold uppercase text-nexus-brandText flex items-center gap-1.5">
              <UserIcon className="w-3.5 h-3.5" />
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
            <span>Sign In as Demo User (1-Click)</span>
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
            <label className="text-xs font-semibold text-nexus-textSecondary" htmlFor="user-email">
              Email address
            </label>
            <input
              id="user-email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="user@platform.internal"
              className="h-10 px-3 bg-nexus-input border border-nexus-border focus:border-nexus-brandText rounded-sm text-xs text-nexus-textPrimary outline-none transition-colors"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-nexus-textSecondary" htmlFor="user-password">
              Password
            </label>
            <div className="relative flex items-center">
              <input
                id="user-password"
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
            <span>{loading ? 'Signing in...' : 'Sign in as User'}</span>
            {!loading && <ArrowUpRightIcon className="w-4 h-4" />}
          </button>
        </form>

        {/* Links / Navigation */}
        <div className="flex flex-col gap-2.5 text-center text-[11px] text-nexus-textMuted border-t border-nexus-borderSubtle pt-4">
          <div className="flex items-center justify-center gap-3">
            <span>Don't have an account?</span>
            <button
              onClick={() => navigate('/register?role=user')}
              className="text-nexus-brandText hover:underline font-semibold"
            >
              Register New Account
            </button>
          </div>
          <div>
            Need administrator access?{' '}
            <button
              onClick={() => navigate('/login/admin')}
              className="text-nexus-brandText hover:underline"
            >
              Admin sign in
            </button>
          </div>
        </div>

      </div>
    </div>
  );
};
