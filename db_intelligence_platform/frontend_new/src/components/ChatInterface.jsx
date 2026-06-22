/* eslint-disable no-unused-vars */
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  Plus, 
  Settings, 
  Send, 
  RefreshCw, 
  ThumbsUp, 
  ThumbsDown, 
  Copy, 
  Trash2, 
  Database, 
  User,
  BarChart2, 
  ChevronDown, 
  ChevronUp, 
  Check, 
  Code,
  FileSpreadsheet,
  Search
} from 'lucide-react';

// Lightweight zero-dependency canvas bar chart
function CanvasBarChart({ chartSpec, theme }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    if (!canvasRef.current || !chartSpec) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const W = canvas.offsetWidth || 500;
    const H = 220;
    canvas.width = W;
    canvas.height = H;

    // Extract labels + values from ECharts-style spec
    const labels = chartSpec?.xAxis?.data || [];
    const series = chartSpec?.series || [];
    const values = series[0]?.data || [];
    if (!labels.length || !values.length) {
      ctx.fillStyle = theme === 'light' ? '#64748b' : '#94a3b8';
      ctx.font = '13px Inter, sans-serif';
      ctx.fillText('No chart data available', 20, H / 2);
      return;
    }

    const numericVals = values.map(v => Number(v) || 0);
    const maxVal = Math.max(...numericVals, 1);
    const pad = { top: 20, right: 20, bottom: 50, left: 60 };
    const chartW = W - pad.left - pad.right;
    const chartH = H - pad.top - pad.bottom;
    const barW = Math.max(6, Math.floor(chartW / labels.length) - 6);

    // Background
    ctx.fillStyle = 'transparent';
    ctx.clearRect(0, 0, W, H);

    // Y-axis gridlines
    const gridLines = 4;
    for (let i = 0; i <= gridLines; i++) {
      const y = pad.top + chartH - (i / gridLines) * chartH;
      ctx.beginPath();
      ctx.strokeStyle = theme === 'light' ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.06)';
      ctx.lineWidth = 1;
      ctx.moveTo(pad.left, y);
      ctx.lineTo(pad.left + chartW, y);
      ctx.stroke();
      const labelVal = ((maxVal * i) / gridLines).toFixed(0);
      ctx.fillStyle = theme === 'light' ? '#475569' : '#64748b';
      ctx.font = '10px Inter, sans-serif';
      ctx.textAlign = 'right';
      ctx.fillText(labelVal, pad.left - 6, y + 3);
    }

    // Bars
    labels.forEach((label, idx) => {
      const val = numericVals[idx];
      const bh = Math.max(2, (val / maxVal) * chartH);
      const x = pad.left + idx * (chartW / labels.length) + (chartW / labels.length - barW) / 2;
      const y = pad.top + chartH - bh;

      // Gradient bar
      const grad = ctx.createLinearGradient(x, y, x, y + bh);
      grad.addColorStop(0, '#a855f7');
      grad.addColorStop(1, '#7c3aed');
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.roundRect(x, y, barW, bh, [3, 3, 0, 0]);
      ctx.fill();

      // X-label
      ctx.fillStyle = theme === 'light' ? '#475569' : '#94a3b8';
      ctx.font = '9px Inter, sans-serif';
      ctx.textAlign = 'center';
      const shortLabel = String(label).length > 10 ? String(label).slice(0, 9) + '…' : String(label);
      ctx.fillText(shortLabel, x + barW / 2, H - pad.bottom + 14);

      // Value on top
      ctx.fillStyle = theme === 'light' ? '#0f172a' : '#e2e8f0';
      ctx.font = 'bold 9px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(val.toLocaleString(), x + barW / 2, y - 4);
    });
  }, [chartSpec, theme]);

  return (
    <canvas
      ref={canvasRef}
      style={{ width: '100%', height: '220px', display: 'block' }}
    />
  );
}

const TRANSLATIONS = {
  en: {
    hello: 'Hello Tej,',
    howCanIHelp: 'How can I help you today?',
    typeQuery: 'Type your query',
    disabledBankData: 'Disabled: Bank Data',
    enabledBankData: 'Enabled: Bank Data',
    findingSolution: 'Finding a solution to your query',
    schemaViewer: 'Database Schema Browser',
    samplePrompts: 'Suggested NL2QL Queries',
    copysql: 'Copy SQL',
    sqlQuery: 'Compiled SQL Query',
    agentReasoning: 'Agent Reasoning Path',
    queryResults: 'Query Output Rows',
    visualChart: 'Data Chart Analysis'
  },
  hi: {
    hello: 'नमस्ते तेज,',
    howCanIHelp: 'आज मैं आपकी क्या सहायता कर सकता हूँ?',
    typeQuery: 'अपना प्रश्न यहाँ टाइप करें',
    disabledBankData: 'अक्षम: बैंक डेटा',
    enabledBankData: 'सक्षम: बैंक डेटा',
    findingSolution: 'आपके प्रश्न का समाधान खोजा जा रहा है',
    schemaViewer: 'डेटाबेस स्कीमा ब्राउज़र',
    samplePrompts: 'सुझाए गए NL2QL प्रश्न',
    copysql: 'SQL कॉपी करें',
    sqlQuery: 'संकलित SQL प्रश्न',
    agentReasoning: 'एजेंट सोच पथ (Reasoning)',
    queryResults: 'क्वेरी परिणाम पंक्तियाँ',
    visualChart: 'डेटा चार्ट विश्लेषण'
  }
};

const SUGGESTIONS = [
  { text: 'What is the total lending observed value?', label: 'Lending Observed Value (CIMS)' },
  { text: 'What are the issues for which SBI has been penalised by RBI in the recent past?', label: 'SBI Penalties (CMS)' },
  { text: 'What is my supervisory evaluation?', label: 'My Performance Appraisal (CIMS)' },
  { text: 'Compare total penalties by bank', label: 'Penalty Comparison Chart' }
];

const REGULATED_ENTITIES = [
  "State Bank of India (SBI)",
  "HDFC Bank",
  "ICICI Bank",
  "Axis Bank",
  "Bank of Baroda",
  "Punjab National Bank",
  "Canara Bank",
  "Union Bank of India",
  "Indian Bank",
  "Bank of India",
  "Central Bank of India",
  "Indian Overseas Bank",
  "UCO Bank",
  "Bank of Maharashtra",
  "Punjab & Sind Bank",
  "Kotak Mahindra Bank",
  "IndusInd Bank",
  "Federal Bank",
  "IDBI Bank",
  "Yes Bank",
  "South Indian Bank"
];

export default function ChatInterface({ lang, theme = 'dark', presetQuery, clearPresetQuery, onNewChatSession, userRole = 'user' }) {
  const [messages, setMessages] = useState([]);
  const [inputVal, setInputVal] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [dbList, setDbList] = useState([]);
  
  // Search Context states from the input settings gear popover (default checked at start)
  const [bankDataChecked, setBankDataChecked] = useState(true);
  const [myFilesChecked, setMyFilesChecked] = useState(true);
  const [chatWithDbEnabled, setChatWithDbEnabled] = useState(true);
  const [showSettingsDropdown, setShowSettingsDropdown] = useState(false);
  
  const [selectedEntities, setSelectedEntities] = useState(REGULATED_ENTITIES);
  const [showEntityDropdown, setShowEntityDropdown] = useState(false);
  const [showDbSetupPage, setShowDbSetupPage] = useState(true);
  
  const [entitySearchVal, setEntitySearchVal] = useState('');
  const [showSetupEntityDropdown, setShowSetupEntityDropdown] = useState(false);
  const [refreshSchemasKey, setRefreshSchemasKey] = useState(0);
  
  const [showSchema, setShowSchema] = useState(false);
  const [copiedMsgId, setCopiedMsgId] = useState(null);
  const [showThoughts, setShowThoughts] = useState({});

  const chatEndRef = useRef(null);
  const settingsRef = useRef(null); // Ref to detect clicks outside dropdown
  const entityDropdownRef = useRef(null); // Ref to detect clicks outside entity selection dropdown
  const entitySetupDropdownRef = useRef(null); // Ref to detect clicks outside setup entities dropdown
  const schemaFileInputRef = useRef(null); // Ref to schema upload file picker input
  const t = TRANSLATIONS[lang];

  // Fetch registered databases from the backend stats
  const fetchDbList = async () => {
    try {
      const res = await fetch("/api/v1/stats");
      if (!res.ok) throw new Error("Stats request failed");
      const data = await res.json();
      setDbList(data.databases || []);
    } catch (err) {
      console.error("Failed to fetch database stats:", err);
    }
  };

  useEffect(() => {
    fetchDbList();
  }, [refreshSchemasKey]);

  // Close dropdowns if clicked outside their boundaries
  useEffect(() => {
    function handleClickOutside(event) {
      if (settingsRef.current && !settingsRef.current.contains(event.target)) {
        setShowSettingsDropdown(false);
      }
      if (entityDropdownRef.current && !entityDropdownRef.current.contains(event.target)) {
        setShowEntityDropdown(false);
      }
      if (entitySetupDropdownRef.current && !entitySetupDropdownRef.current.contains(event.target)) {
        setShowSetupEntityDropdown(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [settingsRef, entityDropdownRef, entitySetupDropdownRef]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleSend = useCallback(async (queryText) => {
    const textToSend = queryText || inputVal;
    if (!textToSend.trim()) return;

    // Clear input
    setInputVal('');

    // Update parent Recent Chats history list dynamically
    if (onNewChatSession) {
      onNewChatSession(textToSend);
    }

    // Add user message
    const userMsg = {
      id: Math.random().toString(36).substr(2, 9),
      sender: 'user',
      text: textToSend,
      timestamp: new Date().toLocaleString('en-US', { month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: true })
    };

    setMessages(prev => [...prev, userMsg]);
    setIsLoading(true);

    try {
      // POST to backend query endpoint
      const response = await fetch("/api/v1/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          database_id: null, // Allow global query database auto-routing
          question: textToSend
        })
      });

      if (!response.ok) {
        throw new Error("Failed to compile or execute SQL statement against the target databases.");
      }

      const data = await response.json();

      let columns = [];
      let rows = [];
      if (data.results && data.results.length > 0) {
        columns = Object.keys(data.results[0]);
        rows = data.results;
      }

      const thoughts = [
        { step: "Intent Identification", desc: `Analyzing input: "${textToSend}".` },
        { step: "Database Schema Auto-Routing", desc: data.database_id ? `Routed query to Database ID: [${data.database_name || data.database_id}]` : "No specific database matching." },
        { step: "NL2QL dialect generation", desc: data.sql_used ? "Successfully synthesized SQL dialect." : "No SQL generated." },
        { step: "Execution Verification", desc: "Fetched records matching schema targets from Oracle DB." }
      ];

      const agentMsg = {
        id: Math.random().toString(36).substr(2, 9),
        sender: 'agent',
        text: data.answer || "No response generated.",
        sql: data.sql_used,
        thoughts: thoughts,
        columns: columns,
        rows: rows,
        chartSpec: data.visualizations?.spec,
        databaseName: data.database_name || data.database_id,
        timestamp: new Date().toLocaleString('en-US', { month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: true })
      };

      setMessages(prev => [...prev, agentMsg]);

    } catch (error) {
      console.error(error);
      const errMsg = {
        id: Math.random().toString(36).substr(2, 9),
        sender: 'agent',
        text: `Error processing query: ${error.message}. Please verify the backend is running and databases are onboarded.`,
        timestamp: new Date().toLocaleString('en-US', { month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: true })
      };
      setMessages(prev => [...prev, errMsg]);
    } finally {
      setIsLoading(false);
    }
  }, [inputVal, onNewChatSession]);

  useEffect(() => {
    if (presetQuery) {
      const q = presetQuery;
      clearPresetQuery();
      const timer = setTimeout(() => {
        handleSend(q);
      }, 0);
      return () => clearTimeout(timer);
    }
  }, [presetQuery, handleSend, clearPresetQuery]);

  const handleCopyText = (text, id) => {
    navigator.clipboard.writeText(text);
    setCopiedMsgId(id);
    setTimeout(() => setCopiedMsgId(null), 1500);
  };

  const handleDeleteMessage = (id) => {
    setMessages(prev => prev.filter(m => m.id !== id));
  };

  const toggleThoughts = (id) => {
    setShowThoughts(prev => ({
      ...prev,
      [id]: !prev[id]
    }));
  };

  // Basic Markdown Bold/List parser
  const renderMarkdown = (text) => {
    if (!text) return null;
    const lines = text.split('\n');
    return lines.map((line, idx) => {
      let content = line;
      let elementKey = `line-${idx}`;

      // Check for headings: ### Header
      if (content.startsWith('### ')) {
        return <h4 key={elementKey} className="md-h3" style={{ fontSize: '14px', margin: '12px 0 6px 0', color: 'var(--text-primary)', fontWeight: '600' }}>{content.replace('### ', '')}</h4>;
      }
      
      // Check for bullet lists: * List
      if (content.startsWith('* ')) {
        const itemText = content.replace('* ', '');
        return (
          <li key={elementKey} className="md-li" style={{ marginLeft: '16px', listStyleType: 'disc', color: 'var(--text-secondary)', marginBottom: '4px' }}>
            {parseBoldText(itemText)}
          </li>
        );
      }

      // Default paragraph
      return <p key={elementKey} className="md-p" style={{ margin: '6px 0', color: 'var(--text-secondary)' }}>{parseBoldText(content)}</p>;
    });
  };

  const parseBoldText = (text) => {
    const parts = text.split(/\*\*(.*?)\*\*/g);
    return parts.map((part, index) => {
      if (index % 2 === 1) {
        return <strong key={index} className="md-bold" style={{ color: 'var(--text-primary)', fontWeight: '700' }}>{part}</strong>;
      }
      return part;
    });
  };

  if (chatWithDbEnabled && showDbSetupPage) {
    return (
      <div className="db-setup-workspace">
        <div className="db-setup-container">
          {/* Header */}
          <div className="db-setup-header">
            <div className="db-setup-icon-ring flex-center">
              <Database size={18} className="db-setup-header-icon" />
            </div>
            <h1 className="db-setup-title">Database Agent Setup</h1>
            <p className="db-setup-subtitle">
              Verify connected databases and select which regulated entities to include in the supervisory evaluation context.
            </p>
          </div>

          <div className="db-setup-body">
            {/* Section 1: Connected Databases */}
            <div className="db-setup-section">
              <h2 className="db-setup-section-title">Connected Database Tables ({dbList.length})</h2>
              <div className="db-setup-grid">
                {dbList.map((db) => {
                  let dbDesc = `Active connected database with ID: ${db.id}`;
                  
                  if (db.name === 'CIMS') {
                    dbDesc = 'Centralised Information Management System for regulatory reporting, appraisals, and banking metrics.';
                  } else if (db.name === 'CMS') {
                    dbDesc = 'Complaint Management System capturing customer complaints, audits, and compliance records.';
                  } else if (db.name === 'DAKSH') {
                    dbDesc = 'RBI\'s Advanced Supervisory Monitoring System for compliance inspection and penalties.';
                  }

                  return (
                    <div key={db.id} className="db-setup-card">
                      <div className="db-card-header flex-center">
                        <div className="db-card-icon-wrapper flex-center">
                          <Database size={16} />
                        </div>
                        <span className="db-card-name-title">{db.name}</span>
                        <div className="db-card-status flex-center">
                          <span className={db.status === 'completed' ? 'pulsing-green-dot' : 'pulsing-yellow-dot'}></span>
                          <span className="status-text-label">{db.status === 'completed' ? 'Active' : 'Onboarding'}</span>
                        </div>
                      </div>
                      <p className="db-card-desc">{dbDesc}</p>
                    </div>
                  );
                })}

                {/* Upload Dynamic Schema Card Link */}
                <div className="db-setup-upload-card flex-center" onClick={() => setRefreshSchemasKey(prev => prev + 1)}>
                  <div className="upload-card-content flex-center">
                    <div className="upload-icon-wrapper flex-center">
                      <RefreshCw size={24} />
                    </div>
                    <span className="upload-card-title">Refresh Databases</span>
                    <span className="upload-card-subtitle">Sync connected databases from backend registry</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Section 2: Regulated Entities Searchable Dropdown */}
            <div className="db-setup-section" ref={entitySetupDropdownRef}>
              <h2 className="db-setup-section-title">Select Regulated Entities Context</h2>
              <div className="setup-searchable-dropdown">
                <button
                  type="button"
                  className="setup-dropdown-trigger flex-center"
                  onClick={() => setShowSetupEntityDropdown(!showSetupEntityDropdown)}
                >
                  <span className="trigger-text">
                    {selectedEntities.length === REGULATED_ENTITIES.length 
                      ? `All Entities (${selectedEntities.length})` 
                      : selectedEntities.length === 0 
                        ? "No Entities Selected" 
                        : `Selected (${selectedEntities.length} Entities)`}
                  </span>
                  <ChevronDown size={16} className={`trigger-arrow ${showSetupEntityDropdown ? 'open' : ''}`} />
                </button>

                {showSetupEntityDropdown && (
                  <div className="setup-dropdown-popover">
                    <div className="dropdown-search-wrapper flex-center">
                      <Search size={14} className="search-icon" />
                      <input
                        type="text"
                        className="dropdown-search-input"
                        placeholder="Search banks/entities..."
                        value={entitySearchVal}
                        onChange={(e) => setEntitySearchVal(e.target.value)}
                      />
                      {entitySearchVal && (
                        <button 
                          type="button" 
                          className="search-clear-btn" 
                          onClick={() => setEntitySearchVal('')}
                        >
                          ×
                        </button>
                      )}
                    </div>

                    <div className="dropdown-actions-row flex-center">
                      <button 
                        type="button" 
                        className="popover-action-btn"
                        onClick={() => setSelectedEntities(REGULATED_ENTITIES)}
                      >
                        Select All
                      </button>
                      <span className="divider-dot">•</span>
                      <button 
                        type="button" 
                        className="popover-action-btn"
                        onClick={() => setSelectedEntities([])}
                      >
                        Clear All
                      </button>
                    </div>

                    <div className="dropdown-options-list">
                      {(() => {
                        const filtered = REGULATED_ENTITIES.filter(entity => 
                          entity.toLowerCase().includes(entitySearchVal.toLowerCase())
                        );

                        if (filtered.length === 0) {
                          return <div className="dropdown-empty-state">No matching entities found</div>;
                        }

                        return filtered.map((entity) => {
                          const isChecked = selectedEntities.includes(entity);
                          return (
                            <label key={entity} className={`dropdown-option-item flex-center ${isChecked ? 'active' : ''}`}>
                              <input 
                                type="checkbox"
                                className="entity-option-checkbox"
                                checked={isChecked}
                                onChange={() => {
                                  if (isChecked) {
                                    setSelectedEntities(prev => prev.filter(e => e !== entity));
                                  } else {
                                    setSelectedEntities(prev => [...prev, entity]);
                                  }
                                }}
                              />
                              <span className="entity-option-label">{entity}</span>
                            </label>
                          );
                        });
                      })()}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Action Footer with Proceed Button */}
          <div className="db-setup-footer flex-center">
            <button 
              type="button"
              className="proceed-setup-btn flex-center"
              onClick={() => setShowDbSetupPage(false)}
            >
              <span>Proceed to Evaluation Chat</span>
              <Settings size={14} style={{ marginLeft: '6px' }} />
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-interface-wrapper">
      {chatWithDbEnabled && (
        <div className="db-context-header flex-center">
          <div className="db-status-section flex-center">
            <span className="db-section-title">Connected Databases:</span>
            <div className="db-badges-list flex-center">
              {dbList.map((db) => (
                <div key={db.id} className="db-badge flex-center" title={`Table: ${db.name}`}>
                  <Database size={12} className="db-badge-icon" />
                  <span className="db-badge-name">{db.name}</span>
                  <span className={db.status === 'completed' ? 'pulsing-green-dot' : 'pulsing-yellow-dot'}></span>
                </div>
              ))}
            </div>
          </div>

          <div className="entity-select-section flex-center" ref={entityDropdownRef}>
            <span className="entity-section-title">Regulated Entities:</span>
            <div className="entity-dropdown-container">
              <button 
                type="button"
                className="entity-select-trigger flex-center"
                onClick={() => setShowEntityDropdown(!showEntityDropdown)}
              >
                <span className="trigger-text">
                  {selectedEntities.length === REGULATED_ENTITIES.length 
                    ? `All Entities (${selectedEntities.length})` 
                    : selectedEntities.length === 0 
                      ? "None Selected" 
                      : `Selected (${selectedEntities.length})`}
                </span>
                <ChevronDown size={14} className={`trigger-arrow ${showEntityDropdown ? 'open' : ''}`} />
              </button>

              {showEntityDropdown && (
                <div className="entity-select-popover">
                  <div className="entity-popover-header flex-center">
                    <button 
                      type="button" 
                      className="popover-action-btn"
                      onClick={() => setSelectedEntities(REGULATED_ENTITIES)}
                    >
                      Select All
                    </button>
                    <button 
                      type="button" 
                      className="popover-action-btn"
                      onClick={() => setSelectedEntities([])}
                    >
                      Clear
                    </button>
                  </div>
                  <div className="entity-options-list">
                    {REGULATED_ENTITIES.map((entity) => {
                      const isChecked = selectedEntities.includes(entity);
                      return (
                        <label key={entity} className="entity-option-item flex-center">
                          <input 
                            type="checkbox"
                            className="entity-option-checkbox"
                            checked={isChecked}
                            onChange={() => {
                              if (isChecked) {
                                setSelectedEntities(prev => prev.filter(e => e !== entity));
                              } else {
                                setSelectedEntities(prev => [...prev, entity]);
                              }
                            }}
                          />
                          <span className="entity-option-label">{entity}</span>
                        </label>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
            
            <button 
              type="button"
              className="db-reconfigure-trigger-btn flex-center"
              onClick={() => setShowDbSetupPage(true)}
              title="Re-configure Databases & Entities"
            >
              <Settings size={12} />
              <span>Configure</span>
            </button>
          </div>
        </div>
      )}

      {/* Main chat messages list */}
      <div className="chat-messages-container">
        {messages.length === 0 ? (
          <div className="chat-welcome-screen flex-center">
            <h1 className="welcome-header">
              {userRole === 'admin' 
                ? (lang === 'en' ? 'Hello Chirag Admin,' : 'नमस्ते चिराग एडमिन,') 
                : t.hello
              }
            </h1>
            <h2 className="welcome-subheader">{t.howCanIHelp}</h2>
            
            {/* Suggested prompts list inside welcome view */}
            <div className="suggestions-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '12px', width: '100%', maxWidth: '720px', marginTop: '30px' }}>
              {SUGGESTIONS.map((s, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handleSend(s.text)}
                  style={{
                    background: 'var(--bg-card)',
                    border: '1px solid var(--border-color)',
                    borderRadius: '8px',
                    padding: '12px 16px',
                    textAlign: 'left',
                    color: 'var(--text-secondary)',
                    cursor: 'pointer',
                    fontSize: '12px',
                    lineHeight: '1.4',
                    transition: 'all 0.15s ease',
                    boxShadow: theme === 'light' ? '0 1px 3px rgba(0,0,0,0.05)' : 'none'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = 'var(--accent-purple)';
                    e.currentTarget.style.color = 'var(--text-primary)';
                    e.currentTarget.style.background = 'var(--bg-hover)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = 'var(--border-color)';
                    e.currentTarget.style.color = 'var(--text-secondary)';
                    e.currentTarget.style.background = 'var(--bg-card)';
                  }}
                >
                  <div style={{ fontWeight: '600', color: '#a855f7', marginBottom: '4px' }}>{s.label}</div>
                  <div style={{ color: theme === 'light' ? 'var(--text-primary)' : 'inherit' }}>{s.text}</div>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="chat-thread">
            {messages.map((msg) => (
              <div key={msg.id} className={`chat-message-row ${msg.sender}-msg-row`}>
                
                {/* User message */}
                {msg.sender === 'user' && (
                  <div className="user-message-bubble">
                    <p>{msg.text}</p>
                  </div>
                )}

                {/* Agent response bubble */}
                {msg.sender === 'agent' && (
                  <div className="agent-message-wrapper" style={{ display: 'flex', flexDirection: 'column', gap: '8px', width: '100%', maxWidth: '720px' }}>
                    
                    {/* Database Routing Badge */}
                    {msg.databaseName && (
                      <div className="agent-routed-badge flex-center" style={{ alignSelf: 'flex-start', margin: '4px 0 0 16px', background: 'rgba(16, 185, 129, 0.1)', color: '#10b981', border: '1px solid rgba(16, 185, 129, 0.2)', padding: '3px 8px', borderRadius: '4px', fontSize: '11px', gap: '4px' }}>
                        <Database size={12} />
                        <span>Routed to DB: {msg.databaseName}</span>
                      </div>
                    )}

                    {/* Collapsible Thoughts Trace */}
                    {msg.thoughts && msg.thoughts.length > 0 && (
                      <div className="agent-thoughts-section" style={{ margin: '4px 16px', border: '1px solid var(--border-light)', borderRadius: '6px', overflow: 'hidden' }}>
                        <button
                          type="button"
                          onClick={() => toggleThoughts(msg.id)}
                          className="flex-center"
                          style={{ width: '100%', padding: '8px 12px', background: 'var(--bg-hover)', border: 'none', color: 'var(--text-secondary)', fontSize: '11px', justifyContent: 'space-between', cursor: 'pointer' }}
                        >
                          <span className="flex-center" style={{ gap: '6px' }}><Settings size={12} /> {t.agentReasoning}</span>
                          {showThoughts[msg.id] ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                        </button>
                        {showThoughts[msg.id] && (
                          <div className="thoughts-content-list" style={{ padding: '10px 12px', background: 'var(--bg-card)', fontSize: '11px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                            {msg.thoughts.map((step, idx) => (
                              <div key={idx} style={{ borderLeft: '2px solid #a855f7', paddingLeft: '8px' }}>
                                <strong style={{ color: '#a855f7' }}>{step.step}: </strong>
                                <span style={{ color: 'var(--text-secondary)' }}>{step.desc}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Collapsible SQL Query Block */}
                    {msg.sql && (
                      <div className="agent-sql-section" style={{ margin: '4px 16px', border: '1px solid var(--border-light)', borderRadius: '6px', overflow: 'hidden' }}>
                        <button
                          type="button"
                          onClick={() => {
                            const key = `sql_${msg.id}`;
                            setShowThoughts(prev => ({ ...prev, [key]: !prev[key] }));
                          }}
                          className="flex-center"
                          style={{ width: '100%', padding: '8px 12px', background: 'var(--bg-hover)', border: 'none', color: 'var(--text-secondary)', fontSize: '11px', justifyContent: 'space-between', cursor: 'pointer' }}
                        >
                          <span className="flex-center" style={{ gap: '6px' }}><Code size={12} /> {t.sqlQuery}</span>
                          {showThoughts[`sql_${msg.id}`] ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                        </button>
                        {showThoughts[`sql_${msg.id}`] && (
                          <div className="sql-code-block" style={{ padding: '12px', background: 'var(--bg-primary)', position: 'relative', borderTop: '1px solid var(--border-light)' }}>
                            <pre style={{ margin: 0, fontFamily: 'monospace', color: 'var(--accent-cyan)', fontSize: '12px', overflowX: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                              <code>{msg.sql}</code>
                            </pre>
                            <button
                              type="button"
                              onClick={() => handleCopyText(msg.sql, `sql_${msg.id}`)}
                              style={{
                                position: 'absolute',
                                top: '8px',
                                right: '8px',
                                background: 'var(--bg-card)',
                                border: '1px solid var(--border-light)',
                                color: 'var(--text-secondary)',
                                padding: '4px 8px',
                                borderRadius: '4px',
                                fontSize: '10px',
                                cursor: 'pointer'
                              }}
                            >
                              {copiedMsgId === `sql_${msg.id}` ? 'Copied!' : t.copysql}
                            </button>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Natural language answer text */}
                    <div className="agent-text-bubble">
                      {renderMarkdown(msg.text)}
                    </div>

                    {/* Interactive SQL Output Rows table */}
                    {msg.rows && msg.rows.length > 0 && (
                      <div className="agent-table-section" style={{ margin: '8px 16px', border: '1px solid var(--border-light)', borderRadius: '8px', overflow: 'hidden' }}>
                        <div className="table-header-title flex-center" style={{ padding: '8px 12px', background: 'var(--bg-hover)', color: 'var(--text-secondary)', fontSize: '11px', borderBottom: '1px solid var(--border-light)', gap: '6px', justifyContent: 'flex-start' }}>
                          <FileSpreadsheet size={12} style={{ color: theme === 'light' ? '#7c3aed' : 'inherit' }} />
                          <span>{t.queryResults} ({msg.rows.length} rows)</span>
                        </div>
                        <div style={{ overflowX: 'auto', maxHeight: '200px' }}>
                          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '11px' }}>
                            <thead>
                              <tr style={{ background: 'var(--bg-hover)', color: 'var(--text-primary)', borderBottom: '1px solid var(--border-light)' }}>
                                {msg.columns.map(col => (
                                  <th key={col} style={{ padding: '8px 12px', fontWeight: '600' }}>{col}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {msg.rows.map((row, idx) => (
                                <tr key={idx} style={{ borderBottom: '1px solid var(--border-light)', background: idx % 2 === 0 ? 'transparent' : 'var(--bg-hover)' }}>
                                  {msg.columns.map(col => (
                                    <td key={col} style={{ padding: '8px 12px', color: 'var(--text-secondary)' }}>{String(row[col] ?? '')}</td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {/* Canvas Bar Chart Visualizations */}
                    {msg.chartSpec && (
                      <div className="agent-chart-section" style={{ margin: '8px 16px', border: '1px solid var(--border-light)', borderRadius: '8px', overflow: 'hidden', background: 'var(--bg-card)', padding: '16px', backdropFilter: 'blur(8px)', boxShadow: theme === 'light' ? '0 4px 6px -1px rgba(0,0,0,0.05)' : 'none' }}>
                        <div className="chart-header-title flex-center" style={{ margin: '0 0 12px 0', color: 'var(--text-secondary)', fontSize: '11px', gap: '6px', justifyContent: 'flex-start' }}>
                          <BarChart2 size={12} style={{ color: theme === 'light' ? '#7c3aed' : 'inherit' }} />
                          <span>{t.visualChart}</span>
                        </div>
                        <CanvasBarChart chartSpec={msg.chartSpec} theme={theme} />
                      </div>
                    )}

                    {/* Feedback and Actions tray */}
                    <div className="agent-feedback-bar">
                      <div className="feedback-icons-group flex-center">
                        <button className="fb-btn flex-center" title="Regenerate Solution">
                          <RefreshCw size={14} />
                        </button>
                        <button className="fb-btn flex-center" title="Good Response">
                          <ThumbsUp size={14} />
                        </button>
                        <button className="fb-btn flex-center" title="Bad Response">
                          <ThumbsDown size={14} />
                        </button>
                        <button 
                          className="fb-btn flex-center" 
                          title="Copy Answer Text"
                          onClick={() => handleCopyText(msg.text, msg.id)}
                        >
                          {copiedMsgId === msg.id ? <Check size={14} className="copied-icon" /> : <Copy size={14} />}
                        </button>
                        <button 
                          className="fb-btn flex-center text-danger" 
                          title="Delete Message"
                          onClick={() => handleDeleteMessage(msg.id)}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                      <span className="msg-timestamp">{msg.timestamp}</span>
                    </div>

                  </div>
                )}

              </div>
            ))}

            {/* Pulsing Loading Status */}
            {isLoading && (
              <div className="loading-state-container">
                <span className="pulsing-dot-spinner"></span>
                <span className="loading-text-label">{t.findingSolution}...</span>
              </div>
            )}
            
            <div ref={chatEndRef} />
          </div>
        )}
      </div>

      {/* Query Input capsule input bar */}
      <div className="bottom-controls-bar">
        <div className="data-filter-badge-row flex-center">
          {!bankDataChecked && (
            <button 
              className="data-filter-badge flex-center disabled"
              onClick={() => setBankDataChecked(true)}
            >
              <span>{t.disabledBankData}</span>
              <span className="badge-close-x">×</span>
            </button>
          )}
          {!myFilesChecked && (
            <button 
              className="data-filter-badge flex-center disabled"
              onClick={() => setMyFilesChecked(true)}
              style={{ marginLeft: '8px' }}
            >
              <span>Disabled: My Files</span>
              <span className="badge-close-x">×</span>
            </button>
          )}
        </div>

        <div className="query-capsule-input-container">
          <div className="left-input-actions flex-center">
            <button className="input-shortcut-btn flex-center" title="Attach Files Context">
              <Plus size={18} />
            </button>
            <div className="settings-dropdown-wrapper" ref={settingsRef}>
              <button 
                className="input-shortcut-btn flex-center" 
                title="Agent Parameters Settings"
                onClick={() => setShowSettingsDropdown(!showSettingsDropdown)}
              >
                <Settings size={18} />
              </button>
              {showSettingsDropdown && (
                <div className="settings-context-dropdown">
                  <span className="dropdown-label">SEARCH</span>
                  <label className="dropdown-checkbox-item">
                    <input 
                      type="checkbox" 
                      className="settings-checkbox-input"
                      checked={bankDataChecked}
                      onChange={() => setBankDataChecked(!bankDataChecked)}
                    />
                    <Database size={14} className="checkbox-icon" />
                    <span>Bank Data</span>
                  </label>
                  <label className="dropdown-checkbox-item">
                    <input 
                      type="checkbox" 
                      className="settings-checkbox-input"
                      checked={myFilesChecked}
                      onChange={() => setMyFilesChecked(!myFilesChecked)}
                    />
                    <User size={14} className="checkbox-icon" />
                    <span>My Files</span>
                  </label>

                  <span className="dropdown-label" style={{ marginTop: '4px' }}>DATABASE</span>
                  <label className="dropdown-checkbox-item">
                    <input 
                      type="checkbox" 
                      className="settings-checkbox-input"
                      checked={chatWithDbEnabled}
                      onChange={() => {
                        const newVal = !chatWithDbEnabled;
                        setChatWithDbEnabled(newVal);
                        setShowDbSetupPage(newVal);
                      }}
                    />
                    <Database size={14} className="checkbox-icon" />
                    <span>Enable Chat with DB</span>
                  </label>
                </div>
              )}
            </div>
          </div>
          
          <input 
            type="text" 
            placeholder={t.typeQuery} 
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSend();
            }}
          />

          <button 
            className="submit-query-btn flex-center" 
            onClick={() => handleSend()}
            disabled={!inputVal.trim()}
            title="Execute Query"
          >
            <Send size={16} />
          </button>
        </div>

        {/* Footer Support Info */}
        <div className="chat-footer-support flex-center">
          <div className="support-item flex-center">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path>
              <polyline points="22,6 12,13 2,6"></polyline>
            </svg>
            <span>chiragsupport@rbi.org.in</span>
          </div>
          <div className="support-item flex-center">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"></path>
            </svg>
            <span>+22-27595554</span>
          </div>
        </div>
      </div>
    </div>
  );
}
