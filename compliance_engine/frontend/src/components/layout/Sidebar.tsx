import { NavLink } from 'react-router-dom';

const navItems = [
  { to: '/', label: 'Network' },
  { to: '/evaluator', label: 'Evaluator' },
  { to: '/wizard', label: 'Wizard' },
  { to: '/admin', label: 'Admin' },
];

export function Sidebar() {
  return (
    <aside className="w-44 bg-white border-r border-gray-100 min-h-[calc(100vh-3.5rem)]">
      <div className="px-5 pt-6 pb-8">
        <span className="text-xs font-bold tracking-[0.2em] uppercase text-gray-900">Compliance</span>
      </div>
      <nav className="space-y-0.5 px-2">
        {navItems.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `block px-3 py-2 text-[13px] rounded transition-colors ${
                isActive
                  ? 'bg-gray-900 text-white'
                  : 'text-gray-500 hover:text-gray-900 hover:bg-gray-50'
              }`
            }
          >
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
