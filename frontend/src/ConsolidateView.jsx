import config from './config';
import React, { useState, useRef, useEffect } from 'react';
import { DotLottiePlayer } from '@dotlottie/react-player';

const ConsolidateView = ({ user }) => {
    const [selectedFiles, setSelectedFiles] = useState([]);
    const [errorMessage, setErrorMessage] = useState('');
    const [processingStatus, setProcessingStatus] = useState('');
    const [isProcessing, setIsProcessing] = useState(false);
    const [successMessage, setSuccessMessage] = useState('');
    const [showSuccessModal, setShowSuccessModal] = useState(false);
    
    const fileInputRef = useRef(null);
    const errorTimerRef = useRef(null);

    const handleUploadClick = () => {
        if (fileInputRef.current) {
            fileInputRef.current.click();
        }
    };

    const handleFileChange = (e) => {
        const files = Array.from(e.target.files);
        if (files.length > 0) {
            setSelectedFiles((prev) => [...prev, ...files]);
        }
    };

    const handleDragOver = (e) => {
        e.preventDefault();
    };

    const handleDrop = (e) => {
        e.preventDefault();
        const files = Array.from(e.dataTransfer.files);
        if (files.length > 0) {
            setSelectedFiles((prev) => [...prev, ...files]);
        }
    };

    const removeFile = (indexToRemove) => {
        setSelectedFiles((prev) => prev.filter((_, index) => index !== indexToRemove));
    };

    const handleProcessFiles = async () => {
        if (selectedFiles.length === 0) {
            setErrorMessage('Please select at least 1 Excel file before processing.');
            if (errorTimerRef.current) clearTimeout(errorTimerRef.current);
            errorTimerRef.current = setTimeout(() => setErrorMessage(''), 5000);
            return;
        }

        const startTime = performance.now();
        setIsProcessing(true);
        setErrorMessage('');
        setSuccessMessage('');

        try {
            // STEP 1: MERGE
            setProcessingStatus('Merging files...');
            const mergeFormData = new FormData();
            mergeFormData.append('action', 'merge');
            mergeFormData.append('user_name', user?.full_name || 'Anonymous');
            selectedFiles.forEach((file) => mergeFormData.append('files', file));

            const mergeRes = await fetch(`${config.API_BASE_URL}/api/consolidate/`, {
                method: 'POST',
                body: mergeFormData,
            });

            if (!mergeRes.ok) {
                const err = await mergeRes.json().catch(() => ({}));
                throw new Error(err?.error || `Merge failed: ${mergeRes.status}`);
            }

            const mergeData = await mergeRes.json();
            const consolidatedPath = mergeData.file_path;
            const skipCons = mergeData.skip_cons;

            // STEP 2: CONS SHEET (Skip if only 1 file was uploaded)
            if (!skipCons) {
                setProcessingStatus('Creating summary sheet...');
                const consRes = await fetch(`${config.API_BASE_URL}/api/consolidate/`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: 'cons', file_path: consolidatedPath, user_name: user?.full_name || 'Anonymous' }),
                });

                if (!consRes.ok) {
                    const err = await consRes.json().catch(() => ({}));
                    throw new Error(err?.error || `Summary creation failed: ${consRes.status}`);
                }
            }

            // STEP 3: CHARTS
            setProcessingStatus('Generating charts...');
            const chartsRes = await fetch(`${config.API_BASE_URL}/api/consolidate/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'charts', file_path: consolidatedPath, user_name: user?.full_name || 'Anonymous' }),
            });

            if (!chartsRes.ok) {
                const err = await chartsRes.json().catch(() => ({}));
                throw new Error(err?.error || `Chart generation failed: ${chartsRes.status}`);
            }

            const finalData = await chartsRes.json();
            
            // DOWNLOAD
            if (finalData?.download_files && finalData.download_files.length > 0) {
                finalData.download_files.forEach((file) => {
                    const link = document.createElement('a');
                    link.href = `${config.API_BASE_URL}${file.download_url}`;
                    link.setAttribute('download', file.file_name);
                    document.body.appendChild(link);
                    link.click();
                    link.remove();
                });
            }

            const endTime = performance.now();
            const durationSec = ((endTime - startTime) / 1000).toFixed(1);
            const timeStr = durationSec > 60 ? `${(durationSec / 60).toFixed(1)} Minutes` : `${durationSec} Seconds`;

            const msg = (
                <>
                    Processed <span className="font-bold text-slate-900 dark:text-white">{selectedFiles.length}</span> files in <span className="font-bold text-primary">{timeStr}</span>.
                </>
            );
            setSuccessMessage(msg);
            setShowSuccessModal(true);
            setSelectedFiles([]);
        } catch (error) {
            setErrorMessage(error.message || 'Something went wrong. Please try again.');
            if (errorTimerRef.current) clearTimeout(errorTimerRef.current);
            errorTimerRef.current = setTimeout(() => setErrorMessage(''), 8000);
        } finally {
            setIsProcessing(false);
            setProcessingStatus('');
            if (fileInputRef.current) fileInputRef.current.value = "";
        }
    };

    const dismissError = () => {
        if (errorTimerRef.current) clearTimeout(errorTimerRef.current);
        setErrorMessage('');
    };

    return (
        <>
            <main className="flex-1 overflow-y-auto bg-background-light dark:bg-background-dark p-8">
                <div className="max-w-6xl mx-auto flex flex-col gap-8">
                    {/* Header Section */}
                    <div className="flex flex-col gap-2">
                        <div className="flex items-center gap-2 text-primary font-bold text-sm">
                            <span>Home</span>
                            <span className="material-symbols-outlined text-xs">chevron_right</span>
                            <span>Consolidate</span>
                        </div>
                        <h1 className="text-4xl mt-4 font-black tracking-tight text-slate-900 dark:text-white">Consolidate Files</h1>
                        <p className="text-slate-500 text-md max-w-5xl">Upload working files, it merge pivot and xns sheets, create cons sheets and also create charts (names, odd fig, doubt, return, bank fin and pvt fin).</p>
                    </div>

                    {/* Main Upload Card */}
                    <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800 overflow-hidden">
                        <div className="p-8">
                            <div
                                className="flex flex-col items-center justify-center gap-8 rounded-xl border-2 border-dashed border-primary/20 bg-primary/5 px-5 py-5 hover:bg-primary/10 transition-colors cursor-pointer group"
                                onClick={handleUploadClick}
                                onDragOver={handleDragOver}
                                onDrop={handleDrop}
                            >
                                <input
                                    type="file"
                                    ref={fileInputRef}
                                    className="hidden"
                                    multiple
                                    accept=".xlsx"
                                    onChange={handleFileChange}
                                />
                                <div className="flex flex-col items-center gap-4">
                                    <div className="size-15 bg-white dark:bg-slate-800 rounded-full flex items-center justify-center shadow-lg group-hover:scale-110 transition-transform">
                                        <span className="material-symbols-outlined text-4xl text-primary">upload_file</span>
                                    </div>
                                    <div className="text-center">
                                        <h4 className="text-xl font-bold mb-1">Drag and drop files here</h4>
                                        <p className="text-slate-500 text-sm max-w-md">Supports .XLSX Excel files only.</p>
                                    </div>
                                </div>
                                <button className="flex items-center gap-2 px-8 py-3 bg-primary text-white rounded-lg font-bold shadow-lg shadow-primary/25 hover:translate-y-[-2px] active:translate-y-0 transition-all cursor-pointer">
                                    <span className="material-symbols-outlined text-xl">add_circle</span>
                                    Browse Files
                                </button>
                            </div>

                            {/* Inline Error Message */}
                            {errorMessage && (
                                <div className="mt-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800/50 text-red-600 dark:text-red-400 px-4 py-3 rounded-lg flex items-center gap-3">
                                    <span className="material-symbols-outlined text-xl">error</span>
                                    <span className="text-sm font-medium flex-1">{errorMessage}</span>
                                    <button
                                        onClick={dismissError}
                                        className="flex items-center justify-center h-6 w-6 rounded hover:bg-red-100 dark:hover:bg-red-900/40 transition-colors"
                                        title="Dismiss"
                                    >
                                        <span className="material-symbols-outlined text-[18px]">close</span>
                                    </button>
                                </div>
                            )}

                            {/* Selected Files List */}
                            {selectedFiles.length > 0 && (
                                <div className="mt-6 flex flex-col gap-3">
                                    <h5 className="font-semibold text-slate-700 dark:text-slate-300">Selected Files:</h5>
                                    {selectedFiles.map((file, index) => (
                                        <div key={index} className="flex items-center justify-between p-3 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50">
                                            <div className="flex items-center gap-3 overflow-hidden">
                                                <span className="material-symbols-outlined text-primary text-xl">description</span>
                                                <span className="text-sm font-medium truncate text-slate-700 dark:text-slate-300">{file.name}</span>
                                                <span className="text-xs text-slate-500 dark:text-slate-400">
                                                    {(file.size / 1024 / 1024).toFixed(2)} MB
                                                </span>
                                            </div>
                                            <button
                                                onClick={() => removeFile(index)}
                                                className="flex items-center justify-center rounded-lg h-8 w-8 text-slate-400 hover:text-red-500 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
                                                title="Remove file"
                                            >
                                                <span className="material-symbols-outlined text-[20px]">delete</span>
                                            </button>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Action Buttons */}
                    <div className="flex justify-end gap-4 mt-4">
                        <button
                            onClick={() => setSelectedFiles([])}
                            className="flex items-center gap-2 px-6 py-2.5 rounded-lg border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 font-semibold hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors cursor-pointer"
                        >
                            <span className="material-symbols-outlined text-xl">restart_alt</span>
                            Clear All
                        </button>
                        <button
                            onClick={handleProcessFiles}
                            disabled={isProcessing}
                            className={`flex items-center gap-2 px-6 py-2.5 bg-primary text-white rounded-lg font-bold shadow-md shadow-primary/20 transition-all ${isProcessing ? 'opacity-70 cursor-not-allowed' : 'hover:bg-primary/90 active:translate-y-0 hover:-translate-y-0.5 cursor-pointer'}`}
                        >
                            {isProcessing ? (
                                <>
                                    <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                    </svg>
                                    Consolidating...
                                </>
                            ) : (
                                <>
                                    <span className="material-symbols-outlined text-xl">auto_awesome</span>
                                    Consolidate
                                </>
                            )}
                        </button>
                    </div>

                </div>

                {/* Footer */}
                <footer className="mt-12 pt-8 border-t border-slate-200 dark:border-slate-800 text-center text-sm text-slate-500 dark:text-slate-400">
                    <p>
                        All rights reserved &copy; 2026 @ Jubilant Capital. Designed and developed by{' '}
                        <a href="mailto:dhinakaran.s@jubilantenterprises.in" className="text-primary hover:underline font-semibold">
                            Dhinakaran Sekar
                        </a>
                    </p>
                </footer>
            </main>

            {/* Processing Modal Overlay */}
            {isProcessing && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-300">
                    <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl p-10 flex flex-col items-center gap-6 max-w-sm w-full mx-4 border border-slate-200 dark:border-slate-800 animate-in zoom-in-95 duration-300">
                        <div className="relative size-32 flex items-center justify-center">
                            <DotLottiePlayer
                                src="https://lottie.host/26c29f4c-00d1-4c13-a161-b608499b7ccb/5uUeWZYlLT.lottie"
                                autoplay
                                loop
                                className="size-full"
                            />
                        </div>
                        <div className="text-center">
                            <h3 className="text-2xl font-black tracking-tight text-slate-900 dark:text-white mb-2">Processing Files</h3>
                            <p className="text-primary font-bold mb-1">{processingStatus}</p>
                            <p className="text-slate-500 dark:text-slate-400 text-sm">Please wait, this may take a few moments...</p>
                        </div>
                        <div className="w-full h-1.5 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden relative">
                            <div className="absolute top-0 bottom-0 left-0 bg-primary w-1/2 rounded-full animate-progress-indeterminate"></div>
                        </div>
                    </div>
                </div>
            )}

            {/* Success Modal Overlay */}
            {showSuccessModal && (
                <div className="fixed inset-0 z-[110] flex items-center justify-center bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-300">
                    <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl p-10 flex flex-col items-center gap-6 max-w-sm w-full mx-4 border border-slate-200 dark:border-slate-800 animate-in zoom-in-95 duration-300">
                        <div className="size-15 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center">
                            <span className="material-symbols-outlined text-green-600 dark:text-green-400 text-[30px]">check_circle</span>
                        </div>
                        <div className="text-center">
                            <h3 className="text-2xl font-black tracking-tight text-slate-900 dark:text-white mb-2">Success!</h3>
                            <p className="text-slate-500 dark:text-slate-400 text-sm">{successMessage || 'Files processed and downloaded successfully.'}</p>
                        </div>
                        <button
                            onClick={() => setShowSuccessModal(false)}
                            className="w-full py-3 bg-green-600 hover:bg-green-700 text-white rounded-lg font-bold shadow-lg shadow-green-600/20 transition-all active:scale-[0.98]"
                        >
                            OK
                        </button>
                    </div>
                </div>
            )}
        </>
    );
};

export default ConsolidateView;
