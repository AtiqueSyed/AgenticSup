/* eslint-disable */
import React, { useState, useRef, useEffect } from 'react';
import { 
  FilePlus, 
  Share2, 
  Save, 
  Download, 
  Copy, 
  Undo2, 
  Redo2, 
  Type, 
  Heading1, 
  Heading2, 
  Heading3, 
  AlignLeft, 
  AlignCenter, 
  AlignRight, 
  Grid, 
  Columns, 
  ChevronUp, 
  Check 
} from 'lucide-react';

const INITIAL_REPORT = `<h2>RBI SUPERVISORY EVALUATION REPORT - CONFIDENTIAL</h2>
<p><strong>Appraisal Cycle:</strong> FY 2022-2023</p>
<p><strong>Supervised Entity:</strong> Commercial Banking Divisions</p>
<hr />
<br />
<h3>1. Executive Summary</h3>
<p>Following a statutory inspection for supervisory evaluation (ISE 2023) conducted under Section 35 of the Banking Regulation Act, 1949, this report presents the key findings regarding compliance and operational safeguards.</p>
<br />
<h3>2. Detailed Findings on Violations</h3>
<p>Our review identified critical issues concerning customer protection directives and transactional operations:</p>
<ul>
  <li><strong>Shadow Reversal Failures:</strong> The inspection highlighted failures in crediting the amount involved in unauthorized electronic transactions (shadow reversal) to customer accounts within 10 working days.</li>
  <li><strong>Delayed Compensations:</strong> Delays exceeding 90 days from the date of receipt of complaints were logged in multiple customer service circles.</li>
  <li><strong>Current Account Maintenance:</strong> Deficiencies in compliance with current account opening policies were recorded, prompting regulatory penalties.</li>
</ul>
<br />
<h3>3. Directive Orders</h3>
<p>After due consideration of representations, the supervised entities are directed to submit a board-approved rectification action plan (RAP) to the Central Office for approval within 30 days. Failure to comply will invite further enforcement actions under Section 47A(1)(c) read with Section 46(4)(i) of the Act.</p>`;

export default function DocumentEditor({ lang }) {
  const [docContent, setDocContent] = useState(INITIAL_REPORT);
  const [isCopied, setIsCopied] = useState(false);
  const [isSaved, setIsSaved] = useState(false);
  const [alignment, setAlignment] = useState('left');
  
  const editorRef = useRef(null);
  
  // History stacks for Undo/Redo
  const [history, setHistory] = useState([INITIAL_REPORT]);
  const [historyIndex, setHistoryIndex] = useState(0);

  const handleEditorInput = () => {
    if (editorRef.current) {
      const newContent = editorRef.current.innerHTML;
      setDocContent(newContent);
      
      // Update history stack
      const newHistory = history.slice(0, historyIndex + 1);
      newHistory.push(newContent);
      // Cap history at 50 states
      if (newHistory.length > 50) newHistory.shift();
      
      setHistory(newHistory);
      setHistoryIndex(newHistory.length - 1);
    }
  };

  const handleUndo = () => {
    if (historyIndex > 0) {
      const nextIndex = historyIndex - 1;
      setHistoryIndex(nextIndex);
      setDocContent(history[nextIndex]);
      if (editorRef.current) editorRef.current.innerHTML = history[nextIndex];
    }
  };

  const handleRedo = () => {
    if (historyIndex < history.length - 1) {
      const nextIndex = historyIndex + 1;
      setHistoryIndex(nextIndex);
      setDocContent(history[nextIndex]);
      if (editorRef.current) editorRef.current.innerHTML = history[nextIndex];
    }
  };

  // Format commands using document.execCommand (standard for contentEditable styling)
  const executeFormat = (command, value = null) => {
    document.execCommand(command, false, value);
    handleEditorInput();
  };

  const handleAlignment = (align) => {
    setAlignment(align);
    executeFormat(`justify${align.charAt(0).toUpperCase() + align.slice(1)}`);
  };

  const handleSave = () => {
    setIsSaved(true);
    setTimeout(() => setIsSaved(false), 2000);
  };

  const handleCopy = () => {
    if (editorRef.current) {
      // Copy text version of the HTML
      navigator.clipboard.writeText(editorRef.current.innerText);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    }
  };

  const handleDownload = () => {
    if (editorRef.current) {
      const element = document.createElement("a");
      const file = new Blob([editorRef.current.innerText], {type: 'text/plain'});
      element.href = URL.createObjectURL(file);
      element.download = `rbi_supervisory_report_${new Date().toISOString().slice(0,10)}.txt`;
      document.body.appendChild(element);
      element.click();
      document.body.removeChild(element);
    }
  };

  const handleCreateNew = () => {
    if (window.confirm("Do you want to create a new blank document? All unsaved edits will be lost.")) {
      const emptyContent = "<h2>NEW REPORT</h2><p>Start typing here...</p>";
      setDocContent(emptyContent);
      if (editorRef.current) editorRef.current.innerHTML = emptyContent;
      setHistory([emptyContent]);
      setHistoryIndex(0);
    }
  };

  return (
    <div className="doc-editor-container">
      {/* Top Document Actions Header (Matches top-right actions in Image 1) */}
      <div className="editor-top-actions">
        <div className="doc-meta-title">
          <span>rbi_supervisory_report.txt</span>
        </div>
        <div className="doc-buttons flex-center">
          <button onClick={handleCreateNew} className="action-icon-btn flex-center" data-tooltip="New Document">
            <FilePlus size={18} />
          </button>
          
          <button className="action-icon-btn flex-center" data-tooltip="Share Report">
            <Share2 size={18} />
          </button>

          <button onClick={handleSave} className="action-icon-btn flex-center" data-tooltip="Save Edits">
            {isSaved ? <Check size={18} className="saved-icon" /> : <Save size={18} />}
          </button>

          <button onClick={handleDownload} className="action-icon-btn flex-center" data-tooltip="Download File">
            <Download size={18} />
          </button>

          <button onClick={handleCopy} className="action-icon-btn flex-center" data-tooltip="Copy Content">
            {isCopied ? <Check size={18} className="copied-icon" /> : <Copy size={18} />}
          </button>
        </div>
      </div>

      {/* Formatting Tool Bar (Matches middle toolbar in Image 1) */}
      <div className="formatting-bar">
        <div className="format-group">
          <button onClick={handleUndo} disabled={historyIndex === 0} className="format-btn flex-center" title="Undo (Ctrl+Z)">
            <Undo2 size={16} />
          </button>
          <button onClick={handleRedo} disabled={historyIndex === history.length - 1} className="format-btn flex-center" title="Redo (Ctrl+Y)">
            <Redo2 size={16} />
          </button>
        </div>

        <div className="format-divider" />

        <div className="format-group">
          <button onClick={() => executeFormat('formatBlock', 'p')} className="format-btn flex-center" title="Normal Paragraph Text">
            <Type size={16} />
          </button>
          <button onClick={() => executeFormat('formatBlock', 'h1')} className="format-btn flex-center" title="Heading 1">
            <Heading1 size={16} />
          </button>
          <button onClick={() => executeFormat('formatBlock', 'h2')} className="format-btn flex-center" title="Heading 2">
            <Heading2 size={16} />
          </button>
          <button onClick={() => executeFormat('formatBlock', 'h3')} className="format-btn flex-center" title="Heading 3">
            <Heading3 size={16} />
          </button>
        </div>

        <div className="format-divider" />

        <div className="format-group">
          <button 
            onClick={() => handleAlignment('left')} 
            className={`format-btn flex-center ${alignment === 'left' ? 'active-fmt' : ''}`} 
            title="Align Left"
          >
            <AlignLeft size={16} />
          </button>
          <button 
            onClick={() => handleAlignment('center')} 
            className={`format-btn flex-center ${alignment === 'center' ? 'active-fmt' : ''}`} 
            title="Align Center"
          >
            <AlignCenter size={16} />
          </button>
          <button 
            onClick={() => handleAlignment('right')} 
            className={`format-btn flex-center ${alignment === 'right' ? 'active-fmt' : ''}`} 
            title="Align Right"
          >
            <AlignRight size={16} />
          </button>
        </div>

        <div className="format-divider" />

        <div className="format-group">
          <button className="format-btn flex-center" title="Insert Table Grid" onClick={() => executeFormat('insertHTML', '<table border="1" style="border-collapse:collapse; width:100%"><tr><th>Header 1</th><th>Header 2</th></tr><tr><td>Row 1</td><td>Data</td></tr></table>')}>
            <Grid size={16} />
          </button>
          <button className="format-btn flex-center" title="Insert Columns layout" onClick={() => executeFormat('insertHTML', '<div style="display:flex;gap:16px"><div style="flex:1">Column 1</div><div style="flex:1">Column 2</div></div>')}>
            <Columns size={16} />
          </button>
        </div>

        <div className="format-align-end">
          <button className="format-btn flex-center" title="Collapse Toolbar">
            <ChevronUp size={16} />
          </button>
        </div>
      </div>

      {/* Editor Content Area (Matches edit field in Image 1) */}
      <div className="document-workspace">
        <div 
          className="editable-canvas"
          contentEditable
          ref={editorRef}
          onInput={handleEditorInput}
          dangerouslySetInnerHTML={{ __html: docContent }}
          style={{ textAlign: alignment }}
        />
      </div>
      
      {/* Toast Alert for Copy/Save actions */}
      {(isCopied || isSaved) && (
        <div className="editor-toast-message">
          {isCopied ? "Text copied to clipboard!" : "Document saved successfully!"}
        </div>
      )}
    </div>
  );
}
