import { Outlet } from 'react-router-dom';
import { Navbar } from './Navbar';
import { useRef, useEffect } from 'react';
import gsap from 'gsap';

export function AppLayout() {
  const mainRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (mainRef.current) {
      gsap.fromTo(mainRef.current, { opacity: 0, y: 10 }, { opacity: 1, y: 0, duration: 0.4, ease: 'power2.out' });
    }
  }, []);

  return (
    <div className="min-h-screen">
      <Navbar />
      <main ref={mainRef} className="px-8 pb-8">
        <Outlet />
      </main>
    </div>
  );
}
