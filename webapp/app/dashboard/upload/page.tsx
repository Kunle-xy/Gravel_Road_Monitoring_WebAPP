"use client";
import React, { useState, useEffect, useRef } from 'react';
import { Upload, X, FileImage, AlertCircle, CheckCircle, Folder } from 'lucide-react';
import { API_ENDPOINTS, fetchWithAuth } from '../../lib/api';

interface FolderOption {
  id: string;
  name: string;
  color: string;
}

type UploadStep = 'idle' | 'presigning' | 'uploading' | 'completing' | 'done' | 'error';

// 100MB threshold — files above this use multipart upload
const MULTIPART_THRESHOLD = 100 * 1024 * 1024;
// 50MB per part for multipart uploads
const PART_SIZE = 50 * 1024 * 1024;

export default function UploadPage() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileType, setFileType] = useState<'DEM' | 'ORTHOPHOTO'>('DEM');
  const [folders, setFolders] = useState<FolderOption[]>([]);
  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(null);
  const [loadingFolders, setLoadingFolders] = useState(true);
  const [step, setStep] = useState<UploadStep>('idle');
  const [uploadProgress, setUploadProgress] = useState(0);
  const [bytesUploaded, setBytesUploaded] = useState(0);
  const [statusText, setStatusText] = useState('');
  const [error, setError] = useState<string | null>(null);
  const uploadStartRef = useRef<number>(0);
  const abortRef = useRef(false);
  const xhrRef = useRef<XMLHttpRequest | null>(null);
  const presignDataRef = useRef<{ upload_id: string; s3_key: string } | null>(null);

  useEffect(() => {
    const fetchFolders = async () => {
      try {
        const response = await fetchWithAuth(API_ENDPOINTS.FOLDERS.LIST);
        if (response.ok) setFolders(await response.json());
      } catch (e) { console.error('Failed to fetch folders:', e); }
      finally { setLoadingFolders(false); }
    };
    fetchFolders();
  }, []);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      if (!file.name.match(/\.(tif|tiff)$/i)) {
        setError('Please select a valid TIFF file (.tif or .tiff)');
        return;
      }
      setSelectedFile(file);
      setError(null);
      setStep('idle');
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  const formatTime = (seconds: number) => {
    if (!isFinite(seconds) || seconds <= 0) return '--';
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
    return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
  };

  const getEta = () => {
    if (bytesUploaded === 0 || !selectedFile) return '--';
    const elapsed = (Date.now() - uploadStartRef.current) / 1000;
    const rate = bytesUploaded / elapsed;
    const remaining = (selectedFile.size - bytesUploaded) / rate;
    return formatTime(remaining);
  };

  const completeUpload = async () => {
    const data = presignDataRef.current;
    if (!data) return;
    setStep('completing');
    setStatusText('Confirming upload & starting processing...');
    setError(null);

    try {
      const res = await fetchWithAuth(API_ENDPOINTS.FILES.COMPLETE, {
        method: 'POST',
        body: JSON.stringify({ upload_id: data.upload_id, s3_key: data.s3_key }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(err?.detail || `Complete failed (${res.status})`);
      }
      setStep('done');
      presignDataRef.current = null;
      setTimeout(() => {
        setSelectedFile(null); setSelectedFolderId(null);
        setStep('idle'); setUploadProgress(0); setBytesUploaded(0);
      }, 3000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to confirm upload');
      setStep('error');
    }
  };

  // Upload a single part via presigned URL, returns ETag
  const uploadPart = (url: string, blob: Blob, partNum: number, totalParts: number, prevBytes: number): Promise<string> => {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhrRef.current = xhr;

      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable && selectedFile) {
          const totalUploaded = prevBytes + e.loaded;
          setBytesUploaded(totalUploaded);
          setUploadProgress(Math.round((totalUploaded / selectedFile.size) * 100));
        }
      });

      xhr.addEventListener('load', () => {
        xhrRef.current = null;
        if (xhr.status >= 200 && xhr.status < 300) {
          const etag = xhr.getResponseHeader('ETag');
          if (!etag) { reject(new Error(`Part ${partNum}: no ETag in response`)); return; }
          resolve(etag.replace(/"/g, ''));
        } else {
          reject(new Error(`Part ${partNum} failed (${xhr.status})`));
        }
      });
      xhr.addEventListener('error', () => { xhrRef.current = null; reject(new Error(`Part ${partNum}: network error`)); });
      xhr.addEventListener('abort', () => { xhrRef.current = null; reject(new Error('Upload cancelled')); });

      xhr.open('PUT', url);
      xhr.send(blob);
    });
  };

  // Multipart upload flow for large files
  const handleMultipartUpload = async (file: File) => {
    setStatusText('Initiating multipart upload...');

    // Step 1: Init multipart
    const initRes = await fetchWithAuth(API_ENDPOINTS.FILES.MULTIPART_INIT, {
      method: 'POST',
      body: JSON.stringify({
        filename: file.name,
        file_size: file.size,
        file_type: fileType,
        folder_id: selectedFolderId,
        content_type: 'image/tiff',
      }),
    });
    if (!initRes.ok) {
      const err = await initRes.json().catch(() => null);
      throw new Error(err?.detail || `Multipart init failed (${initRes.status})`);
    }

    const { upload_id, s3_key, s3_upload_id } = await initRes.json();
    presignDataRef.current = { upload_id, s3_key };

    // Step 2: Upload parts
    setStep('uploading');
    uploadStartRef.current = Date.now();

    const totalParts = Math.ceil(file.size / PART_SIZE);
    const completedParts: { part_number: number; etag: string }[] = [];
    let uploadedBytes = 0;

    for (let partNum = 1; partNum <= totalParts; partNum++) {
      if (abortRef.current) throw new Error('Upload cancelled');

      setStatusText(`Uploading part ${partNum}/${totalParts}...`);

      // Get presigned URL for this part
      const presignRes = await fetchWithAuth(API_ENDPOINTS.FILES.MULTIPART_PRESIGN_PART, {
        method: 'POST',
        body: JSON.stringify({
          s3_key,
          s3_upload_id,
          part_number: partNum,
        }),
      });
      if (!presignRes.ok) throw new Error(`Failed to presign part ${partNum}`);
      const { presigned_url } = await presignRes.json();

      // Slice file for this part
      const start = (partNum - 1) * PART_SIZE;
      const end = Math.min(start + PART_SIZE, file.size);
      const blob = file.slice(start, end);

      // Upload the part
      const etag = await uploadPart(presigned_url, blob, partNum, totalParts, uploadedBytes);
      completedParts.push({ part_number: partNum, etag });
      uploadedBytes += blob.size;
    }

    // Step 3: Complete multipart
    setStatusText('Finalizing multipart upload...');
    setStep('completing');

    const completeRes = await fetchWithAuth(API_ENDPOINTS.FILES.MULTIPART_COMPLETE, {
      method: 'POST',
      body: JSON.stringify({
        upload_id,
        s3_key,
        s3_upload_id,
        parts: completedParts,
      }),
    });
    if (!completeRes.ok) {
      const err = await completeRes.json().catch(() => null);
      throw new Error(err?.detail || 'Multipart complete failed');
    }

    setStep('done');
    presignDataRef.current = null;
    setTimeout(() => {
      setSelectedFile(null); setSelectedFolderId(null);
      setStep('idle'); setUploadProgress(0); setBytesUploaded(0);
    }, 3000);
  };

  // Single presigned PUT for small files
  const handleSimpleUpload = async (file: File) => {
    setStatusText('Getting presigned URL...');
    const presignRes = await fetchWithAuth(API_ENDPOINTS.FILES.PRESIGN, {
      method: 'POST',
      body: JSON.stringify({
        filename: file.name,
        file_size: file.size,
        file_type: fileType,
        folder_id: selectedFolderId,
        content_type: 'image/tiff',
      }),
    });
    if (!presignRes.ok) {
      const err = await presignRes.json().catch(() => null);
      throw new Error(err?.detail || `Presign failed (${presignRes.status})`);
    }

    const { presigned_url, s3_key, upload_id } = await presignRes.json();
    presignDataRef.current = { upload_id, s3_key };

    setStep('uploading');
    setStatusText('Uploading to S3...');
    uploadStartRef.current = Date.now();

    await new Promise<void>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhrRef.current = xhr;
      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
          setUploadProgress(Math.round((e.loaded / e.total) * 100));
          setBytesUploaded(e.loaded);
        }
      });
      xhr.addEventListener('load', () => {
        xhrRef.current = null;
        if (xhr.status >= 200 && xhr.status < 300) resolve();
        else reject(new Error(`S3 upload failed (${xhr.status})`));
      });
      xhr.addEventListener('error', () => { xhrRef.current = null; reject(new Error('Network error')); });
      xhr.addEventListener('abort', () => { xhrRef.current = null; reject(new Error('Upload cancelled')); });
      xhr.open('PUT', presigned_url);
      xhr.setRequestHeader('Content-Type', 'image/tiff');
      xhr.send(file);
    });

    await completeUpload();
  };

  const handleUpload = async () => {
    if (!selectedFile || !selectedFolderId) return;
    setStep('presigning');
    setError(null);
    setUploadProgress(0);
    setBytesUploaded(0);
    abortRef.current = false;

    try {
      if (selectedFile.size > MULTIPART_THRESHOLD) {
        await handleMultipartUpload(selectedFile);
      } else {
        await handleSimpleUpload(selectedFile);
      }
    } catch (err: unknown) {
      if (step !== 'error') {
        setError(err instanceof Error ? err.message : 'Upload failed');
        setStep('error');
      }
    }
  };

  const handleCancel = () => {
    abortRef.current = true;
    if (xhrRef.current) xhrRef.current.abort();
    setSelectedFile(null);
    setError(null);
    setStep('idle');
  };

  const isUploading = step === 'presigning' || step === 'uploading' || step === 'completing';

  return (
    <div className="flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="bg-linear-to-b from-slate-900/95 to-slate-800/95 backdrop-blur-sm rounded-xl shadow-2xl overflow-hidden ring-1 ring-inset ring-slate-700/50">

          <div className="bg-slate-800/50 p-4 border-b border-slate-700/50">
            <div className="flex items-center gap-2 text-white">
              <Upload size={24} />
              <div>
                <h2 className="text-lg font-bold text-white">Upload TIFF File</h2>
                <p className="text-white text-xs opacity-90">DEM or Orthophoto</p>
              </div>
            </div>
          </div>

          <div className="p-4 space-y-3 max-h-[calc(100vh-200px)] overflow-y-auto">

            <div>
              <label className="block text-xs font-semibold text-white mb-2">File Type</label>
              <div className="flex gap-2">
                <button onClick={() => setFileType('DEM')}
                  className={`flex-1 py-2 px-3 rounded-lg border-2 text-sm font-semibold transition-all ${fileType === 'DEM' ? 'border-slate-500 bg-slate-700 text-white' : 'border-slate-600 bg-slate-800/50 text-white hover:border-slate-500 hover:bg-slate-700/50'}`}>
                  DEM
                </button>
                <button onClick={() => setFileType('ORTHOPHOTO')}
                  className={`flex-1 py-2 px-3 rounded-lg border-2 text-sm font-semibold transition-all ${fileType === 'ORTHOPHOTO' ? 'border-slate-500 bg-slate-700 text-white' : 'border-slate-600 bg-slate-800/50 text-white hover:border-slate-500 hover:bg-slate-700/50'}`}>
                  Ortho
                </button>
              </div>
            </div>

            <div className="shrink-0">
              <label className="block text-xs font-semibold text-white mt-2 mb-2">Select Project *</label>
              {loadingFolders ? (
                <div className="text-xs text-white py-2">Loading projects...</div>
              ) : folders.length === 0 ? (
                <div className="text-xs text-white py-2 bg-yellow-900/20 border border-yellow-700/50 rounded-lg px-3">
                  No projects available. Create a project first in the sidebar.
                </div>
              ) : (
                <div style={{ height: '130px', maxHeight: '130px', minHeight: '130px' }} className="space-y-2 overflow-y-auto bg-slate-800/50 rounded-lg p-3 border border-slate-700">
                  {folders.map((folder) => (
                    <label key={folder.id} className={`flex items-center gap-2 p-2 rounded cursor-pointer transition-colors ${selectedFolderId === folder.id ? 'bg-slate-700 ring-2 ring-slate-500' : 'hover:bg-slate-700/50'}`}>
                      <input type="radio" name="project" value={folder.id} checked={selectedFolderId === folder.id}
                        onChange={(e) => setSelectedFolderId(e.target.value)} className="w-4 h-4 text-slate-500 focus:ring-slate-500" />
                      <Folder className="w-4 h-4" style={{ color: folder.color }} />
                      <span className="text-sm text-white flex-1">{folder.name}</span>
                    </label>
                  ))}
                </div>
              )}
            </div>

            <div>
              <label className="block text-xs font-semibold text-white mt-2">Select File</label>
              {!selectedFile ? (
                <label className="flex flex-col items-center justify-center w-full h-48 border-2 border-dashed border-slate-600 rounded-lg cursor-pointer hover:border-slate-500 hover:bg-slate-700/30 transition-all">
                  <div className="flex flex-col items-center justify-center p-6">
                    <FileImage className="w-12 h-12 text-white mb-3 opacity-70" />
                    <p className="text-sm text-white mb-1"><span className="font-semibold">Click to upload</span></p>
                    <p className="text-xs text-white opacity-70">TIFF files only</p>
                  </div>
                  <input type="file" className="hidden" accept=".tif,.tiff" onChange={handleFileSelect} />
                </label>
              ) : (
                <div className="border-2 border-slate-600 bg-slate-700/50 rounded-lg p-5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      <FileImage className="w-8 h-8 text-white flex-shrink-0" />
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-semibold text-white truncate">{selectedFile.name}</p>
                        <p className="text-xs text-white opacity-70">
                          {formatFileSize(selectedFile.size)}
                          {selectedFile.size > MULTIPART_THRESHOLD && (
                            <span className="text-blue-400 ml-1">(multipart)</span>
                          )}
                        </p>
                      </div>
                    </div>
                    <button onClick={handleCancel} className="p-1 hover:bg-red-900/30 rounded transition-colors flex-shrink-0"
                      disabled={step === 'completing'}>
                      <X className="w-4 h-4 text-red-400" />
                    </button>
                  </div>

                  {step === 'uploading' && (
                    <div className="mt-3">
                      <div className="flex justify-between text-xs text-white mb-1">
                        <span className="font-semibold">{statusText}</span>
                        <span className="font-bold text-green-400">{uploadProgress}%</span>
                      </div>
                      <div className="w-full bg-slate-700 rounded-full h-2.5 overflow-hidden">
                        <div className="bg-green-500 h-2.5 transition-all duration-300" style={{ width: `${uploadProgress}%` }} />
                      </div>
                      <div className="flex justify-between text-xs text-slate-400 mt-1">
                        <span>{formatFileSize(bytesUploaded)} / {formatFileSize(selectedFile.size)}</span>
                        <span>ETA: {getEta()}</span>
                      </div>
                    </div>
                  )}

                  {(step === 'presigning' || step === 'completing') && (
                    <div className="mt-3 flex items-center gap-2 text-xs text-slate-300">
                      <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-blue-400" />
                      <span>{statusText || (step === 'presigning' ? 'Preparing...' : 'Confirming...')}</span>
                    </div>
                  )}
                </div>
              )}
            </div>

            {error && (
              <div className="flex items-center gap-2 p-3 bg-red-900/30 border-2 border-red-500/50 rounded-lg">
                <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
                <div className="flex-1">
                  <p className="text-sm text-white font-medium">{error}</p>
                  {presignDataRef.current && (
                    <button onClick={completeUpload} className="text-xs text-blue-400 hover:text-blue-300 mt-1 underline">
                      Retry confirmation
                    </button>
                  )}
                </div>
              </div>
            )}

            {step === 'done' && (
              <div className="flex flex-col items-center gap-3 p-4 bg-gradient-to-br from-green-900/40 to-emerald-900/40 border-2 border-green-500/60 rounded-lg shadow-lg">
                <div className="flex items-center justify-center w-12 h-12 bg-green-500/20 rounded-full">
                  <CheckCircle className="w-8 h-8 text-green-400 animate-bounce" />
                </div>
                <div className="text-center">
                  <p className="text-base text-white font-bold mb-1">Upload Successful!</p>
                  <p className="text-xs text-white opacity-90">Your file is being processed. Tiles will appear when ready.</p>
                </div>
              </div>
            )}

            <div className="flex gap-2 pt-2">
              <button onClick={() => window.history.back()}
                className="flex-1 py-2 px-4 border-2 border-slate-600 rounded-lg text-sm font-semibold text-white hover:bg-slate-700/50 transition-colors"
                disabled={isUploading}>
                Cancel
              </button>
              <button onClick={handleUpload}
                disabled={!selectedFile || !selectedFolderId || isUploading}
                className="flex-1 py-3 px-4 bg-green-600 text-white rounded-lg text-sm font-bold hover:bg-green-500 disabled:bg-slate-800 disabled:text-slate-500 disabled:cursor-not-allowed transition-all shadow-lg hover:shadow-xl">
                {isUploading ? 'Uploading...' : 'Upload'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
