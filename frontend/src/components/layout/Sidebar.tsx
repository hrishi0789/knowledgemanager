import React from 'react';
import { NavLink } from 'react-router-dom';
import { useUiStore } from '../../stores/uiStore';
import { 
  Library, 
  Search, 
  Network, 
  ActivitySquare, 
  Settings,
  PanelLeftClose,
  PanelLeftOpen
} from 'lucide-react';

export const Sidebar: React.FC = () => {
  const { sidebarOpen, toggleSidebar } = useUiStore();

  const navItems = [
    { to: '/library', icon: Library, label: 'Library' },
    { to: '/search', icon: Search, label: 'Search' },
    { to: '/graph', icon: Network, label: 'Graph Explorer' },
    { to: '/analytics', icon: ActivitySquare, label: 'Analytics' },
    { to: '/admin', icon: Settings, label: 'Admin' },
  ];

  return (
    <aside 
      style={{
        width: sidebarOpen ? '250px' : '64px',
        backgroundColor: 'var(--color-surface)',
        borderRight: '1px solid var(--color-border)',
        transition: 'width 0.3s ease',
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: sidebarOpen ? 'space-between' : 'center', padding: 'var(--s-4)' }}>
        {sidebarOpen && (
          <h2 style={{ fontSize: 'var(--s-5)', fontWeight: 600, color: 'var(--color-primary)' }}>
            PKMS
          </h2>
        )}
        <button 
          onClick={toggleSidebar}
          style={{ background: 'transparent', border: 'none', color: 'var(--color-text-secondary)', cursor: 'pointer' }}
          title="Toggle Sidebar"
        >
          {sidebarOpen ? <PanelLeftClose size={20} /> : <PanelLeftOpen size={20} />}
        </button>
      </div>

      <nav style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 'var(--s-2)', padding: 'var(--s-2)' }}>
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            style={({ isActive }) => ({
              display: 'flex',
              alignItems: 'center',
              justifyContent: sidebarOpen ? 'flex-start' : 'center',
              gap: 'var(--s-3)',
              padding: 'var(--s-3)',
              borderRadius: 'var(--r-md)',
              textDecoration: 'none',
              color: isActive ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
              backgroundColor: isActive ? 'var(--color-surface-3)' : 'transparent',
              transition: 'background-color 0.2s',
            })}
          >
            <item.icon size={20} />
            {sidebarOpen && <span>{item.label}</span>}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
};
