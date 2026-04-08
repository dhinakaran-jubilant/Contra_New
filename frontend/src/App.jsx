import React, { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import ContraMatchView from './ContraMatchView'
import Consolidate from './Consolidate'
import Login from './Login'
import AdminDashboard from './AdminDashboard'
import HomeDashboard from './HomeDashboard'
// import RejectList from './RejectList'
// import Incentive from './Incentive'
import './index.css'

// Internal App component to use useNavigate
const AppContent = ({ user, setUser, isLoggedIn, setIsLoggedIn, handleLogout }) => {
  const navigate = useNavigate();

  const handleLogin = (userData) => {
    setUser(userData)
    setIsLoggedIn(true)
    localStorage.setItem('user', JSON.stringify(userData))
    localStorage.setItem('isLoggedIn', 'true')
    localStorage.setItem('lastActivity', Date.now().toString())
    
    // Redirect based on role
    if (userData.role === 'admin') {
      navigate('/dashboard', { replace: true });
    } else {
      navigate('/live', { replace: true });
    }
  }

  // Handle root redirect to avoid infinite loops
  useEffect(() => {
    if (isLoggedIn && window.location.pathname === '/') {
      const target = user?.role === 'admin' ? '/dashboard' : '/live';
      navigate(target, { replace: true });
    }
  }, [isLoggedIn, user?.role, navigate]);

  // Inactivity and Sleep detection
  useEffect(() => {
    if (!isLoggedIn) return;

    const INACTIVITY_LIMIT = 60 * 60 * 1000; // 1 hour
    const CHECK_INTERVAL = 30 * 1000; // 30 seconds
    
    const updateActivity = () => {
      localStorage.setItem('lastActivity', Date.now().toString());
    };

    const checkSession = () => {
      const now = Date.now();
      const lastActivity = parseInt(localStorage.getItem('lastActivity') || now.toString());
      if (now - lastActivity > INACTIVITY_LIMIT) {
        handleLogout();
        navigate('/');
      }
    };

    const events = ['mousedown', 'keydown', 'scroll', 'touchstart', 'mousemove'];
    events.forEach(event => window.addEventListener(event, updateActivity));
    const interval = setInterval(checkSession, CHECK_INTERVAL);

    return () => {
      events.forEach(event => window.removeEventListener(event, updateActivity));
      clearInterval(interval);
    };
  }, [isLoggedIn, handleLogout, navigate]);

  return (
    <Routes>
      <Route 
        path="/" 
        element={isLoggedIn ? (
          // Brief loading state while useEffect handles the redirect
          <div className="flex min-h-screen items-center justify-center bg-slate-50 dark:bg-slate-950">
            <div className="h-10 w-10 animate-spin rounded-full border-4 border-primary border-t-transparent"></div>
          </div>
        ) : (
          <Login onLogin={handleLogin} />
        )} 
      />
      
      <Route 
        path="/dashboard" 
        element={isLoggedIn && user?.role === 'admin' ? (
          <HomeDashboard user={user} onLogout={() => { handleLogout(); navigate('/'); }} />
        ) : isLoggedIn ? (
          <Navigate to="/live" />
        ) : (
          <Navigate to="/" />
        )} 
      />

      <Route 
        path="/live" 
        element={isLoggedIn ? (
          <ContraMatchView user={user} onLogout={() => { handleLogout(); navigate('/'); }} />
        ) : (
          <Navigate to="/" />
        )} 
      />

      <Route 
        path="/users" 
        element={isLoggedIn && user?.role === 'admin' ? (
          <AdminDashboard user={user} onLogout={() => { handleLogout(); navigate('/'); }} initialView="users" />
        ) : (
          <Navigate to="/" />
        )} 
      />

      <Route 
        path="/users/stats" 
        element={isLoggedIn && user?.role === 'admin' ? (
          <AdminDashboard user={user} onLogout={() => { handleLogout(); navigate('/'); }} initialView="stats" />
        ) : (
          <Navigate to="/" />
        )} 
      />

      <Route 
        path="/consolidate" 
        element={isLoggedIn ? (
          <Consolidate user={user} onLogout={() => { handleLogout(); navigate('/'); }} />
        ) : (
          <Navigate to="/" />
        )} 
      />

      {/* <Route 
        path="/reject-list" 
        element={isLoggedIn ? (
          <RejectList user={user} onLogout={() => { handleLogout(); navigate('/'); }} />
        ) : (
          <Navigate to="/" />
        )} 
      />

      <Route 
        path="/incentive" 
        element={isLoggedIn ? (
          <Incentive user={user} onLogout={() => { handleLogout(); navigate('/'); }} />
        ) : (
          <Navigate to="/" />
        )} 
      /> */}

      {/* Catch-all redirect to / */}
      <Route path="*" element={<Navigate to="/" />} />
    </Routes>
  );
}

function App() {
  const [user, setUser] = useState(() => {
    const savedUser = localStorage.getItem('user');
    return savedUser ? JSON.parse(savedUser) : null;
  })
  const [isLoggedIn, setIsLoggedIn] = useState(() => {
    return localStorage.getItem('isLoggedIn') === 'true';
  })

  const handleLogout = () => {
    setUser(null);
    setIsLoggedIn(false);
    localStorage.removeItem('user');
    localStorage.removeItem('isLoggedIn');
    localStorage.removeItem('lastActivity');
  };

  return (
    <BrowserRouter>
      <AppContent 
        user={user} 
        setUser={setUser} 
        isLoggedIn={isLoggedIn} 
        setIsLoggedIn={setIsLoggedIn} 
        handleLogout={handleLogout}
      />
    </BrowserRouter>
  )
}

export default App
