import React, { useState } from 'react';
import { NexusIcon, ArrowUpRightIcon, EyeIcon, EyeOffIcon } from '../components/Icons';

export const LoginView = ({ onLogin, onShowToast }) => {
  const [email, setEmail] = useState('admin@platform.internal');
  const [password, setPassword] = useState('••••••••••••');
  const [rememberMe, setRememberMe] = useState(true);
  const [showPassword, setShowPassword] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    onLogin({ email, password });
    onShowToast('Signed in successfully as Administrator', 'success');
  };

  const handleForgotPassword = (e) => {
    e.preventDefault();
    onShowToast(`Password reset link sent to ${email}`, 'info');
  };

  return (
    <div className="min-h-screen w-full grid grid-cols-1 lg:grid-cols-2 bg-nexus-bg">
      {/* Left Column: Brand Hero & Orbital Geometry Graphic */}
      <div className="relative hidden lg:flex flex-col items-center justify-center bg-[#071330] overflow-hidden border-r border-[#1a2b52] p-12">


        {/* Concentric Orbital Ellipses */}
        <div className="relative flex items-center justify-center w-96 h-96">
          <div className="absolute inset-0 border border-blue-400/25 rounded-full rotate-12 scale-100" />
          <div className="absolute inset-0 border border-blue-400/20 rounded-full -rotate-45 scale-90" />
          <div className="absolute inset-0 border border-blue-400/15 rounded-full rotate-60 scale-110" />

          {/* Central Nexus Emblem */}
          <div className="relative w-24 h-24 rounded-full bg-white flex items-center justify-center text-[#071330] shadow-2xl z-10">
            <span className="font-display text-4xl font-black tracking-tight select-none">P</span>
          </div>
        </div>

        {/* Brand Caption */}
        <div className="mt-8 text-center z-10">
          <div className="text-xs font-mono font-bold tracking-widest text-blue-300 uppercase">
            Nexus Multimodal Data Platform
          </div>
        </div>
      </div>

      {/* Right Column: Authentication Form Area */}
      <div className="flex flex-col justify-center items-center p-8 sm:p-12 lg:p-16 bg-nexus-surface">
        <div className="w-full max-w-md flex flex-col gap-6">
          {/* Top Brand Header */}
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 bg-nexus-brand rounded-sm flex items-center justify-center text-white shrink-0">
              <NexusIcon className="w-4 h-4" />
            </div>
            <span className="text-base font-bold text-nexus-textPrimary tracking-tight">Nexus</span>
          </div>

          {/* Eyebrow & Hero Title */}
          <div className="flex flex-col gap-2 pt-2">
            <span className="text-[11px] font-bold tracking-widest uppercase text-nexus-brandText font-mono">
              Nexus Data Platform
            </span>
            <h1 className="text-3xl sm:text-4xl font-display font-medium text-nexus-textPrimary leading-tight">
              Everything you need, <br />
              <span className="italic text-blue-400">within reach.</span>
            </h1>
            <p className="text-xs sm:text-sm text-nexus-textMuted leading-relaxed">
              Your intelligent S3 data platform for multimodal files, neural enrichment, and fast vector discovery.
            </p>
          </div>

          {/* Sign In Form */}
          <form onSubmit={handleSubmit} className="flex flex-col gap-4 pt-2">
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-semibold text-nexus-textSecondary" htmlFor="email-input">
                Email address
              </label>
              <input
                id="email-input"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@org.internal"
                className="h-10 px-3 bg-nexus-input border border-nexus-border focus:border-nexus-brandText rounded-sm text-xs text-nexus-textPrimary outline-none transition-colors"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-semibold text-nexus-textSecondary" htmlFor="password-input">
                Password
              </label>
              <div className="relative flex items-center">
                <input
                  id="password-input"
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

            <div className="flex items-center justify-between text-xs pt-1">
              <label className="flex items-center gap-2 text-nexus-textSecondary cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  className="rounded-xs accent-nexus-brand"
                />
                <span>Remember me</span>
              </label>
              <button
                type="button"
                onClick={handleForgotPassword}
                className="text-nexus-brandText hover:underline"
              >
                Forgot password?
              </button>
            </div>

            <button
              type="submit"
              className="mt-2 h-11 bg-nexus-brand hover:bg-nexus-brandHover active:bg-blue-900 text-white text-xs font-semibold rounded-sm flex items-center justify-center gap-1.5 border border-nexus-brand transition-colors"
            >
              <span>Sign in</span>
              <ArrowUpRightIcon className="w-4 h-4" />
            </button>
          </form>

          {/* Bottom Caption */}
          <div className="text-center text-[11px] text-nexus-textMuted border-t border-nexus-borderSubtle pt-4">
            Demo access is ready. Use any valid corporate email.
          </div>
        </div>
      </div>
    </div>
  );
};
