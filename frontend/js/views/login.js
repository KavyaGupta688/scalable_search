/**
 * Samsung Prism Enterprise Platform - Login View
 * Matches reference image design:
 * - Centered clean card
 * - Top black badge with database icon
 * - Email, Password with toggle, and MFA inputs
 * - Sign in and Continue with SSO buttons
 */

import { api } from '../api.js';
import { renderIcon } from '../icons.js';

export function renderLoginView(container, { onLoginSuccess, onShowToast }) {
  let isPasswordVisible = false;

  container.innerHTML = `
    <div class="login-page-container">
      <div class="login-auth-card">
        <div class="login-auth-header">
          <div class="login-app-icon">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <ellipse cx="12" cy="5" rx="9" ry="3"/>
              <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
              <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
            </svg>
          </div>
          <h1 class="login-app-title">Sign in to data platform</h1>
          <p class="login-app-subtitle">Admin access only</p>
        </div>

        <form class="login-auth-form" id="login-form">
          <div class="login-field-group">
            <label class="login-field-label" for="login-email">Email</label>
            <input 
              class="login-input" 
              id="login-email" 
              type="email" 
              value="admin@samsung.com" 
              placeholder="name@company.com" 
              required 
            />
          </div>

          <div class="login-field-group">
            <label class="login-field-label" for="login-password">Password</label>
            <div class="login-input-wrapper">
              <input 
                class="login-input" 
                id="login-password" 
                type="password" 
                value="••••••••••••" 
                placeholder="Enter your password" 
                required 
              />
              <button type="button" class="login-toggle-pw" id="btn-toggle-pw" aria-label="Toggle password visibility">
                ${renderIcon('eye')}
              </button>
            </div>
          </div>

          <div class="login-field-group">
            <label class="login-field-label" for="login-mfa">Authentication code</label>
            <input 
              class="login-input" 
              id="login-mfa" 
              type="text" 
              value="849201" 
              placeholder="6-digit code from authenticator app" 
              required 
            />
            <span class="login-field-hint">MFA required for admin roles</span>
          </div>

          <button type="submit" class="login-btn-primary" id="btn-submit-signin">
            Sign in
          </button>

          <div class="login-divider-row">
            <div class="login-divider-line"></div>
            <span class="login-divider-text">or</span>
            <div class="login-divider-line"></div>
          </div>

          <button type="button" class="login-btn-sso" id="btn-sso-login">
            ${renderIcon('shield')} Continue with SSO
          </button>

          <a href="#forgot" class="login-forgot-link" id="link-forgot-pw">
            Forgot password
          </a>
        </form>
      </div>
    </div>
  `;

  // Password visibility toggle
  const pwInput = container.querySelector('#login-password');
  const toggleBtn = container.querySelector('#btn-toggle-pw');
  toggleBtn.addEventListener('click', () => {
    isPasswordVisible = !isPasswordVisible;
    pwInput.type = isPasswordVisible ? 'text' : 'password';
    toggleBtn.innerHTML = renderIcon(isPasswordVisible ? 'eyeOff' : 'eye');
  });

  // Form submit
  container.querySelector('#login-form').addEventListener('submit', (e) => {
    e.preventDefault();
    const email = container.querySelector('#login-email').value;
    const password = container.querySelector('#login-password').value;
    const mfaCode = container.querySelector('#login-mfa').value;

    api.login({ email, password, mfaCode });
    onShowToast('Signed in successfully as Administrator', 'success');
    onLoginSuccess();
  });

  // SSO Login
  container.querySelector('#btn-sso-login').addEventListener('click', () => {
    api.login({ email: 'admin@samsung.com', password: 'sso', mfaCode: 'SSO-SAML' });
    onShowToast('SSO session authenticated with Samsung Knox ID', 'success');
    onLoginSuccess();
  });

  // Forgot password
  container.querySelector('#link-forgot-pw').addEventListener('click', (e) => {
    e.preventDefault();
    onShowToast('Password reset link sent to admin@samsung.com', 'info');
  });
}
