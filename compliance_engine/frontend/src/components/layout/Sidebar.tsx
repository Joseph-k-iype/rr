import { NavLink } from 'react-router-dom';

const navItems = [
  { to: '/', label: 'Rules Network', icon: '\u270E' },
  { to: '/evaluator', label: 'Rule Evaluator', icon: '\uD83D\uDD0D' },
  { to: '/wizard', label: 'Rule Wizard', icon: '\u2630' },
];

export function Sidebar() {
  return (
    <aside className="w-48 bg-white border-r border-gray-200 min-h-[calc(100vh-3.5rem)]">
      <div className="px-4 py-4">
        <div className="w-12 h-12 bg-red-500 rounded-lg flex items-center justify-center text-white text-xs font-bold mb-6">
          Logo
        </div>
      </div>
      <nav>
        {navItems.map(({ to, label, icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                isActive
                  ? 'bg-gray-100 text-gray-900 font-medium'
                  : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
              }`
            }
          >
            <span className="text-base">{icon}</span>
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
