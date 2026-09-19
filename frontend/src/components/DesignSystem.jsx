import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight } from 'lucide-react';

export function Brand({ compact = false }) {
  return <span className="brand"><span className="brand-mark" aria-hidden="true">✳</span>{!compact && <span>nexus<span className="brand-dot">.</span></span>}</span>;
}

export function Button({ as: Tag = 'button', variant = 'primary', className = '', children, ...props }) {
  return <Tag className={`nx-button nx-button--${variant} ${className}`} {...props}>{children}</Tag>;
}

export function Panel({ as: Tag = 'section', className = '', children, ...props }) {
  return <Tag className={`nx-panel ${className}`} {...props}>{children}</Tag>;
}

export function PageHeading({ title, description, action }) {
  return <div className="page-heading"><div><h1>{title}</h1>{description && <p>{description}</p>}</div>{action}</div>;
}

export function AuthLayout({ children, admin = false }) {
  return <main className="auth-page"><div className="auth-frame">
    <aside className="auth-art-panel">
      <div className="auth-art-header"><Link to="/" aria-label="Nexus home"><Brand /></Link><Link to="/" className="back-link">Back to website <ArrowUpRight size={16} /></Link></div>
      <div className="auth-art-copy"><h2>{admin ? 'Manage your data.' : 'Find your next dataset.'}</h2><p>{admin ? 'Connect sources and monitor processing from one place.' : 'Search, preview, and download the files you need.'}</p></div>
    </aside>
    <section className="auth-form-panel"><div className="auth-form-content">{children}</div></section>
  </div></main>;
}
