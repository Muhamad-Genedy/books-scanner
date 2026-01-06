import React, { useEffect, useState } from 'react';
import { X, Download, RefreshCw, CheckCircle, XCircle, AlertCircle } from 'lucide-react';

export default function HistoryModal({ isOpen, onClose }) {
    const [history, setHistory] = useState([]);
    const [loading, setLoading] = useState(false);

    const fetchHistory = async () => {
        setLoading(true);
        try {
            const res = await fetch('/api/history');
            if (res.ok) {
                const data = await res.json();
                setHistory(data);
            }
        } catch (e) {
            console.error("Failed to fetch history", e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (isOpen) {
            fetchHistory();
        }
    }, [isOpen]);

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-xl shadow-xl w-full max-w-4xl max-h-[80vh] flex flex-col">
                <div className="p-6 border-b border-gray-100 flex items-center justify-between bg-gray-50/50 rounded-t-xl">
                    <h2 className="text-xl font-semibold text-gray-800">Operation Log</h2>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={fetchHistory}
                            className="p-2 hover:bg-gray-100 rounded-lg text-gray-500 transition-colors"
                            title="Refresh"
                        >
                            <RefreshCw size={20} className={loading ? "animate-spin" : ""} />
                        </button>
                        <button
                            onClick={onClose}
                            className="p-2 hover:bg-red-50 text-gray-400 hover:text-red-500 rounded-lg transition-colors"
                        >
                            <X size={20} />
                        </button>
                    </div>
                </div>

                <div className="p-6 overflow-y-auto">
                    {history.length === 0 ? (
                        <div className="text-center py-12 text-gray-500">
                            No operations recorded yet.
                        </div>
                    ) : (
                        <table className="w-full text-sm text-left">
                            <thead className="bg-gray-50 text-gray-600 font-medium">
                                <tr>
                                    <th className="px-4 py-3 rounded-l-lg">Timestamp</th>
                                    <th className="px-4 py-3">Folder Name</th>
                                    <th className="px-4 py-3">Status</th>
                                    <th className="px-4 py-3">Stats (P/S/E)</th>
                                    <th className="px-4 py-3 rounded-r-lg text-right">Actions</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-100">
                                {history.map((entry, idx) => (
                                    <tr key={idx} className="hover:bg-gray-50/50 transition-colors">
                                        <td className="px-4 py-3 font-mono text-gray-500">
                                            {new Date(entry.timestamp).toLocaleString()}
                                        </td>
                                        <td className="px-4 py-3 font-medium text-gray-800">
                                            {entry.folder_name || "Unknown"}
                                        </td>
                                        <td className="px-4 py-3">
                                            <StatusBadge status={entry.status} />
                                        </td>
                                        <td className="px-4 py-3 text-gray-600">
                                            {entry.stats.processed} / {entry.stats.skipped} / <span className="text-red-600">{entry.stats.errors}</span>
                                        </td>
                                        <td className="px-4 py-3 text-right">
                                            {entry.output_file && (
                                                <a
                                                    href={`/api/download?filename=${encodeURIComponent(entry.output_file)}`}
                                                    target="_blank"
                                                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-50 text-blue-700 hover:bg-blue-100 rounded-md font-medium text-xs transition-colors"
                                                >
                                                    <Download size={14} /> JSON
                                                </a>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>
            </div>
        </div>
    );
}

function StatusBadge({ status }) {
    if (status === 'COMPLETED') {
        return <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800"><CheckCircle size={12} /> Done</span>;
    }
    if (status === 'ERROR') {
        return <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800"><XCircle size={12} /> Error</span>;
    }
    if (status === 'STOPPED') {
        return <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800"><AlertCircle size={12} /> Stopped</span>;
    }
    return <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">{status}</span>;
}
