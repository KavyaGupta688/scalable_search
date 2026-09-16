import { useDialog } from '../components/useDialog';
import { DialogBackdrop } from '../components/DialogBackdrop';
import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { listUsers } from '../services/auth';
import {
  Users as UsersIcon,
  Plus,
  ShieldCheck,
  User as UserIcon,
  X,
  Loader2,
  AlertCircle,
  Clock,
} from 'lucide-react';

/**
 * UserManagementView — Admin-only view for creating and listing user accounts.
 */
export const UserManagementView = ({ showToast }) => {
  const { register } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showModal, setShowModal] = useState(false);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await listUsers();
      setUsers(data.users || []);
    } catch (err) {
      setError(err.message || 'Failed to load users');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  return (
    <div className="flex-1 flex flex-col min-h-0 page-transition">
      {/* Header */}
      <header className="user-management-header flex items-center justify-between py-4 border-b border-nexus-borderSubtle">
        <div>
          <h1 className="page-title flex items-center gap-3">
            <UsersIcon className="w-5 h-5 text-nexus-brandText" />
            User Management
          </h1>
          <p className="text-sm text-nexus-textMuted mt-0.5">
            Create and manage platform user accounts
          </p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-1.5 px-3.5 h-9 bg-nexus-brand hover:bg-nexus-brandHover text-white text-sm font-semibold rounded-sm transition-colors"
        >
          <Plus className="w-3.5 h-3.5" />
          Create User
        </button>
      </header>

      {/* Content */}
      <section className="flex-1 overflow-y-auto p-6">
        {error && (
          <div className="flex items-center gap-2 p-3 mb-4 rounded-sm bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
            <AlertCircle className="w-4 h-4 shrink-0" />
            {error}
            <button
              onClick={fetchUsers}
              className="ml-auto text-red-300 hover:text-red-200 underline text-sm"
            >
              Retry
            </button>
          </div>
        )}

        <div className="nx-panel overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-nexus-borderSubtle bg-nexus-elevated/50">
                <th className="text-left px-4 py-2.5 font-semibold text-nexus-textSecondary uppercase tracking-wider text-sm">
                  User
                </th>
                <th className="text-left px-4 py-2.5 font-semibold text-nexus-textSecondary uppercase tracking-wider text-sm">
                  Email
                </th>
                <th className="text-left px-4 py-2.5 font-semibold text-nexus-textSecondary uppercase tracking-wider text-sm">
                  Role
                </th>
                <th className="text-left px-4 py-2.5 font-semibold text-nexus-textSecondary uppercase tracking-wider text-sm">
                  Created
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-nexus-borderSubtle">
              {loading ? (
                Array.from({ length: 3 }).map((_, i) => (
                  <tr key={i}>
                    <td className="px-4 py-3" colSpan={4}>
                      <div className="h-4 bg-nexus-elevated rounded animate-pulse" />
                    </td>
                  </tr>
                ))
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-10 text-center text-nexus-textMuted">
                    No users found
                  </td>
                </tr>
              ) : (
                users.map((user) => (
                  <tr key={user.id} className="hover:bg-nexus-hover/30 transition-colors">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2.5">
                        <div
                          className={`w-7 h-7 rounded-sm flex items-center justify-center text-sm font-bold ${
                            user.role === 'admin'
                              ? 'bg-nexus-brandSubtle border border-nexus-borderStrong text-nexus-brandText'
                              : 'bg-nexus-elevated border border-nexus-borderStrong text-nexus-textSecondary'
                          }`}
                        >
                          {(user.display_name || user.email)
                            .split(/[\s@]+/)
                            .slice(0, 2)
                            .map((w) => w[0]?.toUpperCase())
                            .join('')}
                        </div>
                        <span className="text-nexus-textPrimary font-medium">
                          {user.display_name || user.email.split('@')[0]}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-nexus-textSecondary font-mono text-sm">
                      {user.email}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-sm text-sm font-semibold ${
                          user.role === 'admin'
                            ? 'bg-nexus-brandSubtle text-nexus-brandText'
                            : 'bg-nexus-elevated text-nexus-textSecondary border border-nexus-borderSubtle'
                        }`}
                      >
                        {user.role === 'admin' ? (
                          <ShieldCheck className="w-3 h-3" />
                        ) : (
                          <UserIcon className="w-3 h-3" />
                        )}
                        {user.role === 'admin' ? 'Admin' : 'User'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-nexus-textMuted text-sm">
                      <div className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {new Date(user.created_at).toLocaleDateString('en-US', {
                          year: 'numeric',
                          month: 'short',
                          day: 'numeric',
                        })}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <p className="mt-3 text-sm text-nexus-textMuted">
          {users.length} registered {users.length === 1 ? 'account' : 'accounts'}
        </p>
      </section>

      {/* Create User Modal */}
      {showModal && (
        <CreateUserModal
          onClose={() => setShowModal(false)}
          onSuccess={(newUser) => {
            setShowModal(false);
            fetchUsers();
            showToast(`Account created for ${newUser.email}`, 'success');
          }}
          register={register}
        />
      )}
    </div>
  );
};


// ── Create User Modal ──────────────────────────────────────────────────────

const CreateUserModal = ({ onClose, onSuccess, register }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [role, setRole] = useState('user');
  const dialogRef = useDialog(onClose);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      const newUser = await register(email, password, role, displayName);
      onSuccess(newUser);
    } catch (err) {
      setError(err.message || 'Failed to create user');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <DialogBackdrop>
      <div className="detail-dialog max-w-md dialog-surface modal-enter" ref={dialogRef} role="dialog" aria-modal="true" aria-label="Create User Account" tabIndex={-1}>
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-nexus-borderSubtle">
          <h2 className="text-sm font-bold text-nexus-textPrimary">Create User Account</h2>
          <button
            onClick={onClose}
            aria-label="Close dialog" className="p-1 text-nexus-textMuted hover:text-nexus-textPrimary transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-5 flex flex-col gap-4">
          {/* Email */}
          <div className="flex flex-col gap-1.5">
            <label htmlFor="create-user-email" className="text-sm font-medium text-nexus-textSecondary uppercase tracking-wider">Email Address
            </label>
            <input
              type="email"
              required
              id="create-user-email" value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@org.internal"
              className="h-9 px-3 bg-nexus-input border border-nexus-border rounded-sm text-sm text-nexus-textPrimary placeholder:text-nexus-textMuted/50 focus:outline-none focus:border-nexus-brandText transition-colors"
            />
          </div>

          {/* Display Name */}
          <div className="flex flex-col gap-1.5">
            <label htmlFor="create-user-name" className="text-sm font-medium text-nexus-textSecondary uppercase tracking-wider">Display Name
              <span className="ml-1 text-nexus-textMuted font-normal normal-case">(optional)</span>
            </label>
            <input
              type="text"
              id="create-user-name" value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Full name"
              className="h-9 px-3 bg-nexus-input border border-nexus-border rounded-sm text-sm text-nexus-textPrimary placeholder:text-nexus-textMuted/50 focus:outline-none focus:border-nexus-brandText transition-colors"
            />
          </div>

          {/* Password */}
          <div className="flex flex-col gap-1.5">
            <label htmlFor="create-user-password" className="text-sm font-medium text-nexus-textSecondary uppercase tracking-wider">Password
            </label>
            <input
              type="password"
              required
              minLength={6}
              id="create-user-password" value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Minimum 6 characters"
              className="h-9 px-3 bg-nexus-input border border-nexus-border rounded-sm text-sm text-nexus-textPrimary placeholder:text-nexus-textMuted/50 focus:outline-none focus:border-nexus-brandText transition-colors"
            />
          </div>

          {/* Role */}
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium text-nexus-textSecondary uppercase tracking-wider">
              Role
            </label>
            <div className="flex gap-3">
              <label className="flex items-center gap-2 cursor-pointer group">
                <input
                  type="radio"
                  name="role"
                  value="user"
                  checked={role === 'user'}
                  onChange={() => setRole('user')}
                  className="accent-nexus-brandText"
                />
                <span className="flex items-center gap-1 text-sm text-nexus-textSecondary group-hover:text-nexus-textPrimary transition-colors">
                  <UserIcon className="w-3.5 h-3.5" />
                  User
                </span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer group">
                <input
                  type="radio"
                  name="role"
                  value="admin"
                  checked={role === 'admin'}
                  onChange={() => setRole('admin')}
                  className="accent-nexus-brandText"
                />
                <span className="flex items-center gap-1 text-sm text-nexus-textSecondary group-hover:text-nexus-textPrimary transition-colors">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  Admin
                </span>
              </label>
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="flex items-center gap-2 text-red-400 text-sm">
              <AlertCircle className="w-3.5 h-3.5 shrink-0" />
              {error}
            </div>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={submitting}
            className="h-9 mt-1 flex items-center justify-center gap-2 bg-nexus-brand hover:bg-nexus-brandHover text-white text-sm font-semibold rounded-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                Creating...
              </>
            ) : (
              <>
                <Plus className="w-3.5 h-3.5" />
                Create Account
              </>
            )}
          </button>
        </form>
      </div>
    </DialogBackdrop>
  );
};
