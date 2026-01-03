import React, { useState } from 'react';
import { UploadCloud, Key, Folder, Command } from 'lucide-react';

export default function ConfigForm({ onStart }) {
    const [json, setJson] = useState('');
    const [cloudName, setCloudName] = useState('');
    const [apiKey, setApiKey] = useState('');
    const [apiSecret, setApiSecret] = useState('');
    const [rootId, setRootId] = useState('');
    const [academicYear, setAcademicYear] = useState('');
    const [term, setTerm] = useState('');
    const [subject, setSubject] = useState('');
    const [releaseYear, setReleaseYear] = useState('');
    const [error, setError] = useState(null);

    // Load saved credentials from localStorage on mount
    React.useEffect(() => {
        try {
            const savedJson = localStorage.getItem('scanner_service_account_json');
            const savedCloudName = localStorage.getItem('scanner_cloudinary_cloud_name');
            const savedApiKey = localStorage.getItem('scanner_cloudinary_api_key');
            const savedApiSecret = localStorage.getItem('scanner_cloudinary_api_secret');

            if (savedJson) setJson(savedJson);
            if (savedCloudName) setCloudName(savedCloudName);
            if (savedApiKey) setApiKey(savedApiKey);
            if (savedApiSecret) setApiSecret(savedApiSecret);
        } catch (e) {
            console.error('Failed to load saved credentials:', e);
        }
    }, []);

    const handleSubmit = (e) => {
        e.preventDefault();
        setError(null);

        // Basic Validation
        try {
            JSON.parse(json);
        } catch (e) {
            setError("Invalid Service Account JSON");
            return;
        }

        if (!cloudName || !apiKey || !apiSecret) {
            setError("All Cloudinary fields are required.");
            return;
        }

        // Save credentials to localStorage
        try {
            localStorage.setItem('scanner_service_account_json', json);
            localStorage.setItem('scanner_cloudinary_cloud_name', cloudName);
            localStorage.setItem('scanner_cloudinary_api_key', apiKey);
            localStorage.setItem('scanner_cloudinary_api_secret', apiSecret);
        } catch (e) {
            console.error('Failed to save credentials:', e);
        }

        onStart({
            service_account_json: json,
            cloudinary_cloud_name: cloudName,
            cloudinary_api_key: apiKey,
            cloudinary_api_secret: apiSecret,
            drive_root_id: rootId || null,
            academic_year_id: academicYear || 'Direct',
            term_id: term || 'Direct',
            subject_id: subject || 'Direct',
            release_year: releaseYear || 'Direct'
        });
    };

    return (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100 bg-gray-50/50">
                <h2 className="text-lg font-semibold text-gray-800">New Scan Job</h2>
                <p className="text-sm text-gray-500">Configure credentials to start scanning.</p>
            </div>

            <form onSubmit={handleSubmit} className="p-6 space-y-6">
                {error && (
                    <div className="bg-red-50 text-red-700 px-4 py-3 rounded-lg text-sm border border-red-100 flex items-center">
                        <span className="font-semibold mr-1">Error:</span> {error}
                    </div>
                )}

                <div className="space-y-4">
                    <label className="block">
                        <span className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-2">
                            <Command size={16} /> Service Account JSON
                        </span>
                        <textarea
                            className="w-full h-32 px-4 py-3 rounded-lg border border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm font-mono"
                            placeholder='Paste contents of service-account.json here...'
                            value={json}
                            onChange={e => setJson(e.target.value)}
                        />
                    </label>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        <label className="block">
                            <span className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-2">
                                <UploadCloud size={16} /> Cloud Name
                            </span>
                            <input
                                type="text"
                                className="w-full px-4 py-2 rounded-lg border border-gray-300 focus:ring-2 focus:ring-blue-500"
                                value={cloudName}
                                onChange={e => setCloudName(e.target.value)}
                            />
                        </label>
                        <label className="block">
                            <span className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-2">
                                <Key size={16} /> API Key
                            </span>
                            <input
                                type="text"
                                className="w-full px-4 py-2 rounded-lg border border-gray-300 focus:ring-2 focus:ring-blue-500"
                                value={apiKey}
                                onChange={e => setApiKey(e.target.value)}
                            />
                        </label>
                        <label className="block">
                            <span className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-2">
                                <Key size={16} /> API Secret
                            </span>
                            <input
                                type="password"
                                className="w-full px-4 py-2 rounded-lg border border-gray-300 focus:ring-2 focus:ring-blue-500"
                                value={apiSecret}
                                onChange={e => setApiSecret(e.target.value)}
                            />
                        </label>
                    </div>

                    <label className="block">
                        <span className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-2">
                            <Folder size={16} /> Drive Root ID (Optional)
                        </span>
                        <input
                            type="text"
                            placeholder="Leave empty for root"
                            className="w-full px-4 py-2 rounded-lg border border-gray-300 focus:ring-2 focus:ring-blue-500"
                            value={rootId}
                            onChange={e => setRootId(e.target.value)}
                        />
                    </label>

                    <div className="border-t border-gray-200 pt-4">
                        <h3 className="text-sm font-semibold text-gray-700 mb-3">Metadata (Optional)</h3>
                        <p className="text-xs text-gray-500 mb-4">Leave empty to use "Direct" as default value</p>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <label className="block">
                                <span className="text-sm font-medium text-gray-700 mb-2 block">Academic Year</span>
                                <input
                                    type="text"
                                    placeholder="e.g., 2024-2025"
                                    className="w-full px-4 py-2 rounded-lg border border-gray-300 focus:ring-2 focus:ring-blue-500"
                                    value={academicYear}
                                    onChange={e => setAcademicYear(e.target.value)}
                                />
                            </label>
                            <label className="block">
                                <span className="text-sm font-medium text-gray-700 mb-2 block">Term</span>
                                <input
                                    type="text"
                                    placeholder="e.g., First Term"
                                    className="w-full px-4 py-2 rounded-lg border border-gray-300 focus:ring-2 focus:ring-blue-500"
                                    value={term}
                                    onChange={e => setTerm(e.target.value)}
                                />
                            </label>
                            <label className="block">
                                <span className="text-sm font-medium text-gray-700 mb-2 block">Subject</span>
                                <input
                                    type="text"
                                    placeholder="e.g., Arabic"
                                    className="w-full px-4 py-2 rounded-lg border border-gray-300 focus:ring-2 focus:ring-blue-500"
                                    value={subject}
                                    onChange={e => setSubject(e.target.value)}
                                />
                            </label>
                            <label className="block">
                                <span className="text-sm font-medium text-gray-700 mb-2 block">Release Year</span>
                                <input
                                    type="text"
                                    placeholder="e.g., 2025"
                                    className="w-full px-4 py-2 rounded-lg border border-gray-300 focus:ring-2 focus:ring-blue-500"
                                    value={releaseYear}
                                    onChange={e => setReleaseYear(e.target.value)}
                                />
                            </label>
                        </div>
                    </div>
                </div>

                <div className="pt-4 flex justify-end">
                    <button
                        type="submit"
                        className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg shadow-sm transition-colors flex items-center gap-2"
                    >
                        Start Scanning
                    </button>
                </div>
            </form>
        </div>
    );
}
