import React from 'react';
import { Menu } from 'lucide-react';

export function Header({ onMenu }) {
  return (
    <button type="button" className="admin-menu-toggle mobile-only" aria-label="Open navigation" aria-haspopup="dialog" onClick={onMenu}>
      <Menu size={21} /><span>Menu</span>
    </button>
  );
}
