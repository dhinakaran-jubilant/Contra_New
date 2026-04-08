import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import logoImage from './assets/logo.png';

const Layout = ({ children, user, onLogout, activeMenu }) => {
    const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);
    const [isDark, setIsDark] = useState(() => {
        return localStorage.getItem('isDark') === 'true';
    });

    useEffect(() => {
        if (isDark) {
            document.documentElement.classList.add('dark');
        } else {
            document.documentElement.classList.remove('dark');
        }
    }, [isDark]);

    const toggleTheme = () => {
        setIsDark(prev => {
            const next = !prev;
            localStorage.setItem('isDark', String(next));
            return next;
        });
    };

    return (
        <div className="relative flex h-screen w-full flex-col overflow-hidden bg-background-light dark:bg-background-dark text-slate-900 dark:text-slate-100 font-display">
            {/* Top Navigation Bar */}
            <header className="flex h-16 items-center justify-between border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-6 shrink-0">
                <div className="flex items-center gap-4">
                    <img src={logoImage} alt="Jubilant Group Logo" className="h-10 w-auto object-contain" />
                    <h2 className="text-xl font-extrabold tracking-tight mt-1 bg-gradient-to-r from-[#cbb161] via-[#d4af37] to-[#8a712c] text-transparent bg-clip-text drop-shadow-sm">JUBILANT GROUP</h2>
                </div>
                <div className="flex items-center gap-3">
                    <button
                        onClick={toggleTheme}
                        className="flex items-center justify-center rounded-lg h-10 w-10 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                    >
                        <span className="material-symbols-outlined text-slate-600 dark:text-slate-400" title='Theme Switch'>
                            {isDark ? 'light_mode' : 'dark_mode'}
                        </span>
                    </button>
                    <button className="flex items-center justify-center rounded-lg h-10 w-10 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors">
                        <span className="material-symbols-outlined text-slate-600 dark:text-slate-400" title='Notifications'>notifications</span>
                    </button>
                    <button className="flex items-center justify-center rounded-lg h-10 w-10 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors">
                        <span className="material-symbols-outlined text-slate-600 dark:text-slate-400" title='Help'>help_outline</span>
                    </button>
                </div>
            </header>

            <div className="flex flex-1 overflow-hidden">
                {/* Sidebar */}
                <aside className="w-64 border-r border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex flex-col gap-6 shrink-0">
                    <div className="flex flex-col gap-2 p-4">
                        {user?.role === 'admin' && (
                            <Link 
                                to="/dashboard" 
                                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all ${activeMenu === 'dashboard' 
                                    ? 'bg-primary text-white shadow-md shadow-primary/20' 
                                    : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'}`}
                            >
                                <span className="material-symbols-outlined">dashboard</span>
                                <span className="text-sm font-semibold">Dashboard</span>
                            </Link>
                        )}
                        <Link 
                            to="/live" 
                            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all ${activeMenu === 'live' 
                                ? 'bg-primary text-white shadow-md shadow-primary/20' 
                                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'}`}
                        >
                            <span className="material-symbols-outlined">compare_arrows</span>
                            <span className="text-sm font-semibold">Contra Match</span>
                        </Link>
                        <Link 
                            to="/consolidate" 
                            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all ${activeMenu === 'consolidate' 
                                ? 'bg-primary text-white shadow-md shadow-primary/20' 
                                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'}`}
                        >
                            <span className="material-symbols-outlined">join_inner</span>
                            <span className="text-sm font-semibold">Consolidate</span>
                        </Link>
                        <Link 
                            to="/reject-list" 
                            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all ${activeMenu === 'reject-list' 
                                ? 'bg-primary text-white shadow-md shadow-primary/20' 
                                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'}`}
                        >
                            <span className="material-symbols-outlined">assignment_late</span>
                            <span className="text-sm font-semibold">Reject List</span>
                        </Link>
                        <Link 
                            to="/incentive" 
                            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all ${activeMenu === 'incentive' 
                                ? 'bg-primary text-white shadow-md shadow-primary/20' 
                                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'}`}
                        >
                            <span className="material-symbols-outlined">workspace_premium</span>
                            <span className="text-sm font-semibold">Incentive</span>
                        </Link>
                        {user?.role === 'admin' && (
                            <>
                                <Link 
                                    to="/users" 
                                    className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all ${activeMenu === 'users' 
                                        ? 'bg-primary text-white shadow-md shadow-primary/20' 
                                        : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'}`}
                                >
                                    <span className="material-symbols-outlined">group</span>
                                    <span className="text-sm font-semibold">Users</span>
                                </Link>
                                <Link 
                                    to="/users/stats" 
                                    className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all ${activeMenu === 'statistics' 
                                        ? 'bg-primary text-white shadow-md shadow-primary/20' 
                                        : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'}`}
                                >
                                    <span className="material-symbols-outlined">analytics</span>
                                    <span className="text-sm font-semibold">Statistics</span>
                                </Link>
                            </>
                        )}
                        {/* <a className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-all" href="#">
                            <span className="material-symbols-outlined text-xl">folder</span>
                            <span className="text-sm font-medium">Recent Uploads</span>
                        </a> */}
                    </div>

                    <div className="mt-auto py-4 border-t border-slate-200 dark:border-slate-800">
                        <div className="flex items-center gap-3 px-3 py-2">
                            <div className="size-10 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center overflow-hidden shrink-0">
                                <svg viewBox="0 0 100 100" className="size-full bg-primary/5 dark:bg-slate-800">
                                    <circle cx="50" cy="38" r="22" className="fill-primary" />
                                    <path d="M 50 64 C 20 64 4 84 4 100 L 96 100 C 96 84 80 64 50 64 Z" className="fill-primary" />
                                </svg>
                            </div>
                            <div className="flex-1 overflow-hidden">
                                <p className="text-md font-bold truncate" title={user?.full_name || 'User'}>{user?.full_name || 'Test User'}</p>
                                <p className="text-[10px] text-slate-500 uppercase tracking-wider truncate" title={user?.role || 'User'}>{user?.role || 'User'}</p>
                            </div>
                            <button
                                onClick={() => setShowLogoutConfirm(true)}
                                className="text-slate-400 hover:text-red-500 transition-colors cursor-pointer"
                                title="Logout"
                            >
                                <span className="material-symbols-outlined text-xl">logout</span>
                            </button>
                        </div>
                    </div>
                </aside>

                {children}
            </div>

            {/* Logout Confirmation Modal */}
            {showLogoutConfirm && (
                <div className="fixed inset-0 z-[150] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200">
                    <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl w-full max-w-sm overflow-hidden border border-slate-200 dark:border-slate-800 p-8 flex flex-col items-center text-center animate-in zoom-in-95 duration-200">
                        <div className="w-16 h-16 rounded-full bg-red-100 dark:bg-red-500/20 text-red-500 flex items-center justify-center mb-6">
                            <span className="material-symbols-outlined text-[32px]">logout</span>
                        </div>
                        <h3 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">Ready to Leave?</h3>
                        <p className="text-slate-500 dark:text-slate-400 text-sm mb-8">
                            Are you sure you want to log out of your account?
                        </p>
                        <div className="flex gap-3 w-full">
                            <button
                                onClick={() => setShowLogoutConfirm(false)}
                                className="flex-1 px-5 py-3 rounded-xl border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 font-bold hover:bg-slate-50 dark:hover:bg-slate-800 transition-all cursor-pointer"
                            >
                                Stay
                            </button>
                            <button
                                onClick={onLogout}
                                className="flex-1 px-5 py-3 rounded-xl bg-red-500 hover:bg-red-600 text-white font-bold transition-all cursor-pointer shadow-lg shadow-red-500/25"
                            >
                                Logout
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default Layout;
