import React, { useState, useEffect } from 'react';
import Layout from './Layout';
import { Link } from 'react-router-dom';
import config from './config';

const HomeDashboard = ({ user, onLogout }) => {
    const [stats, setStats] = useState(null);
    const [logs, setLogs] = useState([]);
    const [loading, setLoading] = useState(true);
    const [currentPage, setCurrentPage] = useState(1);
    const itemsPerPage = 20;

    const totalPages = Math.ceil(logs.length / itemsPerPage);
    const startIndex = (currentPage - 1) * itemsPerPage;
    const currentLogs = logs.slice(startIndex, startIndex + itemsPerPage);

    const formatNumber = (num) => {
        if (num === null || num === undefined) return '0';
        return Number(num).toLocaleString('en-IN');
    };

    useEffect(() => {
        const fetchData = async () => {
            try {
                setLoading(true);
                // Fetch stats and logs in parallel
                const [statsRes, logsRes] = await Promise.all([
                    fetch(`${config.API_BASE_URL}/api/stats/`),
                    fetch(`${config.API_BASE_URL}/api/get_processing_logs/`)
                ]);

                const statsData = await statsRes.json();
                const logsData = await logsRes.json();

                if (statsData.success) {
                    setStats(statsData.stats);
                }

                if (Array.isArray(logsData) && logsData.length > 0) {
                    // Identify the latest date available across all logs
                    const dates = logsData.map(log => new Date(log.processed_at).toLocaleDateString());
                    const latestDateString = dates.sort().reverse()[0];

                    // Filter logs to only include entries from that exact latest date string
                    const filteredLogs = logsData.filter(log =>
                        new Date(log.processed_at).toLocaleDateString() === latestDateString
                    );

                    setLogs(filteredLogs);
                } else if (Array.isArray(logsData)) {
                    setLogs([]);
                }
            } catch (error) {
                console.error("Failed to fetch dashboard data", error);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    return (
        <Layout user={user} onLogout={onLogout} activeMenu="dashboard">
            <main className="flex-1 overflow-y-auto bg-slate-50 dark:bg-background-dark p-6 scrollbar-slim">
                <div className="mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700">

                    {/* Main Metric Section */}
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        {/* Total Files Card */}
                        <div className="bg-white dark:bg-slate-900 p-8 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm flex items-center gap-6 transition-all duration-300 hover:shadow-2xl hover:-translate-y-2 dark:hover:shadow-slate-500/10 group">
                            <div className="size-16 rounded-2xl bg-amber-500/10 text-amber-500 flex items-center justify-center group-hover:bg-amber-500 group-hover:text-white transition-all duration-300 shrink-0">
                                <span className="material-symbols-outlined text-4xl font-bold">inventory_2</span>
                            </div>
                            <div className="min-w-0">
                                <h4 className="text-xs font-black text-slate-400 uppercase tracking-widest mb-1">Total Processed from 12-12-2025</h4>
                                <div className="flex items-baseline gap-3">
                                    <span className="text-5xl font-black text-slate-900 dark:text-white tabular-nums tracking-normal">
                                        {formatNumber(stats?.total_processed)}
                                    </span>
                                    <span className="text-[10px] text-emerald-500 font-bold uppercase bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/10">All-time</span>
                                </div>
                            </div>
                        </div>

                        {/* Today's Files Card */}
                        <div className="bg-white dark:bg-slate-900 p-8 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm flex items-center gap-6 transition-all duration-300 hover:shadow-2xl hover:-translate-y-2 dark:hover:shadow-emerald-500/10 group">
                            <div className="size-16 rounded-2xl bg-emerald-500/10 text-emerald-500 flex items-center justify-center group-hover:bg-emerald-500 group-hover:text-white transition-all duration-300 shrink-0">
                                <span className="material-symbols-outlined text-4xl font-bold">today</span>
                            </div>
                            <div className="min-w-0">
                                <h4 className="text-xs font-black text-slate-400 uppercase tracking-widest mb-1">Today Processed</h4>
                                <div className="flex items-baseline gap-3">
                                    <span className="text-5xl font-black text-slate-900 dark:text-white tabular-nums tracking-normal">
                                        {formatNumber(stats?.processed_today)}
                                    </span>
                                    <span className="text-[10px] text-emerald-500 font-bold uppercase bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/10 animate-pulse">Live</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Detailed Processing Metrics */}
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                        {/* Contra Match Metrics */}
                        <div className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col gap-2 transition-all duration-300 hover:shadow-lg hover:-translate-y-1 dark:hover:shadow-slate-500/5">
                            <div className="flex items-center justify-between mb-2">
                                <span className="material-symbols-outlined text-blue-500 bg-blue-500/10 p-2 rounded-lg">compare_arrows</span>
                                <span className="text-sm font-black text-slate-400 uppercase tracking-widest">S/W Contra</span>
                            </div>
                            <h4 className="text-3xl font-black text-slate-900 dark:text-white tabular-nums">{formatNumber(stats?.total_sw_contra)}</h4>
                            <p className="text-[10px] text-slate-500 font-bold">Initial Software Count</p>
                        </div>

                        <div className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col gap-2 transition-all duration-300 hover:shadow-lg hover:-translate-y-1 dark:hover:shadow-slate-500/5">
                            <div className="flex items-center justify-between mb-2">
                                <span className={`material-symbols-outlined p-2 rounded-lg transition-colors duration-300 ${(stats?.contra_efficiency || 0) >= 90 ? 'text-emerald-500 bg-emerald-500/10' :
                                        (stats?.contra_efficiency || 0) >= 80 ? 'text-blue-500 bg-blue-500/10' :
                                            (stats?.contra_efficiency || 0) >= 50 ? 'text-amber-500 bg-amber-500/10' : 'text-rose-500 bg-rose-500/10'
                                    }`}>verified</span>
                                <span className="text-sm font-black text-slate-400 uppercase tracking-widest">Final Contra</span>
                            </div>
                            <div className="flex items-center justify-between">
                                <h4 className="text-3xl font-black text-slate-900 dark:text-white tabular-nums">{formatNumber(stats?.total_final_contra)}</h4>
                                <div className={`px-2 py-1 text-white text-sm font-black rounded-lg shadow-sm transition-all duration-300 ${(stats?.contra_efficiency || 0) >= 90 ? 'bg-emerald-500 shadow-emerald-500/20' :
                                        (stats?.contra_efficiency || 0) >= 80 ? 'bg-blue-500 shadow-blue-500/20' :
                                            (stats?.contra_efficiency || 0) >= 50 ? 'bg-amber-500 shadow-amber-500/20' : 'bg-rose-500 shadow-rose-500/20'
                                    }`}>
                                    {stats?.contra_efficiency || 0}%
                                </div>
                            </div>
                            <p className="text-[10px] text-slate-500 font-bold">Match Efficiency</p>
                        </div>

                        {/* Return Match Metrics */}
                        <div className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col gap-2 transition-all duration-300 hover:shadow-lg hover:-translate-y-1 dark:hover:shadow-slate-500/5">
                            <div className="flex items-center justify-between mb-2">
                                <span className="material-symbols-outlined text-purple-500 bg-purple-500/10 p-2 rounded-lg">keyboard_return</span>
                                <span className="text-sm font-black text-slate-400 uppercase tracking-widest">S/W Return</span>
                            </div>
                            <h4 className="text-3xl font-black text-slate-900 dark:text-white tabular-nums">{formatNumber(stats?.total_sw_return)}</h4>
                            <p className="text-[10px] text-slate-500 font-bold">Initial Software Count</p>
                        </div>

                        <div className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col gap-2 transition-all duration-300 hover:shadow-lg hover:-translate-y-1 dark:hover:shadow-slate-500/5">
                            <div className="flex items-center justify-between mb-2">
                                <span className={`material-symbols-outlined p-2 rounded-lg transition-colors duration-300 ${(stats?.return_efficiency || 0) >= 90 ? 'text-emerald-500 bg-emerald-500/10' :
                                        (stats?.return_efficiency || 0) >= 80 ? 'text-blue-500 bg-blue-500/10' :
                                            (stats?.return_efficiency || 0) >= 50 ? 'text-amber-500 bg-amber-500/10' : 'text-rose-500 bg-rose-500/10'
                                    }`}>assignment_return</span>
                                <span className="text-sm font-black text-slate-400 uppercase tracking-widest">Final Return</span>
                            </div>
                            <div className="flex items-center justify-between">
                                <h4 className="text-3xl font-black text-slate-900 dark:text-white tabular-nums">{formatNumber(stats?.total_final_return)}</h4>
                                <div className={`px-2 py-1 text-white text-sm font-black rounded-lg shadow-sm transition-all duration-300 ${(stats?.return_efficiency || 0) >= 90 ? 'bg-emerald-500 shadow-emerald-500/20' :
                                        (stats?.return_efficiency || 0) >= 80 ? 'bg-blue-500 shadow-blue-500/20' :
                                            (stats?.return_efficiency || 0) >= 50 ? 'bg-amber-500 shadow-amber-500/20' : 'bg-rose-500 shadow-rose-500/20'
                                    }`}>
                                    {stats?.return_efficiency || 0}%
                                </div>
                            </div>
                            <p className="text-[10px] text-slate-500 font-bold">Match Efficiency</p>
                        </div>
                    </div>

                    {/* Processed Files Table */}
                    <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-xl overflow-hidden animate-in fade-in slide-in-from-bottom-8 duration-1000 delay-300">
                        <div className="p-6 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-slate-800/50">
                            <div>
                                <h3 className="text-xl font-black text-slate-900 dark:text-white flex items-center gap-3">
                                    <span className="material-symbols-outlined text-primary">history</span>
                                    <span>Recently Processed Files</span>
                                </h3>
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="size-2 rounded-full bg-emerald-500 animate-pulse"></span>
                                <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Live Updates</span>
                            </div>
                        </div>

                        <div className="overflow-x-auto scrollbar-slim">
                            <table className="w-full text-left border-collapse min-w-[1000px]">
                                <thead>
                                    <tr className="bg-slate-50 dark:bg-slate-800/30">
                                        <th className="px-6 py-4 text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-100 dark:border-slate-800">S.No</th>
                                        <th className="px-6 py-4 text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-100 dark:border-slate-800">Date</th>
                                        <th className="px-6 py-4 text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-100 dark:border-slate-800">File Name</th>
                                        <th className="px-6 py-4 text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-100 dark:border-slate-800 text-center">Total Entries</th>
                                        <th className="px-6 py-4 text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-100 dark:border-slate-800 text-center">S/W Matched</th>
                                        <th className="px-6 py-4 text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-100 dark:border-slate-800 text-center">Team Contrib.</th>
                                        <th className="px-6 py-4 text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-100 dark:border-slate-800 text-center">Contra %</th>
                                        <th className="px-6 py-4 text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-100 dark:border-slate-800 text-center">Return %</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {currentLogs.map((log, index) => (
                                        <tr key={log.id} className="group hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors duration-200">
                                            <td className="px-6 py-4 text-xs font-bold text-slate-400 tabular-nums">{startIndex + index + 1}</td>
                                            <td className="px-6 py-4 text-xs font-bold text-slate-600 dark:text-slate-300">
                                                {new Date(log.processed_at).toLocaleDateString()}
                                            </td>
                                            <td className="px-6 py-4 min-w-[240px]">
                                                <div className="flex flex-col">
                                                    <span className="text-sm font-black text-slate-900 dark:text-white truncate max-w-[300px]" title={log.file_name}>
                                                        {log.file_name}
                                                    </span>
                                                    <span className="text-[10px] text-slate-400 font-bold uppercase tracking-tight">{log.bank_name}</span>
                                                </div>
                                            </td>
                                            <td className="px-6 py-4 text-center">
                                                <span className="px-2 py-1 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 rounded-md text-xs font-black tabular-nums">
                                                    {formatNumber(log.total_entries)}
                                                </span>
                                            </td>
                                            <td className="px-6 py-4 text-center">
                                                <div className="flex flex-col items-center gap-1">
                                                    <div className="w-16 h-1.5 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                                                        <div
                                                            className={`h-full transition-all duration-1000 ${log.sw_matched_pct >= 90 ? 'bg-emerald-500' :
                                                                    log.sw_matched_pct >= 80 ? 'bg-blue-500' :
                                                                        log.sw_matched_pct >= 50 ? 'bg-amber-500' : 'bg-rose-500'
                                                                }`}
                                                            style={{ width: `${log.sw_matched_pct}%` }}
                                                        ></div>
                                                    </div>
                                                    <span className={`text-xs font-black tabular-nums ${log.sw_matched_pct >= 90 ? 'text-emerald-500' :
                                                            log.sw_matched_pct >= 80 ? 'text-blue-500' :
                                                                log.sw_matched_pct >= 50 ? 'text-amber-500' : 'text-rose-500'
                                                        }`}>{log.sw_matched_pct}%</span>
                                                </div>
                                            </td>
                                            <td className="px-6 py-4 text-center">
                                                <div className="flex flex-col items-center gap-1">
                                                    <div className="w-16 h-1.5 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                                                        <div
                                                            className={`h-full transition-all duration-1000 ${log.team_contrib_pct >= 90 ? 'bg-emerald-500' :
                                                                    log.team_contrib_pct >= 80 ? 'bg-blue-500' :
                                                                        log.team_contrib_pct >= 50 ? 'bg-amber-500' : 'bg-rose-500'
                                                                }`}
                                                            style={{ width: `${log.team_contrib_pct}%` }}
                                                        ></div>
                                                    </div>
                                                    <span className={`text-xs font-black tabular-nums ${log.team_contrib_pct >= 90 ? 'text-emerald-500' :
                                                            log.team_contrib_pct >= 80 ? 'text-blue-500' :
                                                                log.team_contrib_pct >= 50 ? 'text-amber-500' : 'text-rose-500'
                                                        }`}>{log.team_contrib_pct}%</span>
                                                </div>
                                            </td>
                                            <td className="px-6 py-4 text-center">
                                                <span className={`px-2 py-1 rounded-full text-[10px] font-black tabular-nums border transition-colors duration-300 ${log.contra_pct >= 90
                                                        ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20'
                                                        : log.contra_pct >= 80
                                                            ? 'bg-blue-500/10 text-blue-500 border-blue-500/20'
                                                            : log.contra_pct >= 50
                                                                ? 'bg-amber-500/10 text-amber-500 border-amber-500/20'
                                                                : log.contra_pct > 0
                                                                    ? 'bg-rose-500/10 text-rose-500 border-rose-500/20'
                                                                    : 'bg-slate-100 dark:bg-slate-800 text-slate-400 border-transparent'
                                                    }`}>
                                                    {log.contra_pct}%
                                                </span>
                                            </td>
                                            <td className="px-6 py-4 text-center">
                                                <span className={`px-2 py-1 rounded-full text-[10px] font-black tabular-nums border transition-colors duration-300 ${log.return_pct >= 90
                                                        ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20'
                                                        : log.return_pct >= 80
                                                            ? 'bg-blue-500/10 text-blue-500 border-blue-500/20'
                                                            : log.return_pct >= 50
                                                                ? 'bg-amber-500/10 text-amber-500 border-amber-500/20'
                                                                : log.return_pct > 0
                                                                    ? 'bg-rose-500/10 text-rose-500 border-rose-500/20'
                                                                    : 'bg-slate-100 dark:bg-slate-800 text-slate-400 border-transparent'
                                                    }`}>
                                                    {log.return_pct}%
                                                </span>
                                            </td>
                                        </tr>
                                    ))}
                                    {logs.length === 0 && (
                                        <tr>
                                            <td colSpan="8" className="px-6 py-20 text-center">
                                                <div className="flex flex-col items-center gap-4 opacity-30">
                                                    <span className="material-symbols-outlined text-6xl">cloud_off</span>
                                                    <p className="text-sm font-black uppercase tracking-widest">No processed files found</p>
                                                </div>
                                            </td>
                                        </tr>
                                    )}
                                </tbody>
                            </table>
                        </div>

                        {/* Pagination Footer */}
                        {logs.length > 0 && (
                            <div className="p-4 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-slate-900/50">
                                <div className="text-[10px] font-black text-slate-400 uppercase tracking-widest px-2">
                                    Displaying <span className="text-slate-900 dark:text-white leading-none">{startIndex + 1}</span> - <span className="text-slate-900 dark:text-white">{Math.min(startIndex + itemsPerPage, logs.length)}</span> of <span className="text-slate-900 dark:text-white">{logs.length}</span> entries
                                </div>
                                <div className="flex items-center gap-1.5 translate-x-1">
                                    <button
                                        onClick={() => {
                                            setCurrentPage(p => Math.max(1, p - 1));
                                            document.querySelector('main')?.scrollTo({ top: 0, behavior: 'smooth' });
                                        }}
                                        disabled={currentPage === 1}
                                        className="size-9 rounded-xl border border-slate-200 dark:border-slate-800 flex items-center justify-center text-slate-400 hover:text-primary hover:border-primary disabled:opacity-20 transition-all duration-300 active:scale-90"
                                    >
                                        <span className="material-symbols-outlined text-lg">chevron_left</span>
                                    </button>

                                    <div className="hidden md:flex items-center gap-1">
                                        {[...Array(totalPages)].map((_, i) => {
                                            const pNum = i + 1;
                                            if (totalPages > 6 && (pNum !== 1 && pNum !== totalPages && Math.abs(pNum - currentPage) > 1)) {
                                                if (pNum === 2 || pNum === totalPages - 1) return <span key={pNum} className="text-slate-300">..</span>;
                                                return null;
                                            }
                                            return (
                                                <button
                                                    key={pNum}
                                                    onClick={() => {
                                                        setCurrentPage(pNum);
                                                        document.querySelector('main')?.scrollTo({ top: 0, behavior: 'smooth' });
                                                    }}
                                                    className={`size-9 rounded-xl text-[11px] font-black transition-all duration-300 ${currentPage === pNum
                                                            ? 'bg-primary text-white shadow-lg shadow-primary/20 scale-105'
                                                            : 'text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800'
                                                        }`}
                                                >
                                                    {pNum}
                                                </button>
                                            );
                                        })}
                                    </div>

                                    <button
                                        onClick={() => {
                                            setCurrentPage(p => Math.min(totalPages, p + 1));
                                            document.querySelector('main')?.scrollTo({ top: 0, behavior: 'smooth' });
                                        }}
                                        disabled={currentPage === totalPages}
                                        className="size-9 rounded-xl border border-slate-200 dark:border-slate-800 flex items-center justify-center text-slate-400 hover:text-primary hover:border-primary disabled:opacity-20 transition-all duration-300 active:scale-90"
                                    >
                                        <span className="material-symbols-outlined text-lg">chevron_right</span>
                                    </button>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </main>
        </Layout>
    );
};

export default HomeDashboard;
