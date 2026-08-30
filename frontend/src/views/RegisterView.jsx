import React, { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { NexusIcon, EyeIcon, EyeOffIcon, ArrowUpRightIcon, ShieldIcon, UserIcon } from '../components/Icons';

/**
 * RegisterView — User and Administrator account registration.
 */
export const RegisterView = ({ showToast }) => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { register, login } = useAuth();

  const initialRole = searchParams.get('role') === 'admin' ? 'admin' : 'user';

  const [email, setEmail] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [role, setRole] = useState(initialRole);
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (password.length < 6) {
      setError('Password must be at least 6 characters');
      return;
    }

    setLoading(true);
    try {
      await register(email, password, role, displayName);
      // Auto-login after registration
      await login(email, password, role);
      showToast(`Account created. Welcome to Nexus, ${displayName || email.split('@')[0]}!`, 'success');
      navigate(role === 'admin' ? '/admin/overview' : '/user/search', { replace: true });
    } catch (err) {
      setError(err.message || 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleDemoLogin = async (demoRole) => {
    setError('');
    setLoading(true);
    try {
      if (demoRole === 'admin') {
        await login('admin@platform.internal', 'admin123', 'admin');
        showToast('Signed in as demo administrator', 'success');
        navigate('/admin/overview', { replace: true });
      } else {
        await login('user@platform.internal', 'user123', 'user');
        showToast('Signed in as demo user', 'success');
        navigate('/user/search', { replace: true });
      }
    } catch (err) {
      setError(err.message || 'Demo sign in failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-nexus-bg px-6 py-12 page-transition">
      <div className="w-full max-w-md flex flex-col gap-6 bg-nexus-surface border border-nexus-border rounded-sm p-8">
        
        {/* Header */}
        <div className="flex items-center justify-between border-b border-nexus-borderSubtle pb-4">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-nexus-brand rounded-sm flex items-center justify-center text-white shrink-0 border border-[#23426e]">
              <NexusIcon className="w-4 h-4" />
            </div>
            <div className="flex flex-col">
              <span className="text-sm font-bold text-nexus-textPrimary tracking-tight">Nexus</span>
              <span className="text-[10px] text-nexus-textMuted font-mono">Create Account</span>
            </div>
          </div>

          <span className="text-[10px] font-mono text-nexus-brandText bg-nexus-brandSubtle border border-[#284470] px-2 py-0.5 rounded-xs">
            Open Registration
          </span>
        </div>

        <div>
          <h1 className="text-xl font-display font-medium text-nexus-textPrimary">
            Register for platform access
          </h1>
          <p className="text-xs text-nexus-textSecondary mt-1 leading-relaxed">
            Create your account to search multimodal data or manage connectors.
          </p>
        </div>

        {/* 1-Click Instant Demo Access Box */}
        <div className="p-3.5 bg-nexus-elevated border border-nexus-borderStrong rounded-sm flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono font-bold uppercase text-nexus-brandText">
              Instant Demo Access
            </span>
            <span className="text-[10px] text-nexus-textMuted font-mono">No sign up required</span>
          </div>
          <div className="grid grid-cols-2 gap-2 mt-1">
            <button
              type="button"
              disabled={loading}
              onClick={() => handleDemoLogin('user')}
              className="h-8 px-2.5 bg-nexus-input hover:bg-nexus-hover border border-nexus-border hover:border-nexus-borderStrong rounded-xs text-[11px] font-medium text-nexus-textPrimary flex items-center justify-center gap-1.5 transition-colors"
            >
              <UserIcon className="w-3 h-3 text-nexus-brandText" />
              <span>Demo User</span>
            </button>
            <button
              type="button"
              disabled={loading}
              onClick={() => handleDemoLogin('admin')}
              className="h-8 px-2.5 bg-nexus-input hover:bg-nexus-hover border border-nexus-border hover:border-nexus-borderStrong rounded-xs text-[11px] font-medium text-nexus-textPrimary flex items-center justify-center gap-1.5 transition-colors"
            >
              <ShieldIcon className="w-3 h-3 text-nexus-brandText" />
              <span>Demo Admin</span>
            </button>
          </div>
        </div>

        {/* Error notice */}
        {error && (
          <div className="text-xs text-red-400 bg-red-400/10 border border-red-400/20 rounded-sm px-3 py-2">
            {error}
          </div>
        )}

        {/* Registration Form */}
        <form onSubmit={handleSubmit} className="flex flex-col gap-3.5">
          
          {/* Account Role Selector */}
          <div className="flex flex-col gap-1.5">
            <label className="text-[11px] font-semibold text-nexus-textSecondary uppercase tracking-wider">
              Account Role
            </label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setRole('user')}
                className={`h-9 px-3 rounded-xs border text-xs font-medium flex items-center justify-center gap-1.5 transition-colors ${
                  role === 'user'
                    ? 'bg-nexus-brandSubtle text-nexus-brandText border-[#284470] font-semibold'
                    : 'bg-nexus-input text-nexus-textMuted border-nexus-border hover:text-nexus-textSecondary'
                }`}
              >
                <UserIcon className="w-3.5 h-3.5" />
                <span>Standard User</span>
              </button>
              <button
                type="button"
                onClick={() => setRole('admin')}
                className={`h-9 px-3 rounded-xs border text-xs font-medium flex items-center justify-center gap-1.5 transition-colors ${
                  role === 'admin'
                    ? 'bg-nexus-brandSubtle text-nexus-brandText border-[#284470] font-semibold'
                    : 'bg-nexus-input text-nexus-textMuted border-nexus-border hover:text-nexus-textSecondary'
                }`}
              >
                <ShieldIcon className="w-3.5 h-3.5" />
                <span>Administrator</span>
              </button>
            </div>
          </div>

          {/* Email */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-nexus-textSecondary" htmlFor="reg-email">
              Email Address
            </label>
            <input
              id="reg-email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@org.internal"
              className="h-10 px-3 bg-nexus-input border border-nexus-border focus:border-nexus-brandText rounded-sm text-xs text-nexus-textPrimary outline-none transition-colors"
            />
          </div>

          {/* Full Name */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-nexus-textSecondary" htmlFor="reg-name">
              Full Name <span className="text-nexus-textMuted font-normal">(optional)</span>
            </label>
            <input
              id="reg-name"
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="e.g. Alex Morgan"
              className="h-10 px-3 bg-nexus-input border border-nexus-border focus:border-nexus-brandText rounded-sm text-xs text-nexus-textPrimary outline-none transition-colors"
            />
          </div>

          {/* Password */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-nexus-textSecondary" htmlFor="reg-password">
              Password
            </label>
            <div className="relative flex items-center">
              <input
                id="reg-password"
                type={showPassword ? 'text' : 'password'}
                required
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 6 characters"
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

          {/* Confirm Password */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-nexus-textSecondary" htmlFor="reg-confirm">
              Confirm Password
            </label>
            <input
              id="reg-confirm"
              type={showPassword ? 'text' : 'password'}
              required
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Re-enter password"
              className="h-10 px-3 bg-nexus-input border border-nexus-border focus:border-nexus-brandText rounded-sm text-xs text-nexus-textPrimary outline-none transition-colors"
            />
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={loading}
            className="mt-2 h-11 bg-nexus-brand hover:bg-nexus-brandHover active:bg-blue-900 disabled:opacity-50 text-white text-xs font-semibold rounded-sm flex items-center justify-center gap-1.5 border border-nexus-brand transition-colors"
          >
            <span>{loading ? 'Creating account...' : 'Create Account'}</span>
            {!loading && <ArrowUpRightIcon className="w-4 h-4" />}
          </button>
        </form>

        {/* Footer links */}
        <div className="flex items-center justify-between text-[11px] text-nexus-textMuted border-t border-nexus-borderSubtle pt-4">
          <span>Already have an account?</span>
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate('/login/user')}
              className="text-nexus-brandText hover:underline"
            >
              User Sign In
            </button>
            <span className="text-nexus-borderStrong">|</span>
            <button
              onClick={() => navigate('/login/admin')}
              className="text-nexus-brandText hover:underline"
            >
              Admin Sign In
            </button>
          </div>
        </div>

      </div>
    </div>
  );
};
