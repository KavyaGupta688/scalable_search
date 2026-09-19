import { AuthLayout } from '../components/DesignSystem';
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { EyeIcon, EyeOffIcon, ArrowUpRightIcon } from '../components/Icons';

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

  return (
    <AuthLayout admin>
          {/* Headline */}
          <div className="flex flex-col gap-1.5">
              <h1 className="page-title">
                Administrator sign in
              </h1>
            <p className="text-sm text-nexus-textMuted leading-relaxed">
              Sign in with your administrator credentials.
            </p>
          </div>

          {/* Error */}
          {error && (
            <div className="text-sm text-red-400 bg-red-400/10 border border-red-400/20 rounded-sm px-3 py-2">
              {error}
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-semibold text-nexus-textSecondary" htmlFor="admin-email">
                Email address
              </label>
              <input
                id="admin-email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="admin@platform.internal"
                className="h-10 px-3 bg-nexus-input border border-nexus-border focus:border-nexus-brandText rounded-sm text-sm text-nexus-textPrimary outline-none transition-colors"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-semibold text-nexus-textSecondary" htmlFor="admin-password">
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
                  className="w-full h-10 pl-3 pr-9 bg-nexus-input border border-nexus-border focus:border-nexus-brandText rounded-sm text-sm text-nexus-textPrimary outline-none transition-colors"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                  className="absolute right-2.5 p-1 text-nexus-textMuted hover:text-nexus-textPrimary transition-colors"
                >
                  {showPassword ? <EyeOffIcon className="w-4 h-4" /> : <EyeIcon className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="mt-2 h-11 bg-nexus-brand hover:bg-nexus-brandHover active:bg-blue-900 disabled:opacity-50 text-white text-sm font-semibold rounded-sm flex items-center justify-center gap-1.5 border border-nexus-brand transition-colors"
            >
              <span>{loading ? 'Signing in...' : 'Sign in as Administrator'}</span>
              {!loading && <ArrowUpRightIcon className="w-4 h-4" />}
            </button>
          </form>

          {/* Links / Navigation */}
          <div className="flex flex-col gap-2.5 text-center text-sm text-nexus-textMuted border-t border-nexus-borderSubtle pt-4">
            <div className="flex items-center justify-center gap-3">
              <span>Need administrator access?</span>
              <button disabled title="An existing administrator must create this account." className="text-nexus-brandText font-semibold">Ask your administrator</button>
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
    </AuthLayout>
  );
};
