import React, { useState, useEffect, useRef } from 'react';
import ConfigForm from './components/ConfigForm';
import Dashboard from './components/Dashboard';
import { Activity, BookOpen, AlertCircle } from 'lucide-react';

const API_BASE = '/api'; // Relative path for production and dev (via proxy)
// Best practice is / api proxy in Vite, but let's assume relative for built version or explicit for dev.
// Actually, since I'm running backend on 8000 and frontend on 5173, I need full URL or proxy.
// I'll use a constant for now that defaults to empty string if valid, or localhost:8000.
// But simpler: just assume relative path '/api' in production and setup Vite proxy for dev.

function App() {
    const [status, setStatus] = useState({ state: 'IDLE', counters: {}, elapsed: 0 });
    const [view, setView] = useState('CONFIG'); // CONFIG or DASHBOARD

    useEffect(() => {
        const checkStatus = async () => {
            try {
                const res = await fetch(`${API_BASE}/status`);
                const data = await res.json();

                // Map backend status to frontend state
                // Backend: IDLE, RUNNING, COMPLETED, ERROR
                if (data.status === 'RUNNING' || data.status === 'COMPLETED' || data.status === 'ERROR' || data.status === 'STOPPED') {
                    setView('DASHBOARD');
                } else {
                    setView('CONFIG');
                }
                setStatus({
                    state: data.status,
                    counters: data.counters,
                    elapsed: data.elapsed_seconds
                });
            } catch (e) {
                console.error("Failed to fetch status", e);
            }
        };

        checkStatus();
        const interval = setInterval(checkStatus, 2000);
        return () => clearInterval(interval);
    }, []);

    const handleStart = async (config) => {
        try {
            const res = await fetch(`${API_BASE}/start`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(config)
            });
            if (!res.ok) {
                const err = await res.json();
                alert('Error starting job: ' + err.detail);
                return;
            }
            setView('DASHBOARD');
        } catch (e) {
            alert('Network error: ' + e.message);
        }
    };

    const handleStop = async () => {
        try {
            await fetch(`${API_BASE}/stop`, { method: 'POST' });
        } catch (e) {
            console.error(e);
        }
    };

    const handleBack = async () => {
        try {
            await fetch(`${API_BASE}/reset`, { method: 'POST' });
            setView('CONFIG');
        } catch (e) {
            console.error(e);
            setView('CONFIG'); // Switch anyway
        }
    };

    return (
        <div className="min-h-screen bg-gray-50 text-slate-800 font-sans">
            <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center gap-3 sticky top-0 z-10">
                <div className="p-2 bg-blue-600 rounded-lg text-white">
                    <BookOpen size={24} />
                </div>
                <h1 className="text-xl font-bold tracking-tight text-gray-900">Book Scanner Control Panel</h1>
                <div className="ml-auto flex items-center gap-2 text-sm text-gray-500">
                    {status.state === 'RUNNING' && (
                        <span className="flex items-center gap-2 text-blue-600 font-medium px-3 py-1 bg-blue-50 rounded-full animate-pulse">
                            <Activity size={16} /> Scanning Active
                        </span>
                    )}
                    {status.state === 'ERROR' && (
                        <span className="flex items-center gap-2 text-red-600 font-medium px-3 py-1 bg-red-50 rounded-full">
                            <AlertCircle size={16} /> Error
                        </span>
                    )}
                </div>
            </header>

            <main className="max-w-5xl mx-auto p-6">
                {view === 'CONFIG' ? (
                    <ConfigForm onStart={handleStart} />
                ) : (
                    <Dashboard
                        status={status}
                        onStop={handleStop}
                        onBack={handleBack}
                    />
                )}
            </main>
        </div>
    )
}

export default App
