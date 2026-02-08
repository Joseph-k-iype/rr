import { Link } from 'react-router-dom';

export function Navbar() {
  return (
    <nav className="bg-blue-900 text-white shadow-lg">
      <div className="max-w-full mx-auto px-4">
        <div className="flex justify-between h-14 items-center">
          <Link to="/" className="text-lg font-bold tracking-wide">
            Compliance Engine v6.0
          </Link>
          <div className="flex items-center gap-4 text-sm">
            <Link to="/" className="hover:text-blue-200 transition-colors">
              Rules Network
            </Link>
            <Link to="/evaluator" className="hover:text-blue-200 transition-colors">
              Evaluator
            </Link>
            <Link to="/wizard" className="hover:text-blue-200 transition-colors">
              Rule Wizard
            </Link>
          </div>
        </div>
      </div>
    </nav>
  );
}
