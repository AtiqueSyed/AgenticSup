import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  Database, 
  Terminal, 
  Play, 
  CheckCircle, 
  Clock, 
  Loader2, 
  LogOut, 
  Network, 
  Server, 
  Upload, 
  BookOpen, 
  Info,
  Layers,
  Maximize2,
  Minimize2,
  AlertCircle,
  Sun,
  Moon
} from 'lucide-react';
import ReactFlow, {
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState
} from 'reactflow';
import 'reactflow/dist/style.css';

export default function ACEOnboarding({ onLogout, adminActiveTab, setAdminActiveTab, theme, toggleTheme }) {
  const [sourceType, setSourceType] = useState('structured'); // 'structured' or 'unstructured'
  
  // Structured form inputs
  const [dbName, setDbName] = useState('');
  const [connUrl, setConnUrl] = useState('');
  const [port, setPort] = useState('');
  
  // Unstructured form inputs
  const [unstructuredEngine, setUnstructuredEngine] = useState('elastic'); // 'elastic' or 'mongo'
  const [nosqlUrl, setNosqlUrl] = useState('http://localhost:9200');
  const [uploadedFile, setUploadedFile] = useState(null);
  
  const [dbDesc, setDbDesc] = useState('');

  // Pipeline execution state
  const [pipelineStatus, setPipelineStatus] = useState('idle'); // 'idle' | 'running' | 'completed' | 'failed'
  const [currentStep, setCurrentStep] = useState(0); // 0 to 4
  const [logs, setLogs] = useState([]);
  
  // ReactFlow graph states
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [isGraphFullscreen, setIsGraphFullscreen] = useState(false);
  const [currentDbId, setCurrentDbId] = useState(null); // tracks the DB being onboarded
  const [isTerminalMinimized, setIsTerminalMinimized] = useState(true); // start collapsed
  const terminalEndRef = useRef(null);
  const pollIntervalRef = useRef(null);

  // Stepper list
  const steps = [
    { 
      title: 'Establish Connection', 
      desc: 'Call connector tool using credentials', 
      tool: 'connector_tool(conn_url, port)' 
    },
    { 
      title: 'Extract Schema details', 
      desc: 'Call schema inspector tool & scan catalogs', 
      tool: 'schema_inspector_tool() -> raw_schema' 
    },
    { 
      title: 'Identify Entities & Relations', 
      desc: 'Process schema output via Descriptor Tool & register in registry', 
      tool: 'schema_descriptor_tool(raw_schema) -> metadata_registry' 
    },
    { 
      title: 'Build Knowledge Graph', 
      desc: 'Fetch metadata registry and commit ontology to Neo4j', 
      tool: 'commit_ontology_transaction(nodes, edges)' 
    }
  ];

  // Auto scroll terminal logs
  useEffect(() => {
    if (terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  // Clean up polling interval on unmount
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, []);

  // Update node and edge styles dynamically on theme change
  useEffect(() => {
    setNodes(prevNodes => prevNodes.map(node => ({
      ...node,
      style: {
        ...node.style,
        background: theme === 'light' ? 'rgba(255, 255, 255, 0.95)' : 'rgba(20, 25, 35, 0.95)',
        color: theme === 'light' ? '#0f172a' : '#ffffff',
        boxShadow: theme === 'light' ? '0 4px 12px rgba(0,0,0,0.08)' : '0 8px 16px -2px rgba(0,0,0,0.5)',
      }
    })));

    setEdges(prevEdges => prevEdges.map(edge => ({
      ...edge,
      style: {
        ...edge.style,
        stroke: theme === 'light' ? '#cbd5e1' : '#475569',
      },
      labelStyle: {
        ...edge.labelStyle,
        fill: theme === 'light' ? '#475569' : '#94a3b8',
        background: theme === 'light' ? '#f1f5f9' : '#0a0e14',
      }
    })));
  }, [theme, setNodes, setEdges]);

  const addLog = useCallback((message) => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs(prev => [...prev, `[${timestamp}] ${message}`]);
  }, []);

  // Position nodes dynamically in a nice layout
  const positionNodes = useCallback((graphNodes) => {
    return graphNodes.map((node, index) => {
      let x, y;
      if (node.type === 'input') {
        // Database nodes at the top
        x = 250 + (index * 220);
        y = 50;
      } else {
        // Entities distributed in a circle below
        const angle = (index * 2 * Math.PI) / (graphNodes.length - 1 || 1);
        x = 350 + 220 * Math.cos(angle);
        y = 250 + 130 * Math.sin(angle);
      }
      
      return {
        ...node,
        position: { x, y },
        style: {
          background: theme === 'light' ? 'rgba(255, 255, 255, 0.95)' : 'rgba(20, 25, 35, 0.95)',
          color: theme === 'light' ? '#0f172a' : '#ffffff',
          border: `2px solid ${node.type === 'input' ? '#a855f7' : '#06b6d4'}`,
          borderRadius: '8px',
          padding: '10px 14px',
          fontSize: '12px',
          fontWeight: '600',
          boxShadow: theme === 'light' ? '0 4px 12px rgba(0,0,0,0.08)' : '0 8px 16px -2px rgba(0,0,0,0.5)',
          backdropFilter: 'blur(8px)',
          minWidth: '150px',
          textAlign: 'center'
        }
      };
    });
  }, [theme]);

  const fetchGraphData = useCallback(async (dbId) => {
    try {
      // Scope graph to this specific database if an ID is provided
      const url = dbId ? `/api/v1/graph?database_id=${dbId}` : '/api/v1/graph';
      const response = await fetch(url);
      if (!response.ok) throw new Error('Failed to fetch graph data');
      const data = await response.json();
      
      const positioned = positionNodes(data.nodes);
      setNodes(positioned);
      
      const mappedEdges = data.edges.map(e => ({
        ...e,
        animated: e.type !== 'CONTAINS',
        style: { stroke: theme === 'light' ? '#cbd5e1' : '#475569', strokeWidth: 2 },
        labelStyle: { fill: theme === 'light' ? '#475569' : '#94a3b8', fontSize: 10, fontWeight: 500, background: theme === 'light' ? '#f1f5f9' : '#0a0e14', padding: '2px 4px' }
      }));
      setEdges(mappedEdges);
    } catch (err) {
      console.error(err);
      addLog(`[ERROR] Failed to load Neo4j Graph elements: ${err.message}`);
    }
  }, [positionNodes, addLog, setNodes, setEdges, theme]);

  // Handle file uploads for unstructured/CSV parsing
  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (file) {
      setUploadedFile(file);
      addLog(`Selected file schema: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`);
    }
  };

  // Run Onboarding ReAct Loop using the Real API
  const handleStartPipeline = async () => {
    if (pipelineStatus === 'running') return;
    
    setPipelineStatus('running');
    setCurrentStep(1);
    setLogs([]);

    addLog('⚡ Initializing Automatic Context Engineering (ACE) agent loop...');
    addLog(`⚙️ Mode selected: ${sourceType.toUpperCase()} database source.`);
    
    // Choose connection string
    let finalConnectionString = connUrl;
    if (sourceType === 'unstructured') {
      finalConnectionString = nosqlUrl;
    }

    addLog(`🔍 Action: invoking connector_tool for "${dbName}"...`);
    addLog(`🔗 URL string target: ${finalConnectionString}`);

    try {
      // Step 1: POST to onboard API
      const response = await fetch('/api/v1/onboard', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          connection_string: finalConnectionString,
          database_name: dbName
        })
      });

      if (!response.ok) {
        throw new Error('Onboarding initiation request rejected by endpoint.');
      }

      const initData = await response.json();
      const dbId = initData.database_id;
      setCurrentDbId(dbId); // remember which DB we're onboarding
      addLog(`✅ [SUCCESS] Socket established. Database target ID resolved: ${dbId}`);
      addLog('🛰️ Initiating background introspection workflow (LangGraph thread)...');
      
      // Step 2: Poll for status
      setCurrentStep(2);
      let stepTracker = 2;
      
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
      
      pollIntervalRef.current = setInterval(async () => {
        try {
          const statusRes = await fetch(`/api/v1/onboard/${dbId}/status`);
          if (!statusRes.ok) throw new Error('Status polling failed');
          
          const statusData = await statusRes.json();
          const currentStatus = statusData.status;
          
          if (currentStatus === 'running') {
            // Cycle logs for realistic feedback
            if (stepTracker === 2) {
              addLog('⚙️ Action: calling schema_inspector_tool(). Scanning metadata catalog...');
              stepTracker = 3;
              setCurrentStep(2);
            } else if (stepTracker === 3) {
              addLog('⚙️ Action: sending catalog to Schema Descriptor Tool. Generating semantic descriptions table-by-table...');
              stepTracker = 4;
              setCurrentStep(3);
            } else if (stepTracker === 4) {
              addLog('🤖 Agent reasoning: identifying abstract Entities and mapping relational keys in Neo4j...');
              stepTracker = 5;
              setCurrentStep(4);
            }
          } else if (currentStatus === 'completed' || currentStatus.startsWith('completed')) {
            clearInterval(pollIntervalRef.current);
            setCurrentStep(4);
            addLog('🎉 [SUCCESS] Metadata registry and Neo4j Ontology committed.');
            addLog('⚡ Generating FastEmbed small vector embeddings for entities and pushing to Elasticsearch...');
            addLog('✅ [SUCCESS] Knowledge Graph and Vector store synchronized successfully.');
            setPipelineStatus('completed');
            fetchGraphData(dbId); // pass dbId to scope graph to this DB only
          } else if (currentStatus.startsWith('failed')) {
            clearInterval(pollIntervalRef.current);
            addLog(`❌ [ERROR] Onboarding failed: ${currentStatus}`);
            setPipelineStatus('failed');
          }
        } catch (pollErr) {
          clearInterval(pollIntervalRef.current);
          addLog(`❌ [ERROR] Polling endpoint error: ${pollErr.message}`);
          setPipelineStatus('failed');
        }
      }, 2000);

    } catch (err) {
      addLog(`❌ [ERROR] Failed to start pipeline: ${err.message}`);
      setPipelineStatus('failed');
    }
  };

  return (
    <div className={`ace-onboarding-wrapper ${theme}-theme`}>
      {/* Platform Navigation Header */}
      <header className="ace-dashboard-header flex-center">
        <div className="header-logo-section flex-center">
          <div className="header-logo-icon flex-center">
            <Layers size={18} />
          </div>
          <div>
            <h1 className="header-title">ACE Onboarding</h1>
            <p className="header-subtitle">Automatic Context Engineering Agent</p>
          </div>
        </div>

        <nav className="header-tab-nav flex-center">
          <button 
            type="button" 
            className="nav-tab-item active flex-center"
          >
            <Server size={14} className="tab-icon" />
            <span>Admin • ACE Onboarding</span>
          </button>
          
          <button 
            type="button" 
            className="nav-tab-item flex-center"
            onClick={() => setAdminActiveTab('registry')}
          >
            <Database size={14} className="tab-icon" />
            <span>Admin • Metadata Registry</span>
          </button>

          <button 
            type="button" 
            className="nav-tab-item flex-center"
            onClick={() => setAdminActiveTab('query')}
          >
            <BookOpen size={14} className="tab-icon" />
            <span>User • Query Execution</span>
          </button>
        </nav>

        <div className="header-profile-section flex-center">
          <div className="profile-badge flex-center">
            <div className="profile-avatar flex-center">C</div>
            <span className="profile-name">Chirag Admin</span>
          </div>
          <button 
            type="button" 
            className="logout-button flex-center theme-toggle-btn-admin" 
            onClick={toggleTheme}
            title={theme === 'dark' ? "Switch to Light Mode" : "Switch to Dark Mode"}
            style={{
              background: 'transparent',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              padding: '6px',
              borderRadius: '6px',
              color: '#94a3b8',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'all 0.15s ease',
              width: '32px',
              height: '32px',
              marginRight: '8px'
            }}
          >
            {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
          </button>
          <button 
            type="button" 
            className="logout-button flex-center" 
            onClick={onLogout}
            title="Logout from platform"
          >
            <LogOut size={16} />
            <span>Logout</span>
          </button>
        </div>
      </header>

      {/* Main Workspace Layout */}
      <main className="ace-dashboard-body">
        {/* Left Column: Data Source Configuration Form */}
        <section className="ace-panel-card config-panel-card">
          <div className="panel-header flex-center">
            <span className="panel-step-badge">01</span>
            <h2 className="panel-title">Source Configuration</h2>
          </div>

          <div className="panel-content">
            {/* Database Name */}
            <div className="form-field-group">
              <label className="field-label-tag">Database Identifier</label>
              <input 
                type="text"
                className="config-text-input"
                value={dbName}
                onChange={(e) => setDbName(e.target.value)}
                placeholder="e.g. CIMS"
                disabled={pipelineStatus === 'running'}
              />
            </div>

            {/* Source Type Selector Tabs */}
            <div className="form-field-group">
              <label className="field-label-tag">Database Paradigm</label>
              <div className="paradigm-selector-tabs flex-center">
                <button
                  type="button"
                  className={`paradigm-tab flex-center ${sourceType === 'structured' ? 'active' : ''}`}
                  onClick={() => setSourceType('structured')}
                  disabled={pipelineStatus === 'running'}
                >
                  <Database size={14} className="tab-icon" />
                  <span>Structured (SQL)</span>
                </button>
                <button
                  type="button"
                  className={`paradigm-tab flex-center ${sourceType === 'unstructured' ? 'active' : ''}`}
                  onClick={() => setSourceType('unstructured')}
                  disabled={pipelineStatus === 'running'}
                >
                  <Network size={14} className="tab-icon" />
                  <span>Unstructured (NoSQL)</span>
                </button>
              </div>
            </div>

            {/* Conditional Form Inputs */}
            {sourceType === 'structured' ? (
              <div className="conditional-inputs-block animate-fade-in">
                <div className="form-field-group">
                  <label className="field-label-tag">Connection Host URL</label>
                  <input 
                    type="text"
                    className="config-text-input"
                    value={connUrl}
                    onChange={(e) => setConnUrl(e.target.value)}
                    placeholder="oracle+oracledb_async://user:pass@host:port/?service_name=XE"
                    disabled={pipelineStatus === 'running'}
                  />
                </div>
                <div className="form-field-group">
                  <label className="field-label-tag">Port</label>
                  <input 
                    type="number"
                    className="config-text-input"
                    value={port}
                    onChange={(e) => setPort(e.target.value)}
                    placeholder="1522"
                    disabled={pipelineStatus === 'running'}
                  />
                </div>
              </div>
            ) : (
              <div className="conditional-inputs-block animate-fade-in">
                <div className="form-field-group">
                  <label className="field-label-tag">Connect to No-SQL DB</label>
                  <div className="nosql-engine-toggle flex-center">
                    <button 
                      type="button" 
                      className={`engine-toggle-btn ${unstructuredEngine === 'elastic' ? 'active' : ''}`}
                      onClick={() => {
                        setUnstructuredEngine('elastic');
                        setNosqlUrl('http://localhost:9200');
                      }}
                      disabled={pipelineStatus === 'running'}
                    >
                      Elasticsearch
                    </button>
                    <button 
                      type="button" 
                      className={`engine-toggle-btn ${unstructuredEngine === 'mongo' ? 'active' : ''}`}
                      onClick={() => {
                        setUnstructuredEngine('mongo');
                        setNosqlUrl('mongodb://localhost:27017');
                      }}
                      disabled={pipelineStatus === 'running'}
                    >
                      MongoDB
                    </button>
                  </div>
                  <input 
                    type="text"
                    className="config-text-input mt-2"
                    value={nosqlUrl}
                    onChange={(e) => setNosqlUrl(e.target.value)}
                    placeholder="mongodb://localhost:27017"
                    disabled={pipelineStatus === 'running'}
                  />
                </div>

                <div className="form-field-group">
                  <label className="field-label-tag">Or Upload Schema File</label>
                  <div className="upload-dropzone flex-center" onClick={() => document.getElementById('admin-schema-file')?.click()}>
                    <Upload size={20} className="upload-drop-icon" />
                    <span className="upload-drop-title">
                      {uploadedFile ? uploadedFile.name : 'Select JSON/CSV DB Schema'}
                    </span>
                    <span className="upload-drop-subtitle">
                      {uploadedFile ? `${(uploadedFile.size / 1024).toFixed(1)} KB` : 'Drag and drop or click to upload'}
                    </span>
                    <input 
                      type="file" 
                      id="admin-schema-file" 
                      style={{ display: 'none' }} 
                      onChange={handleFileUpload}
                      disabled={pipelineStatus === 'running'}
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Human Level Context Description */}
            <div className="form-field-group">
              <div className="field-label-wrapper flex-center">
                <label className="field-label-tag">Human-Level Database Description</label>
                <div className="tooltip-info-icon" title="Helps the ACE agent understand the business context of your schema.">
                  <Info size={12} />
                </div>
              </div>
              <textarea
                className="config-textarea-input"
                rows={3}
                value={dbDesc}
                onChange={(e) => setDbDesc(e.target.value)}
                placeholder="Explain the business value and entity contents of this database..."
                disabled={pipelineStatus === 'running'}
              />
            </div>

            {/* Action Trigger Button */}
            <button
              type="button"
              className={`start-pipeline-btn flex-center ${pipelineStatus === 'running' ? 'running' : ''}`}
              onClick={handleStartPipeline}
              disabled={pipelineStatus === 'running'}
            >
              {pipelineStatus === 'running' ? (
                <>
                  <Loader2 size={16} className="spinner-icon animate-spin" />
                  <span>Executing ReAct Onboarding...</span>
                </>
              ) : (
                <>
                  <Play size={16} className="play-icon" />
                  <span>Run Onboarding Sequence</span>
                </>
              )}
            </button>
          </div>
        </section>

        {/* Right Columns: Stepper Loop & Knowledge Graph */}
        <div className="ace-right-column flex-column">
          {/* Top Panel: Agent Actions Loop Progress */}
          <section className="ace-panel-card progress-panel-card">
            <div className="panel-header flex-center">
              <span className="panel-step-badge">02</span>
              <h2 className="panel-title">ACE Onboarding Agent - ReAct Loop</h2>
              {pipelineStatus === 'completed' && (
                <div className="completion-badge flex-center">
                  <CheckCircle size={12} />
                  <span>Committed to Neo4j</span>
                </div>
              )}
            </div>

            <div className="panel-content steps-grid">
              {steps.map((step, idx) => {
                const stepNum = idx + 1;
                const isSuccess = currentStep > stepNum || pipelineStatus === 'completed';
                const isCurrent = currentStep === stepNum && pipelineStatus === 'running';
                
                return (
                  <div key={idx} className={`step-timeline-item ${isSuccess ? 'success' : ''} ${isCurrent ? 'current' : ''}`}>
                    <div className="step-status-icon flex-center">
                      {isSuccess ? (
                        <CheckCircle size={16} className="check-icon" />
                      ) : isCurrent ? (
                        <Loader2 size={16} className="loader-icon animate-spin" />
                      ) : (
                        <Clock size={16} className="pending-icon" />
                      )}
                    </div>
                    <div className="step-info">
                      <div className="step-header flex-center">
                        <span className="step-title-name">{step.title}</span>
                        {isCurrent && <span className="running-badge">running</span>}
                      </div>
                      <p className="step-desc-text">{step.desc}</p>
                      <div className="step-tool-badge flex-center">
                        <Terminal size={10} className="badge-terminal-icon" />
                        <code>{step.tool}</code>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          {/* Bottom Panel: Knowledge Graph Visualization */}
          <section className="ace-panel-card graph-panel-card">
            <div className="panel-header flex-center">
              <span className="panel-step-badge">03</span>
              <h2 className="panel-title">Visualize Knowledge Graph</h2>
              {(pipelineStatus === 'completed' || nodes.length > 0) && (
                <button
                  type="button"
                  className="graph-expand-btn flex-center"
                  onClick={() => setIsGraphFullscreen(true)}
                  title="Expand Graph to Fullscreen"
                  style={{ 
                    marginLeft: 'auto', 
                    background: theme === 'light' ? '#ffffff' : 'rgba(255,255,255,0.03)', 
                    border: theme === 'light' ? '1px solid #cbd5e1' : '1px solid rgba(255,255,255,0.08)', 
                    color: theme === 'light' ? '#475569' : '#94a3b8', 
                    cursor: 'pointer',
                    padding: '4px 8px',
                    borderRadius: '4px',
                    fontSize: '11px',
                    gap: '4px'
                  }}
                >
                  <Maximize2 size={12} />
                  <span>Fullscreen</span>
                </button>
              )}
            </div>

            <div className="panel-content graph-workspace flex-center">
              {pipelineStatus !== 'completed' && nodes.length === 0 ? (
                <div className="graph-idle-state flex-center">
                  <Network size={40} className="idle-network-icon animate-pulse" />
                  <span className="idle-text-title">Graph Visualizer Idle</span>
                  <span className="idle-text-subtitle">
                    Run the onboarding sequence to fetch metadata registry and build ontology graph
                  </span>
                </div>
              ) : pipelineStatus === 'running' && nodes.length === 0 ? (
                <div className="graph-idle-state flex-center">
                  <Loader2 size={40} className="graph-loader-icon animate-spin" />
                  <span className="idle-text-title">Scanning Schema Metadata...</span>
                  <span className="idle-text-subtitle">
                    The agent is building the ontology registry. ReactFlow nodes loading soon.
                  </span>
                </div>
              ) : (
                <div className="interactive-graph-container animate-fade-in" style={{ width: '100%', height: '100%', minHeight: '380px' }}>
                  {/* ReactFlow Knowledge Graph Explorer */}
                  <ReactFlow
                    nodes={nodes}
                    edges={edges}
                    onNodesChange={onNodesChange}
                    onEdgesChange={onEdgesChange}
                    fitView
                  >
                    <Controls style={{
                      background: theme === 'light' ? '#ffffff' : 'rgba(14,18,26,0.9)',
                      border: theme === 'light' ? '1px solid #cbd5e1' : '1px solid rgba(255,255,255,0.08)',
                      borderRadius: '8px',
                      color: theme === 'light' ? '#0f172a' : '#ffffff',
                    }} />
                    <MiniMap 
                      nodeColor={(node) => node.type === 'input' ? '#a855f7' : '#06b6d4'} 
                      style={{
                        background: theme === 'light' ? '#ffffff' : 'rgba(10,14,20,0.95)',
                        border: theme === 'light' ? '1px solid #cbd5e1' : '1px solid rgba(255,255,255,0.06)',
                        borderRadius: '8px',
                      }}
                    />
                    <Background gap={12} size={1} color={theme === 'light' ? 'rgba(0,0,0,0.06)' : "rgba(255, 255, 255, 0.05)"} />
                  </ReactFlow>
                </div>
              )}
            </div>
          </section>
        </div>
      </main>

      {/* Execution Trace Terminal Console (Full Width at Bottom) */}
      <footer className={`ace-terminal-footer ${isTerminalMinimized ? 'terminal-minimized' : ''}`}>
        <div
          className="terminal-header flex-center"
          onClick={() => setIsTerminalMinimized(prev => !prev)}
          style={{ cursor: 'pointer', userSelect: 'none' }}
          title={isTerminalMinimized ? 'Expand terminal' : 'Minimize terminal'}
        >
          <div className="terminal-actions flex-center">
            <span className="dot dot-red"></span>
            <span className="dot dot-yellow"></span>
            <span className="dot dot-green"></span>
          </div>
          <span className="terminal-title flex-center">
            <Terminal size={12} className="title-icon" />
            <span>ace-agent-executor:~ - Bash Shell (ReAct loop logs)</span>
          </span>
          <div className="terminal-header-right flex-center" style={{ marginLeft: 'auto', gap: '10px' }}>
            <div className="terminal-status-light flex-center">
              <span className={`status-dot ${pipelineStatus}`}></span>
              <span className="status-label">{pipelineStatus.toUpperCase()}</span>
            </div>
            <button
              type="button"
              className="terminal-toggle-btn flex-center"
              onClick={(e) => { e.stopPropagation(); setIsTerminalMinimized(prev => !prev); }}
              title={isTerminalMinimized ? 'Maximize terminal' : 'Minimize terminal'}
              style={{
                background: theme === 'light' ? '#ffffff' : 'rgba(255,255,255,0.04)',
                border: theme === 'light' ? '1px solid #cbd5e1' : '1px solid rgba(255,255,255,0.08)',
                borderRadius: '4px',
                color: theme === 'light' ? '#475569' : '#94a3b8',
                cursor: 'pointer',
                padding: '3px 7px',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                fontSize: '11px',
                transition: 'background 0.15s'
              }}
            >
              {isTerminalMinimized
                ? <><Maximize2 size={11} /><span>Expand</span></>
                : <><Minimize2 size={11} /><span>Minimize</span></>}
            </button>
          </div>
        </div>

        {!isTerminalMinimized && (
          <div className="terminal-body scrollbar-custom">
            {logs.length === 0 ? (
              <div className="terminal-empty flex-center">
                <span className="empty-text">Terminal idle. Click "Run Onboarding Sequence" to view agent execution traces...</span>
              </div>
            ) : (
              <div className="terminal-logs-wrapper">
                {logs.map((log, index) => {
                  let logClass = '';
                  if (log.includes('[SUCCESS]')) logClass = 'success-log';
                  else if (log.includes('🔍 Action:')) logClass = 'action-log';
                  else if (log.includes('⚙️ Mode')) logClass = 'mode-log';
                  else if (log.includes('📌 Entity')) logClass = 'entity-log';
                  else if (log.includes('[ERROR]')) logClass = 'text-danger';
                  
                  return (
                    <div key={index} className={`terminal-log-line ${logClass}`}>
                      {log}
                    </div>
                  );
                })}
                <div ref={terminalEndRef} />
              </div>
            )}
          </div>
        )}
      </footer>

      {/* Fullscreen Graph Overlay Modal */}
      {isGraphFullscreen && (
        <div className="graph-fullscreen-overlay animate-fade-in">
          <div className="fullscreen-overlay-header flex-center">
            <div className="flex-center" style={{ gap: '10px' }}>
              <Network size={20} style={{ color: '#06b6d4' }} />
              <h2 className="overlay-title">Interactive Knowledge Graph Workspace</h2>
            </div>
            <button
              type="button"
              className="close-overlay-btn flex-center"
              onClick={() => setIsGraphFullscreen(false)}
              title="Close Fullscreen"
            >
              <Minimize2 size={16} />
              <span>Exit Fullscreen</span>
            </button>
          </div>

          <div className="fullscreen-overlay-body" style={{ background: theme === 'light' ? '#f1f5f9' : '#0a0e14', position: 'relative' }}>
            <div className="interactive-graph-container" style={{ width: '100%', height: '100%' }}>
              <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                fitView
              >
                <Controls style={{
                  background: theme === 'light' ? '#ffffff' : 'rgba(14,18,26,0.9)',
                  border: theme === 'light' ? '1px solid #cbd5e1' : '1px solid rgba(255,255,255,0.08)',
                  borderRadius: '8px',
                  color: theme === 'light' ? '#0f172a' : '#ffffff',
                }} />
                <MiniMap 
                  nodeColor={(node) => node.type === 'input' ? '#a855f7' : '#06b6d4'} 
                  style={{
                    background: theme === 'light' ? '#ffffff' : 'rgba(10,14,20,0.95)',
                    border: theme === 'light' ? '1px solid #cbd5e1' : '1px solid rgba(255,255,255,0.06)',
                    borderRadius: '8px',
                  }}
                />
                <Background gap={12} size={1} color={theme === 'light' ? 'rgba(0,0,0,0.06)' : "rgba(255, 255, 255, 0.05)"} />
              </ReactFlow>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
