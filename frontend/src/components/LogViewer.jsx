import React, { useEffect, useRef, useState } from 'react';

export default function LogViewer() {
    const [logs, setLogs] = useState([]);
    const bottomRef = useRef(null);

    useEffect(() => {
        const evtSource = new EventSource('http://localhost:8000/api/logs/stream');

        evtSource.onmessage = (e) => {
            setLogs(prev => [...prev.slice(-499), e.data]); // Keep last 500
        };

        evtSource.onerror = (e) => {
            // console.error("EventSource failed:", e);
            evtSource.close();
            // Retry logic could go here, but for now simple close
        };

        return () => {
            evtSource.close();
        };
    }, []);

    useEffect(() => {
        if (bottomRef.current) {
            bottomRef.current.scrollIntoView({ behavior: 'smooth' });
        }
    }, [logs]);

    return (
        <div className="bg-gray-900 rounded-lg p-4 font-mono text-xs md:text-sm h-96 overflow-y-auto text-gray-300 shadow-inner">
            {logs.length === 0 && <div className="text-gray-600 italic">Waiting for logs...</div>}
            {logs.map((log, i) => (
                <div key={i} className="whitespace-pre-wrap break-words py-0.5 border-l-2 border-transparent hover:border-blue-500 hover:bg-white/5 pl-2 transition-colors">
                    {parseLog(log)}
                </div>
            ))}
            <div ref={bottomRef} />
        </div>
    );
}

function parseLog(log) {
    if (log.includes("[ERROR]") || log.includes("CRITICAL")) {
        return <span className="text-red-400">{log}</span>;
    }
    if (log.includes("[SUCCESS]")) {
        return <span className="text-green-400">{log}</span>;
    }
    if (log.includes("[INFO]")) {
        return <span className="text-blue-300">{log}</span>;
    }
    return log;
}
