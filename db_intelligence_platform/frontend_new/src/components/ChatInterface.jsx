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
  Search,
  AlertTriangle,
  ArrowRight
} from 'lucide-react';
import { palette } from '../theme';
import { messageEnter, listEnter } from '../motion';

const CHART_FONT_STACK = "-apple-system, BlinkMacSystemFont, 'SF Pro Text', sans-serif";

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
    const c = palette(theme);

    // Extract labels + values from ECharts-style spec
    const labels = chartSpec?.xAxis?.data || [];
    const series = chartSpec?.series || [];
    const values = series[0]?.data || [];
    if (!labels.length || !values.length) {
      ctx.fillStyle = c.textMuted;
      ctx.font = `13px ${CHART_FONT_STACK}`;
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
    ctx.clearRect(0, 0, W, H);

    // Y-axis gridlines
    const gridLines = 4;
    for (let i = 0; i <= gridLines; i++) {
      const y = pad.top + chartH - (i / gridLines) * chartH;
      ctx.beginPath();
      ctx.strokeStyle = c.border;
      ctx.lineWidth = 1;
      ctx.moveTo(pad.left, y);
      ctx.lineTo(pad.left + chartW, y);
      ctx.stroke();
      const labelVal = ((maxVal * i) / gridLines).toFixed(0);
      ctx.fillStyle = c.textMuted;
      ctx.font = `10px ${CHART_FONT_STACK}`;
      ctx.textAlign = 'right';
      ctx.fillText(labelVal, pad.left - 6, y + 3);
    }

    // Bars
    labels.forEach((label, idx) => {
      const val = numericVals[idx];
      const bh = Math.max(2, (val / maxVal) * chartH);
      const x = pad.left + idx * (chartW / labels.length) + (chartW / labels.length - barW) / 2;
      const y = pad.top + chartH - bh;

      ctx.fillStyle = c.accent;
      ctx.beginPath();
      ctx.roundRect(x, y, barW, bh, [3, 3, 0, 0]);
      ctx.fill();

      // X-label
      ctx.fillStyle = c.textSecondary;
      ctx.font = `9px ${CHART_FONT_STACK}`;
      ctx.textAlign = 'center';
      const shortLabel = String(label).length > 10 ? String(label).slice(0, 9) + '…' : String(label);
      ctx.fillText(shortLabel, x + barW / 2, H - pad.bottom + 14);

      // Value on top
      ctx.fillStyle = c.text;
      ctx.font = `bold 9px ${CHART_FONT_STACK}`;
      ctx.textAlign = 'center';
      ctx.fillText(val.toLocaleString(), x + barW / 2, y - 4);
    });
  }, [chartSpec, theme]);

  return <canvas ref={canvasRef} className="chart-canvas" />;
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

  // Ease the newest row in rather than having it pop. Reads the DOM only; the
  // message list itself is untouched.
  useEffect(() => {
    const rows = document.querySelectorAll('.chat-thread .chat-message-row');
    messageEnter(rows[rows.length - 1]);
  }, [messages.length]);

  // Stagger the welcome suggestions on first paint.
  useEffect(() => {
    if (messages.length === 0) {
      listEnter(document.querySelectorAll('.suggestions-grid .suggestion-chip'), { each: 0.05 });
    }
  }, [messages.length]);

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
        text: `Error processing query: ${error.message.replace(/\.$/, '')}. Please verify the backend is running and databases are onboarded.`,
        isError: true,
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
        return <h4 key={elementKey} className="md-h3">{content.replace('### ', '')}</h4>;
      }

      // Check for bullet lists: * List
      if (content.startsWith('* ')) {
        const itemText = content.replace('* ', '');
        return (
          <li key={elementKey} className="md-li">
            {parseBoldText(itemText)}
          </li>
        );
      }

      // Default paragraph
      return <p key={elementKey} className="md-p">{parseBoldText(content)}</p>;
    });
  };

  const parseBoldText = (text) => {
    const parts = text.split(/\*\*(.*?)\*\*/g);
    return parts.map((part, index) => {
      if (index % 2 === 1) {
        return <strong key={index} className="md-bold">{part}</strong>;
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
              {dbList.length === 0 && (
                <div className="db-setup-empty">
                  <Database size={22} className="db-setup-empty-icon" />
                  <p className="db-setup-empty-title">No databases connected</p>
                  <p className="db-setup-empty-hint">
                    An administrator needs to onboard a schema before it can be queried here.
                  </p>
                </div>
              )}

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
              <ArrowRight size={14} />
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
              {dbList.length === 0 && (
                <span className="db-badge-empty">None connected</span>
              )}
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
            <h1 className="welcome-header line-reveal">
              <span><span>
                {userRole === 'admin'
                  ? (lang === 'en' ? 'Hello Chirag Admin,' : 'नमस्ते चिराग एडमिन,')
                  : t.hello
                }
              </span></span>
            </h1>
            <h2 className="welcome-subheader line-reveal">
              <span><span>{t.howCanIHelp}</span></span>
            </h2>
            
            {/* Suggested prompts list inside welcome view */}
            <div className="suggestions-heading meta-label">Suggested queries</div>
            <div className="suggestions-grid">
              {SUGGESTIONS.map((s, idx) => (
                <button
                  key={idx}
                  type="button"
                  className="suggestion-chip"
                  onClick={() => handleSend(s.text)}
                >
                  <div className="suggestion-chip-label">{s.label}</div>
                  <div className="suggestion-chip-text">{s.text}</div>
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
                  <div className="agent-message-wrapper">

                    {/* Database Routing Badge */}
                    {msg.databaseName && (
                      <div className="agent-routed-badge flex-center">
                        <Database size={12} />
                        <span>Routed to DB: {msg.databaseName}</span>
                      </div>
                    )}

                    {/* Collapsible Thoughts Trace */}
                    {msg.thoughts && msg.thoughts.length > 0 && (
                      <div className="agent-thoughts-section">
                        <button
                          type="button"
                          onClick={() => toggleThoughts(msg.id)}
                          className="agent-collapsible-toggle flex-center"
                        >
                          <span className="flex-center toggle-label"><Settings size={12} /> {t.agentReasoning}</span>
                          {showThoughts[msg.id] ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                        </button>
                        {showThoughts[msg.id] && (
                          <div className="thoughts-content-list">
                            {msg.thoughts.map((step, idx) => (
                              <div key={idx} className="thought-item">
                                <strong className="thought-step-label">{step.step}: </strong>
                                <span className="thought-step-desc">{step.desc}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Collapsible SQL Query Block */}
                    {msg.sql && (
                      <div className="agent-sql-section">
                        <button
                          type="button"
                          onClick={() => {
                            const key = `sql_${msg.id}`;
                            setShowThoughts(prev => ({ ...prev, [key]: !prev[key] }));
                          }}
                          className="agent-collapsible-toggle flex-center"
                        >
                          <span className="flex-center toggle-label"><Code size={12} /> {t.sqlQuery}</span>
                          {showThoughts[`sql_${msg.id}`] ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                        </button>
                        {showThoughts[`sql_${msg.id}`] && (
                          <div className="sql-code-block">
                            <pre>
                              <code>{msg.sql}</code>
                            </pre>
                            <button
                              type="button"
                              onClick={() => handleCopyText(msg.sql, `sql_${msg.id}`)}
                              className="copy-sql-btn"
                            >
                              {copiedMsgId === `sql_${msg.id}` ? 'Copied!' : t.copysql}
                            </button>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Natural language answer text */}
                    <div className={`agent-text-bubble${msg.isError ? ' is-error' : ''}`}>
                      {msg.isError && <AlertTriangle size={15} className="agent-error-icon" />}
                      <div className="agent-text-body">{renderMarkdown(msg.text)}</div>
                    </div>

                    {/* Interactive SQL Output Rows table */}
                    {msg.rows && msg.rows.length > 0 && (
                      <div className="agent-table-section">
                        <div className="table-header-title flex-center">
                          <FileSpreadsheet size={12} />
                          <span>{t.queryResults} ({msg.rows.length} rows)</span>
                        </div>
                        <div className="table-scroll-container">
                          <table className="results-table">
                            <thead>
                              <tr>
                                {msg.columns.map(col => (
                                  <th key={col}>{col}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {msg.rows.map((row, idx) => (
                                <tr key={idx}>
                                  {msg.columns.map(col => (
                                    <td key={col}>{String(row[col] ?? '')}</td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                        <div className="fig-caption">
                          <span>{msg.rows.length} rows &times; {msg.columns.length} columns</span>
                          <span className="fig-caption-right">Query result</span>
                        </div>
                      </div>
                    )}

                    {/* Canvas Bar Chart Visualizations */}
                    {msg.chartSpec && (
                      <div className="agent-chart-section">
                        <div className="chart-header-title flex-center">
                          <BarChart2 size={12} />
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
                <span className="loading-dots">
                  <span className="pulsing-dot-spinner"></span>
                  <span className="pulsing-dot-spinner"></span>
                  <span className="pulsing-dot-spinner"></span>
                </span>
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
            >
              <span>Disabled: My Files</span>
              <span className="badge-close-x">×</span>
            </button>
          )}
        </div>

        <div className="query-capsule-input-container">
          <div className="left-input-actions flex-center">
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
                  <span className="dropdown-label">Search</span>
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

                  <span className="dropdown-label">Database</span>
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
            className="query-capsule-input"
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
