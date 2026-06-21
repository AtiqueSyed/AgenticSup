/* eslint-disable */
import React, { useRef } from 'react';
import { FileText, Trash2, Info, Plus, FileSpreadsheet, FileCode } from 'lucide-react';
import { registerDynamicTable } from '../utils/mockData';

const TRANSLATIONS = {
  en: {
    buildKnowledge: 'Build knowledge',
    myFiles: 'My Files',
    addFiles: 'Add files',
    noFiles: 'No files yet'
  },
  hi: {
    buildKnowledge: 'ज्ञान संचय (Build)',
    myFiles: 'मेरी फाइलें',
    addFiles: 'फाइलें जोड़ें',
    noFiles: 'कोई फाइल नहीं है'
  }
};

export default function KnowledgeSidebar({ 
  lang, 
  uploadedFiles, 
  setUploadedFiles, 
  isRightSidebarCollapsed, 
  setIsRightSidebarCollapsed 
}) {
  const fileInputRef = useRef(null);
  const t = TRANSLATIONS[lang];

  const handleAddFileClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (e) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      
      // Basic check for file count limit
      if (uploadedFiles.length >= 10) {
        alert("Maximum limit of 10 files reached.");
        break;
      }

      // Check if file is CSV/JSON to register as dynamic schema table
      const fileExtension = file.name.split('.').pop().toLowerCase();
      
      if (fileExtension === 'csv') {
        const reader = new FileReader();
        reader.onload = (evt) => {
          const text = evt.target.result;
          parseAndRegisterCsv(file.name, text);
        };
        reader.readAsText(file);
      }

      const newFileObj = {
        id: Math.random().toString(36).substr(2, 9),
        name: file.name,
        size: (file.size / 1024).toFixed(1) + ' KB',
        type: fileExtension
      };

      setUploadedFiles(prev => [...prev, newFileObj]);
    }
    
    // Clear file selection value to allow re-uploading same file
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // Basic CSV parser to extract columns and register custom table inside mock db engine
  const parseAndRegisterCsv = (filename, csvText) => {
    const tableName = filename.split('.')[0].toLowerCase().replace(/[^a-z0-9]/g, '_');
    const lines = csvText.split('\n').map(line => line.trim()).filter(line => line.length > 0);
    if (lines.length === 0) return;

    const headers = lines[0].split(',').map(h => h.trim().replace(/['"]/g, ''));
    const dataRows = [];

    for (let i = 1; i < lines.length; i++) {
      const cols = lines[i].split(',').map(c => c.trim().replace(/['"]/g, ''));
      const rowObj = {};
      headers.forEach((header, idx) => {
        rowObj[header] = cols[idx] || '';
      });
      dataRows.push(rowObj);
    }

    // Register it to mockData engine
    registerDynamicTable(tableName, headers, dataRows);
    console.log(`Registered table ${tableName} from file upload with headers:`, headers);
  };

  const handleDeleteFile = (id) => {
    setUploadedFiles(prev => prev.filter(file => file.id !== id));
  };

  const getFileIcon = (type) => {
    switch (type) {
      case 'pdf':
        return <div className="pdf-icon-badge">pdf</div>;
      case 'csv':
      case 'xlsx':
        return <FileSpreadsheet size={16} className="file-icon xlsx" />;
      case 'json':
      case 'xml':
        return <FileCode size={16} className="file-icon json" />;
      default:
        return <FileText size={16} className="file-icon text" />;
    }
  };

  if (isRightSidebarCollapsed) {
    return (
      <div className="right-sidebar-collapsed flex-center">
        <button 
          onClick={() => setIsRightSidebarCollapsed(false)}
          className="collapsed-open-btn flex-center"
          title="Open Build Knowledge Panel"
        >
          <Plus size={18} />
        </button>
      </div>
    );
  }

  return (
    <div className="right-sidebar">
      {/* Header */}
      <div className="right-sidebar-header">
        <button 
          className="close-right-sidebar flex-center"
          onClick={() => setIsRightSidebarCollapsed(true)}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
        <span className="build-knowledge-title">{t.buildKnowledge}</span>
      </div>

      {/* Files Sub-header */}
      <div className="files-section-header">
        <div className="my-files-label">
          <FileText size={16} />
          <span>{t.myFiles}</span>
          <Info size={13} className="info-icon" data-tooltip="Ingested files used as contextual knowledge for NL2QL queries" />
        </div>
        
        {uploadedFiles.length > 0 && (
          <button 
            className="clear-all-files flex-center"
            onClick={() => setUploadedFiles([])}
            title="Remove all files"
          >
            <Trash2 size={15} />
          </button>
        )}
      </div>

      {/* Upload Drag and Drop box */}
      <div className="add-files-dropzone flex-center" onClick={handleAddFileClick}>
        <Plus size={16} />
        <span>{t.addFiles}</span>
        <span className="file-count-fraction">{uploadedFiles.length}/10</span>
        
        <input 
          type="file" 
          ref={fileInputRef}
          style={{ display: 'none' }}
          onChange={handleFileChange}
          multiple
          accept=".pdf,.csv,.txt,.xlsx,.json"
        />
      </div>

      {/* File List */}
      <div className="uploaded-files-list">
        {uploadedFiles.length > 0 ? (
          uploadedFiles.map(file => (
            <div key={file.id} className="uploaded-file-card">
              <div className="file-card-details">
                {getFileIcon(file.type)}
                <div className="file-text-info">
                  <span className="file-name-span" title={file.name}>{file.name}</span>
                  <span className="file-size-span">{file.size}</span>
                </div>
              </div>
              
              <button 
                className="delete-single-file-btn flex-center"
                onClick={() => handleDeleteFile(file.id)}
                title="Remove file"
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))
        ) : (
          <div className="empty-files-placeholder flex-center">
            <span>{t.noFiles}</span>
          </div>
        )}
      </div>
    </div>
  );
}
