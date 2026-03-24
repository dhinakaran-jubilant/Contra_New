import React, { useState, useEffect } from 'react';
import Layout from './Layout';
import config from './config';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell
} from 'recharts';

const AdminDashboard = ({ user, onLogout, initialView }) => {
    const [isAddUserOpen, setIsAddUserOpen] = useState(false);
    const [newUser, setNewUser] = useState({
        employee_code: '',
        email_id: '',
        full_name: '',
        password: '',
        role: 'User'
    });
    const [showNewUserPassword, setShowNewUserPassword] = useState(false);
    const [addUserState, setAddUserState] = useState({ loading: false, error: '', success: '' });
    const [showSuccessPopup, setShowSuccessPopup] = useState(false);

    // Dynamic Users State
    const [users, setUsers] = useState([]);
    const [isLoadingUsers, setIsLoadingUsers] = useState(true);
    const [currentPage, setCurrentPage] = useState(1);
    const USERS_PER_PAGE = 10;
    const [deleteTarget, setDeleteTarget] = useState(null);
    const [editTarget, setEditTarget] = useState(null);
    const [editForm, setEditForm] = useState({});
    const [editState, setEditState] = useState({ loading: false, error: '' });
    const [showEditPassword, setShowEditPassword] = useState(false);
    const [showEditSuccessPopup, setShowEditSuccessPopup] = useState(false);
    const [searchQuery, setSearchQuery] = useState('');

    // Statistics State
    const [activeTab, setActiveTab] = useState(initialView || 'users');
    const [stats, setStats] = useState(null);
    const [isLoadingStats, setIsLoadingStats] = useState(false);
    const [logs, setLogs] = useState([]);
    const [isLoadingLogs, setIsLoadingLogs] = useState(false);

    useEffect(() => {
        if (initialView) {
            setActiveTab(initialView);
        }
    }, [initialView]);

    const filteredUsers = users.filter(u => {
        const query = searchQuery.toLowerCase();
        return (
            (u.full_name?.toLowerCase().includes(query)) ||
            (u.employee_code?.toString().toLowerCase().includes(query)) ||
            (u.email?.toLowerCase().includes(query)) ||
            (u.role?.toLowerCase().includes(query))
        );
    });

    const totalPages = Math.ceil(filteredUsers.length / USERS_PER_PAGE);
    const paginatedUsers = filteredUsers.slice((currentPage - 1) * USERS_PER_PAGE, currentPage * USERS_PER_PAGE);
    const startIndex = filteredUsers.length > 0 ? (currentPage - 1) * USERS_PER_PAGE + 1 : 0;
    const endIndex = Math.min(currentPage * USERS_PER_PAGE, filteredUsers.length);

    const fetchUsers = async () => {
        try {
            setIsLoadingUsers(true);
            const response = await fetch(`${config.API_BASE_URL}/api/users/`);
            const data = await response.json();
            if (response.ok && data.success) {
                setUsers(data.users);
            }
        } catch (error) {
            console.error("Failed to fetch users", error);
        } finally {
            setIsLoadingUsers(false);
        }
    };

    const fetchStats = async () => {
        try {
            setIsLoadingStats(true);
            const response = await fetch(`${config.API_BASE_URL}/api/stats/`);
            const data = await response.json();
            if (response.ok && data.success) {
                setStats(data.stats);
            }
        } catch (error) {
            console.error("Failed to fetch statistics", error);
        } finally {
            setIsLoadingStats(false);
        }
    };

    const fetchLogs = async () => {
        try {
            setIsLoadingLogs(true);
            const response = await fetch(`${config.API_BASE_URL}/api/get_processing_logs/`);
            const data = await response.json();
            if (response.ok) {
                setLogs(data);
            }
        } catch (error) {
            console.error("Failed to fetch logs", error);
        } finally {
            setIsLoadingLogs(false);
        }
    };


    useEffect(() => {
        if (activeTab === 'stats') {
            fetchStats();
            fetchLogs();
        }
    }, [activeTab]);

    useEffect(() => {
        fetchUsers();
    }, []);

    const handleAddUser = async (e) => {
        e.preventDefault();
        setAddUserState({ loading: true, error: '', success: '' });

        try {
            const response = await fetch(`${config.API_BASE_URL}/api/users/add/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(newUser),
            });

            const data = await response.json();

            if (response.ok && data.success) {
                setIsAddUserOpen(false);
                setNewUser({
                    employee_code: '',
                    email_id: '',
                    full_name: '',
                    password: '',
                    role: 'User'
                });
                setAddUserState({ loading: false, error: '', success: '' });
                setShowSuccessPopup(true);
                setTimeout(() => {
                    setShowSuccessPopup(false);
                }, 3000);
                fetchUsers();
                setCurrentPage(1);
            } else {
                setAddUserState({ loading: false, error: data.message || 'Failed to create user.', success: '' });
            }
        } catch (error) {
            setAddUserState({ loading: false, error: 'An error occurred while communicating with the server.', success: '' });
        }
    };

    const handleDeleteUser = async () => {
        if (!deleteTarget) return;
        try {
            const response = await fetch(`${config.API_BASE_URL}/api/users/delete/${deleteTarget.employee_code}/`, {
                method: 'DELETE',
            });
            const data = await response.json();
            if (response.ok && data.success) {
                setDeleteTarget(null);
                fetchUsers();
                setCurrentPage(p => {
                    const remaining = filteredUsers.length - 1;
                    const newTotalPages = Math.ceil(remaining / USERS_PER_PAGE);
                    return p > newTotalPages ? Math.max(newTotalPages, 1) : p;
                });
            }
        } catch (error) {
            console.error('Failed to delete user', error);
        }
    };

    const openEditModal = (u) => {
        setEditTarget(u);
        setEditForm({
            full_name: u.full_name,
            email_id: u.email,
            role: u.role ? u.role.charAt(0).toUpperCase() + u.role.slice(1) : 'User',
            is_active: u.is_active,
            password: ''
        });
        setEditState({ loading: false, error: '' });
        setShowEditPassword(false);
    };

    const handleEditUser = async () => {
        if (!editTarget) return;
        setEditState({ loading: true, error: '' });
        try {
            const response = await fetch(`${config.API_BASE_URL}/api/users/update/${editTarget.employee_code}/`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(editForm),
            });
            const data = await response.json();
            if (response.ok && data.success) {
                setEditTarget(null);
                fetchUsers();
                setShowEditSuccessPopup(true);
                setTimeout(() => setShowEditSuccessPopup(false), 3000);
            } else {
                setEditState({ loading: false, error: data.message || 'Failed to update user.' });
            }
        } catch (error) {
            setEditState({ loading: false, error: 'An error occurred.' });
        }
    };

    return (
        <>
            <Layout user={user} onLogout={onLogout} activeMenu={activeTab === 'stats' ? 'statistics' : 'users'}>
                <main className="flex-1 flex flex-col overflow-hidden bg-background-light dark:bg-background-dark text-slate-900 dark:text-slate-100">
                    <div className="flex-1 flex flex-col p-6 overflow-hidden">
                        <div className="w-full flex-1 flex flex-col gap-6 overflow-hidden">
                            {activeTab === 'users' ? (
                                <>
                                    {/* Page Title & Actions */}
                                    <div className="flex flex-col md:flex-row md:items-center gap-4 shrink-0 justify-between">
                                        <div className="relative flex-1 max-w-[50%]">
                                            <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">search</span>
                                            <input
                                                className="w-full h-10 pl-10 pr-4 bg-slate-50 dark:bg-slate-800 rounded-lg focus:outline-none text-sm"
                                                placeholder="Search users by name, email, or role..."
                                                type="text"
                                                value={searchQuery}
                                                onChange={(e) => setSearchQuery(e.target.value)}
                                            />
                                        </div>
                                        <div className="flex items-center gap-3">
                                            <button
                                                onClick={() => setIsAddUserOpen(true)}
                                                className="inline-flex h-10 items-center justify-center gap-2 bg-primary text-white px-4 rounded-lg font-bold hover:bg-primary/90 transition-all cursor-pointer"
                                                title="Add New User"
                                            >
                                                <span className="material-symbols-outlined text-[20px]">person_add</span>
                                                <span className="text-sm">New User</span>
                                            </button>
                                        </div>
                                    </div>

                                    {/* Users Table */}
                                    <div className="flex-1 flex flex-col bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
                                        {/* Fixed Header */}
                                        <div className="shrink-0 overflow-x-auto bg-slate-50/95 dark:bg-slate-800/95 border-b border-slate-100 dark:border-slate-800 scrollbar-slim">
                                            <table className="w-full text-left border-collapse table-fixed">
                                                <thead>
                                                    <tr>
                                                        <th className="w-[20%] px-6 py-4 text-xs font-bold uppercase tracking-wider text-slate-500">Name</th>
                                                        <th className="w-[15%] px-6 py-4 text-xs font-bold uppercase tracking-wider text-slate-500">Employee Code</th>
                                                        <th className="w-[30%] px-6 py-4 text-xs font-bold uppercase tracking-wider text-slate-500">Email</th>
                                                        <th className="w-[10%] px-6 py-4 text-xs font-bold uppercase tracking-wider text-slate-500">Role</th>
                                                        <th className="w-[10%] px-6 py-4 text-xs font-bold uppercase tracking-wider text-slate-500">Status</th>
                                                        <th className="w-[15%] px-6 py-4 text-xs font-bold uppercase tracking-wider text-slate-500 text-right">Actions</th>
                                                    </tr>
                                                </thead>
                                            </table>
                                        </div>

                                        {/* Scrollable Body */}
                                        <div className="flex-1 overflow-x-auto overflow-y-auto scroll-smooth scrollbar-slim">
                                            <table className="w-full text-left border-collapse table-fixed">
                                                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                                                    {isLoadingUsers ? (
                                                        <tr>
                                                            <td colSpan="6" className="px-6 py-8 text-center text-slate-500">
                                                                <div className="flex items-center justify-center gap-2">
                                                                    <span className="material-symbols-outlined animate-spin">progress_activity</span>
                                                                    Loading users...
                                                                </div>
                                                            </td>
                                                        </tr>
                                                    ) : filteredUsers.length === 0 ? (
                                                        <tr>
                                                            <td colSpan="6" className="px-6 py-8 text-center text-slate-500">
                                                                No users found.
                                                            </td>
                                                        </tr>
                                                    ) : (
                                                        paginatedUsers.map((u, index) => (
                                                            <tr key={u.employee_code || index} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition-colors">
                                                                <td className="w-[20%] px-6 py-2">
                                                                    <div className="flex items-center gap-3">
                                                                        <div className="w-8 h-8 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-xs uppercase">
                                                                            {u.full_name ? u.full_name.substring(0, 2) : 'US'}
                                                                        </div>
                                                                        <span className="font-semibold text-slate-900 dark:text-white truncate">{u.full_name}</span>
                                                                    </div>
                                                                </td>
                                                                <td className="w-[15%] px-6 py-2 text-slate-700 dark:text-slate-300 text-sm font-mono font-bold">{u.employee_code}</td>
                                                                <td className="w-[30%] px-6 py-2 text-slate-600 dark:text-slate-400 text-sm truncate">{u.email}</td>
                                                                <td className="w-[10%] px-6 py-2">
                                                                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${u.role === 'admin'
                                                                        ? 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300'
                                                                        : u.role === 'staff'
                                                                            ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300'
                                                                            : 'bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300'
                                                                        }`}>
                                                                        {u.role ? u.role.charAt(0).toUpperCase() + u.role.slice(1) : 'User'}
                                                                    </span>
                                                                </td>
                                                                <td className="w-[10%] px-6 py-2">
                                                                    <span className={`inline-flex items-center gap-1 text-xs font-bold ${u.is_active ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-400 dark:text-slate-500'}`}>
                                                                        <span className={`w-1.5 h-1.5 rounded-full ${u.is_active ? 'bg-emerald-500' : 'bg-slate-300 dark:bg-slate-600'}`}></span>
                                                                        {u.is_active ? 'Active' : 'Inactive'}
                                                                    </span>
                                                                </td>
                                                                <td className="w-[15%] px-6 py-2 text-right">
                                                                    <div className="flex justify-end gap-2 text-right">
                                                                        <button
                                                                            className="p-1.5 text-slate-400 hover:text-primary transition-colors"
                                                                            title="Edit"
                                                                            onClick={() => openEditModal(u)}
                                                                        >
                                                                            <span className="material-symbols-outlined text-[20px]">edit</span>
                                                                        </button>
                                                                        <button
                                                                            className="p-1.5 text-slate-400 hover:text-red-500 transition-colors"
                                                                            title="Delete"
                                                                            onClick={() => setDeleteTarget({ employee_code: u.employee_code, full_name: u.full_name })}
                                                                        >
                                                                            <span className="material-symbols-outlined text-[20px]">delete</span>
                                                                        </button>
                                                                    </div>
                                                                </td>
                                                            </tr>
                                                        ))
                                                    )}
                                                </tbody>
                                            </table>
                                        </div>
                                        {/* Table Footer / Pagination */}
                                        <div className="px-6 py-3 bg-slate-50 dark:bg-slate-800/80 backdrop-blur-sm border-t border-slate-100 dark:border-slate-800 flex items-center justify-between shrink-0">
                                            <p className="text-sm text-slate-500">
                                                Showing {startIndex} to {endIndex} of {filteredUsers.length} users
                                            </p>
                                            {totalPages > 1 && (
                                                <div className="flex items-center gap-2">
                                                    <button
                                                        onClick={() => setCurrentPage(p => Math.max(p - 1, 1))}
                                                        disabled={currentPage === 1}
                                                        className="p-1 rounded border border-slate-200 dark:border-slate-700 hover:bg-white dark:hover:bg-slate-900 disabled:opacity-50 transition-colors"
                                                    >
                                                        <span className="material-symbols-outlined text-sm">chevron_left</span>
                                                    </button>
                                                    {Array.from({ length: totalPages }, (_, i) => i + 1).map(page => (
                                                        <button
                                                            key={page}
                                                            onClick={() => setCurrentPage(page)}
                                                            className={`w-8 h-8 rounded text-sm font-bold transition-colors ${page === currentPage
                                                                ? 'bg-primary text-white'
                                                                : 'hover:bg-white dark:hover:bg-slate-900 text-slate-600 dark:text-slate-300 font-medium'
                                                                }`}
                                                        >
                                                            {page}
                                                        </button>
                                                    ))}
                                                    <button
                                                        onClick={() => setCurrentPage(p => Math.min(p + 1, totalPages))}
                                                        disabled={currentPage === totalPages}
                                                        className="p-1 rounded border border-slate-200 dark:border-slate-700 hover:bg-white dark:hover:bg-slate-900 disabled:opacity-50 transition-colors"
                                                    >
                                                        <span className="material-symbols-outlined text-sm">chevron_right</span>
                                                    </button>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                </>
                            ) : (
                                <div className="flex-1 flex flex-col gap-6 overflow-y-auto pr-1 scrollbar-slim">
                                    {/* Statistics View */}
                                    <div className="flex items-center justify-between shrink-0">
                                        <div>
                                            <h2 className="text-2xl font-bold bg-gradient-to-r from-slate-900 to-slate-700 dark:from-white dark:to-slate-300 text-transparent bg-clip-text">System Statistics</h2>
                                            <p className="text-slate-500 text-sm">Real-time overview of your application usage</p>
                                        </div>
                                        <button
                                            onClick={() => { fetchStats(); fetchLogs(); }}
                                            className={`flex items-center gap-2 px-4 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl hover:bg-slate-50 dark:hover:bg-slate-800 transition-all font-bold text-sm shadow-sm ${(isLoadingStats || isLoadingLogs) ? 'opacity-50 pointer-events-none' : ''}`}
                                        >
                                            <span className={`material-symbols-outlined text-[18px] ${(isLoadingStats || isLoadingLogs) ? 'animate-spin' : ''}`}>refresh</span>
                                            Refresh
                                        </button>
                                    </div>


                                    {/* Summary Cards */}
                                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-4 shrink-0">
                                        <div className="bg-white dark:bg-slate-900 rounded-2xl p-4 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center gap-3 transition-transform hover:scale-[1.02]">
                                            <div className="size-10 rounded-xl bg-amber-100 dark:bg-amber-500/10 text-amber-600 flex items-center justify-center shrink-0">
                                                <span className="material-symbols-outlined text-[20px]">inventory_2</span>
                                            </div>
                                            <div className="min-w-0">
                                                <p className="text-[9px] text-slate-500 font-bold uppercase tracking-wider truncate">Total Files</p>
                                                <h4 className="text-lg font-black text-amber-600 tabular-nums">{stats?.total_processed || 0}</h4>
                                            </div>
                                        </div>

                                        <div className="bg-white dark:bg-slate-900 rounded-2xl p-4 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center gap-3 transition-transform hover:scale-[1.02] border-l-emerald-500">
                                            <div className="size-10 rounded-xl bg-emerald-100 dark:bg-emerald-500/10 text-emerald-600 flex items-center justify-center shrink-0">
                                                <span className="material-symbols-outlined text-[20px]">today</span>
                                            </div>
                                            <div className="min-w-0">
                                                <p className="text-[9px] text-slate-500 font-bold uppercase tracking-wider truncate">Today's Files</p>
                                                <h4 className="text-lg font-black text-emerald-600 tabular-nums">{stats?.processed_today || 0}</h4>
                                            </div>
                                        </div>

                                        <div className="bg-white dark:bg-slate-900 rounded-2xl p-4 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center gap-3 transition-transform hover:scale-[1.02]">
                                            <div className="size-10 rounded-xl bg-blue-100 dark:bg-blue-500/10 text-blue-600 flex items-center justify-center shrink-0">
                                                <span className="material-symbols-outlined text-[20px]">compare_arrows</span>
                                            </div>
                                            <div className="min-w-0">
                                                <p className="text-[9px] text-slate-500 font-bold uppercase tracking-wider truncate">S/W Contra</p>
                                                <h4 className="text-lg font-black text-blue-600 tabular-nums">{stats?.total_sw_contra || 0}</h4>
                                            </div>
                                        </div>

                                        <div className="bg-white dark:bg-slate-900 rounded-2xl p-4 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center gap-3 transition-transform hover:scale-[1.02]">
                                            <div className="size-10 rounded-xl bg-emerald-100 dark:bg-emerald-500/10 text-emerald-600 flex items-center justify-center shrink-0">
                                                <span className="material-symbols-outlined text-[20px]">verified</span>
                                            </div>
                                            <div className="min-w-0 flex-1">
                                                <div className="flex items-center justify-between">
                                                    <p className="text-[9px] text-slate-500 font-bold uppercase tracking-wider truncate">Final Contra</p>
                                                    <span className={`text-[8px] font-black text-white px-1 rounded-sm transition-colors duration-300 ${(stats?.contra_efficiency || 0) >= 90 ? 'bg-emerald-500' :
                                                            (stats?.contra_efficiency || 0) >= 80 ? 'bg-blue-500' :
                                                                (stats?.contra_efficiency || 0) >= 50 ? 'bg-amber-500' : 'bg-rose-500'
                                                        }`}>{stats?.contra_efficiency || 0}%</span>
                                                </div>
                                                <h4 className={`text-lg font-black tabular-nums transition-colors duration-300 ${(stats?.contra_efficiency || 0) >= 90 ? 'text-emerald-600' :
                                                        (stats?.contra_efficiency || 0) >= 80 ? 'text-blue-600' :
                                                            (stats?.contra_efficiency || 0) >= 50 ? 'text-amber-600' : 'text-rose-600'
                                                    }`}>{stats?.total_final_contra || 0}</h4>
                                            </div>
                                        </div>

                                        <div className="bg-white dark:bg-slate-900 rounded-2xl p-4 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center gap-3 transition-transform hover:scale-[1.02]">
                                            <div className="size-10 rounded-xl bg-purple-100 dark:bg-purple-500/10 text-purple-600 flex items-center justify-center shrink-0">
                                                <span className="material-symbols-outlined text-[20px]">keyboard_return</span>
                                            </div>
                                            <div className="min-w-0">
                                                <p className="text-[9px] text-slate-500 font-bold uppercase tracking-wider truncate">S/W Return</p>
                                                <h4 className="text-lg font-black text-purple-600 tabular-nums">{stats?.total_sw_return || 0}</h4>
                                            </div>
                                        </div>

                                        <div className="bg-white dark:bg-slate-900 rounded-2xl p-4 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center gap-3 transition-transform hover:scale-[1.02]">
                                            <div className="size-10 rounded-xl bg-rose-100 dark:bg-rose-500/10 text-rose-600 flex items-center justify-center shrink-0">
                                                <span className="material-symbols-outlined text-[20px]">assignment_return</span>
                                            </div>
                                            <div className="min-w-0 flex-1">
                                                <div className="flex items-center justify-between">
                                                    <p className="text-[9px] text-slate-500 font-bold uppercase tracking-wider truncate">Final Return</p>
                                                    <span className={`text-[8px] font-black text-white px-1 rounded-sm transition-colors duration-300 ${(stats?.return_efficiency || 0) >= 90 ? 'bg-emerald-500' :
                                                            (stats?.return_efficiency || 0) >= 80 ? 'bg-blue-500' :
                                                                (stats?.return_efficiency || 0) >= 50 ? 'bg-amber-500' : 'bg-rose-500'
                                                        }`}>{stats?.return_efficiency || 0}%</span>
                                                </div>
                                                <h4 className={`text-lg font-black tabular-nums transition-colors duration-300 ${(stats?.return_efficiency || 0) >= 90 ? 'text-emerald-600' :
                                                        (stats?.return_efficiency || 0) >= 80 ? 'text-blue-600' :
                                                            (stats?.return_efficiency || 0) >= 50 ? 'text-amber-600' : 'text-rose-600'
                                                    }`}>{stats?.total_final_return || 0}</h4>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Monthly Trends Chart */}
                                    <div className="bg-white dark:bg-slate-900 rounded-2xl p-6 border border-slate-200 dark:border-slate-800 shadow-sm shrink-0">
                                        <div className="flex items-center justify-between mb-6">
                                            <h3 className="font-bold text-slate-900 dark:text-white flex items-center gap-2">
                                                <span className="material-symbols-outlined text-primary">bar_chart</span>
                                                Monthly Performance Trends
                                            </h3>
                                            <div className="flex items-center gap-4 text-[10px] font-bold uppercase tracking-wider">
                                                <div className="flex items-center gap-1.5">
                                                    <span className="w-2.5 h-2.5 rounded-full bg-blue-500"></span>
                                                    <span className="text-slate-500">Contra %</span>
                                                </div>
                                                <div className="flex items-center gap-1.5">
                                                    <span className="w-2.5 h-2.5 rounded-full bg-purple-500"></span>
                                                    <span className="text-slate-500">Return %</span>
                                                </div>
                                            </div>
                                        </div>
                                        <div className="h-[250px] w-full">
                                            <ResponsiveContainer width="100%" height="100%">
                                                <BarChart
                                                    data={stats?.monthly_trends || []}
                                                    margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
                                                    barGap={8}
                                                >
                                                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" opacity={0.5} />
                                                    <XAxis
                                                        dataKey="name"
                                                        axisLine={false}
                                                        tickLine={false}
                                                        tick={{ fill: '#94A3B8', fontSize: 10, fontWeight: 700 }}
                                                        dy={10}
                                                    />
                                                    <YAxis
                                                        axisLine={false}
                                                        tickLine={false}
                                                        tick={{ fill: '#94A3B8', fontSize: 10, fontWeight: 700 }}
                                                        domain={[0, 100]}
                                                        tickCount={6}
                                                    />
                                                    <Tooltip
                                                        cursor={false}
                                                        content={({ active, payload, label }) => {
                                                            if (active && payload && payload.length) {
                                                                return (
                                                                    <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-3 rounded-xl shadow-xl">
                                                                        <p className="text-[10px] font-black text-slate-400 mb-2 uppercase tracking-widest">{label}</p>
                                                                        <div className="space-y-1.5">
                                                                            <div className="flex items-center justify-between gap-6">
                                                                                <span className="text-xs font-bold text-slate-600 dark:text-slate-400">Contra Efficiency</span>
                                                                                <span className="text-xs font-black text-blue-600">{payload[0].value}%</span>
                                                                            </div>
                                                                            <div className="flex items-center justify-between gap-6">
                                                                                <span className="text-xs font-bold text-slate-600 dark:text-slate-400">Return Efficiency</span>
                                                                                <span className="text-xs font-black text-purple-600">{payload[1].value}%</span>
                                                                            </div>
                                                                            <div className="flex items-center justify-between gap-6 pt-1.5 border-t border-slate-100 dark:border-slate-700">
                                                                                <span className="text-xs font-bold text-slate-600 dark:text-slate-400">Files Processed</span>
                                                                                <span className="text-xs font-black text-slate-900 dark:text-white">{stats?.monthly_trends?.find(t => t.name === label)?.files || 0}</span>
                                                                            </div>
                                                                        </div>
                                                                    </div>
                                                                );
                                                            }
                                                            return null;
                                                        }}
                                                    />
                                                    <Bar
                                                        dataKey="contra"
                                                        fill="#3B82F6"
                                                        radius={[4, 4, 0, 0]}
                                                        barSize={32}
                                                        animationDuration={1500}
                                                    />
                                                    <Bar
                                                        dataKey="return"
                                                        fill="#8B5CF6"
                                                        radius={[4, 4, 0, 0]}
                                                        barSize={32}
                                                        animationDuration={1500}
                                                    />
                                                </BarChart>
                                            </ResponsiveContainer>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </main>

                {/* Modals */}
                {isAddUserOpen && (
                    <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
                        <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-xl w-full max-w-md overflow-hidden border border-slate-200 dark:border-slate-800 flex flex-col">
                            <div className="flex items-center justify-between p-4 border-b border-slate-100 dark:border-slate-800">
                                <h3 className="text-xl font-bold text-slate-900 dark:text-white">Add New User</h3>
                                <button
                                    onClick={() => setIsAddUserOpen(false)}
                                    className="flex items-center justify-center size-8 rounded-full text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 transition-colors cursor-pointer"
                                >
                                    <span className="material-symbols-outlined text-[20px]">close</span>
                                </button>
                            </div>
                            <div className="p-8 overflow-y-auto flex-1">
                                {addUserState.error && (
                                    <div className="mb-4 p-3 bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 text-red-600 dark:text-red-400 rounded-lg text-sm text-center font-medium">
                                        {addUserState.error}
                                    </div>
                                )}
                                <form className="grid grid-cols-1 gap-4" onSubmit={handleAddUser}>
                                    <div>
                                        <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5 uppercase tracking-wider">Employee Code</label>
                                        <input
                                            type="text"
                                            value={newUser.employee_code}
                                            onChange={(e) => setNewUser({ ...newUser, employee_code: e.target.value })}
                                            className="w-full px-4 py-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary focus:outline-none transition-all"
                                            placeholder="e.g. EMP1024"
                                            required
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5 uppercase tracking-wider">Email ID</label>
                                        <input
                                            type="email"
                                            value={newUser.email_id}
                                            onChange={(e) => setNewUser({ ...newUser, email_id: e.target.value })}
                                            className="w-full px-4 py-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary focus:outline-none transition-all"
                                            placeholder="user@company.com"
                                            required
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5 uppercase tracking-wider">Full Name</label>
                                        <input
                                            type="text"
                                            value={newUser.full_name}
                                            onChange={(e) => setNewUser({ ...newUser, full_name: e.target.value })}
                                            className="w-full px-4 py-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary focus:outline-none transition-all"
                                            placeholder="John Doe"
                                            required
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5 uppercase tracking-wider">Temporary Password</label>
                                        <div className="relative group">
                                            <input
                                                type={showNewUserPassword ? 'text' : 'password'}
                                                value={newUser.password}
                                                onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
                                                className="w-full pl-4 pr-12 py-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary focus:outline-none transition-all"
                                                placeholder="••••••••"
                                                required
                                            />
                                            <button
                                                type="button"
                                                onClick={() => setShowNewUserPassword(!showNewUserPassword)}
                                                className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors"
                                            >
                                                <span className="material-symbols-outlined text-[20px]">
                                                    {showNewUserPassword ? 'visibility_off' : 'visibility'}
                                                </span>
                                            </button>
                                        </div>
                                    </div>
                                </form>
                            </div>
                            <div className="p-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/50 flex justify-end gap-3 shrink-0">
                                <button
                                    onClick={() => setIsAddUserOpen(false)}
                                    className="px-5 py-2.5 rounded-lg text-slate-600 dark:text-slate-300 font-semibold hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors cursor-pointer"
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={handleAddUser}
                                    disabled={addUserState.loading}
                                    className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg bg-primary text-white font-bold hover:bg-primary/90 transition-all shadow-md shadow-primary/20 cursor-pointer disabled:opacity-70"
                                >
                                    {addUserState.loading ? 'Saving...' : 'Save User'}
                                </button>
                            </div>
                        </div>
                    </div>
                )}

                {showSuccessPopup && (
                    <div className="fixed inset-0 z-[130] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
                        <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-xl w-full max-w-sm overflow-hidden border border-slate-200 dark:border-slate-800 p-8 flex flex-col items-center text-center">
                            <div className="w-16 h-16 rounded-full bg-emerald-100 dark:bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 flex items-center justify-center mb-5">
                                <span className="material-symbols-outlined text-[32px]">check_circle</span>
                            </div>
                            <h3 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">Success!</h3>
                            <p className="text-slate-600 dark:text-slate-400 text-sm mb-8">User has been created successfully.</p>
                            <button
                                onClick={() => setShowSuccessPopup(false)}
                                className="w-full px-5 py-3 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-bold transition-colors cursor-pointer shadow-md shadow-emerald-600/20"
                            >
                                OK
                            </button>
                        </div>
                    </div>
                )}

                {editTarget && (
                    <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
                        <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-xl w-full max-w-md overflow-hidden border border-slate-200 dark:border-slate-800 flex flex-col">
                            <div className="flex items-center justify-between p-4 border-b border-slate-100 dark:border-slate-800">
                                <h3 className="text-xl font-bold text-slate-900 dark:text-white">Edit User</h3>
                                <button
                                    onClick={() => setEditTarget(null)}
                                    className="flex items-center justify-center size-8 rounded-full text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 transition-colors cursor-pointer"
                                >
                                    <span className="material-symbols-outlined text-[20px]">close</span>
                                </button>
                            </div>
                            <div className="p-6 overflow-y-auto flex-1">
                                {editState.error && (
                                    <div className="mb-4 p-3 bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 text-red-600 dark:text-red-400 rounded-lg text-sm text-center font-medium">
                                        {editState.error}
                                    </div>
                                )}
                                <div className="mb-3">
                                    <label className="block text-xs font-semibold text-slate-500 mb-1 uppercase tracking-wider">Employee Code</label>
                                    <p className="px-4 py-2.5 bg-slate-100 dark:bg-slate-800 rounded-lg text-sm text-slate-500 font-mono font-bold tracking-tight">{editTarget.employee_code}</p>
                                </div>
                                <form className="flex flex-col gap-4">
                                    <div>
                                        <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5 uppercase tracking-wider">Full Name</label>
                                        <input
                                            type="text"
                                            value={editForm.full_name || ''}
                                            onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })}
                                            className="w-full px-4 py-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary focus:outline-none transition-all"
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5 uppercase tracking-wider">Email ID</label>
                                        <input
                                            type="email"
                                            value={editForm.email_id || ''}
                                            onChange={(e) => setEditForm({ ...editForm, email_id: e.target.value })}
                                            className="w-full px-4 py-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary focus:outline-none transition-all"
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5 uppercase tracking-wider">Reset Password <span className="text-slate-400 font-normal normal-case">(optional)</span></label>
                                        <div className="relative">
                                            <input
                                                type={showEditPassword ? 'text' : 'password'}
                                                value={editForm.password || ''}
                                                onChange={(e) => setEditForm({ ...editForm, password: e.target.value })}
                                                className="w-full pl-4 pr-12 py-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary focus:outline-none transition-all"
                                                placeholder="Leave blank to keep current"
                                            />
                                            <button
                                                type="button"
                                                onClick={() => setShowEditPassword(!showEditPassword)}
                                                className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors"
                                            >
                                                <span className="material-symbols-outlined text-[20px]">{showEditPassword ? 'visibility_off' : 'visibility'}</span>
                                            </button>
                                        </div>
                                    </div>
                                    <div className="flex gap-4">
                                        <div className="flex-1">
                                            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5 uppercase tracking-wider">Role</label>
                                            <select
                                                value={editForm.role || 'User'}
                                                onChange={(e) => setEditForm({ ...editForm, role: e.target.value })}
                                                className="w-full px-4 py-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary focus:outline-none transition-all appearance-none cursor-pointer"
                                            >
                                                <option value="Admin">Admin</option>
                                                <option value="Staff">Staff</option>
                                                <option value="User">User</option>
                                            </select>
                                        </div>
                                        <div className="flex-1">
                                            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5 uppercase tracking-wider">Status</label>
                                            <select
                                                value={editForm.is_active ? 'true' : 'false'}
                                                onChange={(e) => setEditForm({ ...editForm, is_active: e.target.value === 'true' })}
                                                className="w-full px-4 py-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary focus:outline-none transition-all appearance-none cursor-pointer"
                                            >
                                                <option value="true">Active</option>
                                                <option value="false">Inactive</option>
                                            </select>
                                        </div>
                                    </div>
                                </form>
                            </div>
                            <div className="p-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/50 flex justify-end gap-3">
                                <button
                                    onClick={() => setEditTarget(null)}
                                    className="px-5 py-2.5 rounded-lg text-slate-600 dark:text-slate-300 font-semibold hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors cursor-pointer"
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={handleEditUser}
                                    disabled={editState.loading}
                                    className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg bg-primary text-white font-bold hover:bg-primary/90 transition-all shadow-md shadow-primary/20 cursor-pointer disabled:opacity-70"
                                >
                                    {editState.loading ? 'Saving...' : 'Save Changes'}
                                </button>
                            </div>
                        </div>
                    </div>
                )}

                {showEditSuccessPopup && (
                    <div className="fixed inset-0 z-[130] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
                        <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-xl w-full max-w-sm overflow-hidden border border-slate-200 dark:border-slate-800 p-8 flex flex-col items-center text-center">
                            <div className="w-15 h-15 rounded-full bg-emerald-100 dark:bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 flex items-center justify-center mb-5">
                                <span className="material-symbols-outlined text-[30px]">check_circle</span>
                            </div>
                            <h3 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">Updated!</h3>
                            <p className="text-slate-600 dark:text-slate-400 text-sm mb-8">User details have been updated successfully.</p>
                            <button
                                onClick={() => setShowEditSuccessPopup(false)}
                                className="w-full px-5 py-3 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-bold transition-colors cursor-pointer shadow-md shadow-emerald-600/20"
                            >
                                OK
                            </button>
                        </div>
                    </div>
                )}

                {deleteTarget && (
                    <div className="fixed inset-0 z-[140] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
                        <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-xl w-full max-w-sm overflow-hidden border border-slate-200 dark:border-slate-800 p-8 flex flex-col items-center text-center">
                            <div className="w-14 h-14 rounded-full bg-red-100 dark:bg-red-500/20 text-red-500 flex items-center justify-center mb-5">
                                <span className="material-symbols-outlined text-[28px]">delete_forever</span>
                            </div>
                            <h3 className="text-xl font-bold text-slate-900 dark:text-white mb-2">Delete User?</h3>
                            <p className="text-slate-500 dark:text-slate-400 text-sm mb-8">
                                Are you sure you want to delete <span className="font-semibold text-slate-900 dark:text-white">{deleteTarget.full_name}</span>? This action cannot be undone.
                            </p>
                            <div className="flex gap-3 w-full">
                                <button
                                    onClick={() => setDeleteTarget(null)}
                                    className="flex-1 px-5 py-2.5 rounded-lg border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 font-semibold hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={handleDeleteUser}
                                    className="flex-1 px-5 py-2.5 rounded-lg bg-red-500 hover:bg-red-600 text-white font-bold transition-colors cursor-pointer shadow-md shadow-red-500/20"
                                >
                                    Delete
                                </button>
                            </div>
                        </div>
                    </div>
                )}
            </Layout>
        </>
    );
};

export default AdminDashboard;
