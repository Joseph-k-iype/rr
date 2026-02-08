import { NavLink } from 'react-router-dom';

const navItems = [
  { to: '/', label: 'Rules Network', icon: 'M' },
  { to: '/evaluator', label: 'Evaluator', icon: 'E' },
  { to: '/wizard', label: 'Rule Wizard', icon: 'W' },
];

export function Sidebar() {
  return (
    <aside className="w-56 bg-white border-r border-gray-200 min-h-[calc(100vh-3.5rem)]">
      <nav className="py-4">
        {navItems.map(({ to, label, icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                isActive
                  ? 'bg-blue-50 text-blue-700 border-r-2 border-blue-700 font-medium'
                  : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
              }`
            }
          >
            <span className="w-7 h-7 rounded bg-gray-100 flex items-center justify-center text-xs font-bold text-gray-500">
              {icon}
            </span>
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
