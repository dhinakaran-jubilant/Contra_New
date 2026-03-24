import React from 'react';

export default function SuccessModal({ title, message, onClose }) {
  return (
    <div className="fixed inset-0 z-[110] flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4 animate-in fade-in duration-300">
      <div className="w-full max-w-sm bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden animate-in zoom-in slide-in-from-bottom-4 duration-500">
        <div className="p-8 text-center">
          <div className="inline-flex items-center justify-center w-15 h-15 rounded-full bg-emerald-100 dark:bg-emerald-900/30 text-emerald-500 mb-6">
            <span className="material-symbols-outlined text-[30px]">check_circle</span>
          </div>
          <h2 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mb-3">{title || 'Success!'}</h2>
          <p className="text-slate-500 dark:text-slate-400 text-sm mb-8 leading-relaxed">
            {message || 'Your action has been completed successfully.'}
          </p>
          <button
            onClick={onClose}
            className="w-full bg-emerald-500 hover:bg-emerald-600 text-white font-bold h-12 rounded-xl transition-all shadow-lg shadow-emerald-500/25 flex items-center justify-center gap-2 group"
          >
            Got it, thanks!
            <span className="material-symbols-outlined text-lg group-hover:scale-110 transition-transform">celebration</span>
          </button>
        </div>
      </div>
    </div>
  );
}
