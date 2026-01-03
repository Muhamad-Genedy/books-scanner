import React from 'react';
import LogViewer from './LogViewer';
import { Files, XCircle, CheckCircle, Clock, Download, StopCircle } from 'lucide-react';

export default function Dashboard({ status, onStop, onBack }) {
    const { state, counters, elapsed } = status;

    const isRunning = state === 'RUNNING';
    const isDone = state === 'COMPLETED' || state === 'STOPPED' || state === 'ERROR';

    const formatTime = (seconds) => {
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = seconds % 60;
        return `${h}h ${m}m ${s}s`;
    };

    return (
        <div className="space-y-6">
            {/* Stats Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <StatCard
                    label="Processed"
                    value={counters.processed || 0}
                    icon={<Files size={20} className="text-blue-500" />}
                />
                <StatCard
                    label="Skipped"
                    value={counters.skipped || 0}
                    icon={<CheckCircle size={20} className="text-gray-400" />}
                />
                <StatCard
                    label="Errors"
                    value={counters.errors || 0}
                    icon={<XCircle size={20} className="text-red-500" />}
                />
                <StatCard
                    label="Duration"
                    value={formatTime(elapsed)}
                    icon={<Clock size={20} className="text-purple-500" />}
                />
            </div>

            {/* Actions & Status */}
            <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm flex flex-col md:flex-row items-center justify-between gap-4">
                <div>
                    <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium
                        ${state === 'RUNNING' ? 'bg-blue-100 text-blue-800' :
                            state === 'COMPLETED' ? 'bg-green-100 text-green-800' :
                                state === 'ERROR' ? 'bg-red-100 text-red-800' : 'bg-gray-100 text-gray-800'}`}>
                        Status: {state}
                    </span>
                </div>

                <div className="flex gap-3">
                    {isRunning && (
                        <button
                            onClick={onStop}
                            className="flex items-center gap-2 px-4 py-2 bg-red-50 text-red-700 hover:bg-red-100 rounded-lg border border-red-200 font-medium transition-colors"
                        >
                            <StopCircle size={18} /> Stop Job
                        </button>
                    )}

                    {isDone && (
                        <>
                            <button
                                onClick={onBack}
                                className="px-4 py-2 text-gray-600 hover:bg-gray-50 rounded-lg font-medium transition-colors"
                            >
                                Start New Job
                            </button>
                            <a
                                href="/api/download"
                                target="_blank"
                                className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium shadow-sm transition-colors"
                            >
                                <Download size={18} /> Download JSON
                            </a>
                        </>
                    )}
                </div>
            </div>

            {/* Logs */}
            <div className="rounded-xl overflow-hidden border border-gray-200 shadow-sm">
                <div className="bg-gray-50 px-4 py-2 border-b border-gray-200 font-medium text-sm text-gray-600">
                    Live Logs
                </div>
                <LogViewer />
            </div>
        </div>
    );
}

function StatCard({ label, value, icon }) {
    return (
        <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm flex items-center justify-between">
            <div>
                <p className="text-sm text-gray-500 font-medium">{label}</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
            </div>
            <div className="p-2 bg-gray-50 rounded-lg">
                {icon}
            </div>
        </div>
    );
}
