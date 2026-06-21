import React, { useState, useEffect, useCallback, useRef } from 'react';
import ReactFlow, {
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
} from 'reactflow';
import 'reactflow/dist/style.css';
import {
  Database,
  Activity,
  Trash2,
  CheckCircle,
  XCircle,
  Loader2,
  LogOut,
  Layers,
  BookOpen,
  Server,
  RefreshCw,
  AlertTriangle,
  GitBranch,
  Eye,
  EyeOff,
} from 'lucide-react';

/* ─────────────────────────────────────────────────────────
   Custom dark-themed ReactFlow node styles injected once
───────────────────────────────────────────────────────── */
const RF_NODE_STYLES = {
  Database: {
    background: 'linear-gradient(135deg, rgba(168,85,247,0.25), rgba(109,40,217,0.15))',
    border: '1px solid rgba(168,85,247,0.5)',
    borderRadius: '10px',
    color: '#e9d5ff',
    fontSize: '11px',
    fontWeight: '700',
    padding: '8px 14px',
    backdropFilter: 'blur(8px)',
    textAlign: 'center',
    minWidth: '90px',
  },
  Entity: {
    background: 'linear-gradient(135deg, rgba(6,182,212,0.12), rgba(8,145,178,0.08))',
    border: '1px solid rgba(6,182,212,0.3)',
    borderRadius: '8px',
    color: '#a5f3fc',
    fontSize: '10px',
    fontWeight: '500',
    padding: '6px 10px',
    backdropFilter: 'blur(8px)',
    textAlign: 'center',
    minWidth: '72px',
  },
  Table: {
    background: 'linear-gradient(135deg, rgba(234,179,8,0.12), rgba(202,138,4,0.08))',
    border: '1px solid rgba(234,179,8,0.3)',
    borderRadius: '8px',
    color: '#fef08a',
    fontSize: '10px',
    fontWeight: '500',
    padding: '6px 10px',
    backdropFilter: 'blur(8px)',
    textAlign: 'center',
    minWidth: '72px',
  },
  Column: {
    background: 'linear-gradient(135deg, rgba(244,63,94,0.12), rgba(225,29,72,0.08))',
    border: '1px solid rgba(244,63,94,0.3)',
    borderRadius: '8px',
    color: '#fecdd3',
    fontSize: '10px',
    fontWeight: '500',
    padding: '6px 10px',
    backdropFilter: 'blur(8px)',
    textAlign: 'center',
    minWidth: '72px',
  },
};

/* ─────────────────────────────────────────────────────────
   Knowledge Graph Panel
   ───────────────────────────────────────────────────────── */
function KnowledgeGraphPanel({ refreshKey }) {
  const [rawGraphData, setRawGraphData] = useState({ nodes: [], edges: [] });
  const [graphLoading, setGraphLoading] = useState(true);
  const [showDatabases, setShowDatabases] = useState(true);
  const [showTables, setShowTables] = useState(false);
  const [showColumns, setShowColumns] = useState(false);
  const [nodeCount, setNodeCount] = useState(0);
  const [edgeCount, setEdgeCount] = useState(0);

  const [nodes, setNodes, onNodesChangeCore] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const savedPositions = useRef(new Map());
  const draggedNodes = useRef(new Set());

  const onNodesChange = useCallback((changes) => {
    onNodesChangeCore(changes);
    changes.forEach((c) => {
      if (c.type === 'position' && c.position) {
        if (c.dragging || draggedNodes.current.has(c.id)) {
          savedPositions.current.set(c.id, c.position);
          draggedNodes.current.add(c.id);
        }
      }
    });
  }, [onNodesChangeCore]);

  const fetchGraph = async () => {
    setGraphLoading(true);
    try {
      const response = await fetch('/api/v1/graph');
      const data = await response.json();
      savedPositions.current.clear();
      draggedNodes.current.clear();
      setRawGraphData(data);
    } catch (err) {
      console.error('Failed to fetch graph:', err);
    } finally {
      setGraphLoading(false);
    }
  };

  useEffect(() => {
    fetchGraph();
  }, [refreshKey]);

  useEffect(() => {
    let filteredNodes = rawGraphData.nodes;
    let filteredEdges = rawGraphData.edges;

    const excludedTypes = new Set();
    if (!showDatabases) excludedTypes.add('Database');
    if (!showTables) excludedTypes.add('Table');
    if (!showColumns) excludedTypes.add('Column');

    if (excludedTypes.size > 0) {
      const hiddenNodeIds = new Set();
      filteredNodes = rawGraphData.nodes.filter((n) => {
        const labelText = n.data?.label || '';
        let nodeType = 'Entity';
        if (labelText.startsWith('[Database]') || n.type === 'input') {
          nodeType = 'Database';
        } else if (labelText.startsWith('[Table]')) {
          nodeType = 'Table';
        } else if (labelText.startsWith('[Column]')) {
          nodeType = 'Column';
        }

        const isHidden = excludedTypes.has(nodeType);
        if (isHidden) {
          hiddenNodeIds.add(n.id);
        }
        return !isHidden;
      });

      filteredEdges = rawGraphData.edges.filter(
        (e) => !hiddenNodeIds.has(e.source) && !hiddenNodeIds.has(e.target)
      );
    }

    setNodeCount(filteredNodes.length);
    setEdgeCount(filteredEdges.length);

    setNodes((currentNodes) => {
      currentNodes.forEach((n) => savedPositions.current.set(n.id, n.position));
      
      const dbNodes = filteredNodes.filter(n => n.type === 'input' || n.data?.label?.startsWith('[Database]'));
      const entityNodes = filteredNodes.filter(n => n.data?.label?.startsWith('[Entity]') || (!n.data?.label?.startsWith('[Database]') && !n.data?.label?.startsWith('[Table]') && !n.data?.label?.startsWith('[Column]') && n.type !== 'input'));
      const tableNodes = filteredNodes.filter(n => n.data?.label?.startsWith('[Table]'));
      const columnNodes = filteredNodes.filter(n => n.data?.label?.startsWith('[Column]'));

      const entityColumns = 6;
      const entityRows = Math.ceil(entityNodes.length / entityColumns) || 1;
      
      const tableColumns = 5;
      const tableRows = Math.ceil(tableNodes.length / tableColumns) || 1;

      const dbStartY = 40;
      const entityStartY = 200;
      const tableStartY = entityStartY + entityRows * 130;
      const columnStartY = tableStartY + (showTables ? tableRows * 130 : 0);

      let dbCount = 0;
      let entityCount = 0;
      let tableCount = 0;
      let columnCount = 0;

      return filteredNodes.map((node) => {
        const labelText = node.data?.label || '';
        let style = RF_NODE_STYLES.Entity;
        let isDb = false;
        let x = 0;
        let y = 160;

        if (labelText.startsWith('[Database]') || node.type === 'input') {
          style = RF_NODE_STYLES.Database;
          isDb = true;
          x = 300 + (dbCount % 3) * 320;
          y = dbStartY;
          dbCount++;
        } else if (labelText.startsWith('[Table]')) {
          style = RF_NODE_STYLES.Table;
          x = (tableCount % tableColumns) * 240;
          y = tableStartY + Math.floor(tableCount / tableColumns) * 130;
          tableCount++;
        } else if (labelText.startsWith('[Column]')) {
          style = RF_NODE_STYLES.Column;
          x = (columnCount % 6) * 180;
          y = columnStartY + Math.floor(columnCount / 6) * 130;
          columnCount++;
        } else {
          style = RF_NODE_STYLES.Entity;
          x = (entityCount % entityColumns) * 220;
          y = entityStartY + Math.floor(entityCount / entityColumns) * 130;
          entityCount++;
        }

        return {
          ...node,
          style,
          position: savedPositions.current.get(node.id) || { x, y },
        };
      });
    });

    setEdges(
      filteredEdges.map((e) => ({
        ...e,
        style: {
          stroke: e.animated ? 'rgba(6,182,212,0.5)' : 'rgba(168,85,247,0.3)',
          strokeWidth: 1.5,
        },
        labelStyle: { fill: '#94a3b8', fontSize: 9 },
        labelBgStyle: {
          fill: 'rgba(10,14,20,0.85)',
          fillOpacity: 0.9,
        },
        markerEnd: { type: 'arrowclosed', color: e.animated ? '#06b6d4' : '#a855f7' },
      }))
    );
  }, [rawGraphData, showDatabases, showTables, showColumns, setNodes, setEdges]);

  const onConnect = useCallback(
    (params) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 0 }}>
      {/* Graph Panel Header */}
      <div style={{
        padding: '14px 18px',
        borderBottom: '1px solid rgba(255,255,255,0.05)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: 'rgba(0,0,0,0.2)',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span className="panel-step-badge">KG</span>
          <div>
            <h2 className="panel-title" style={{ margin: 0, fontSize: '14px' }}>Knowledge Graph</h2>
            <p style={{ margin: '2px 0 0', fontSize: '11px', color: '#64748b' }}>
              {nodeCount} nodes · {edgeCount} edges — sourced from Neo4j
            </p>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {/* Toggle DB Nodes */}
          <button
            type="button"
            onClick={() => setShowDatabases(!showDatabases)}
            title={showDatabases ? 'Hide DB nodes' : 'Show DB nodes'}
            style={{
              background: showDatabases ? 'rgba(168,85,247,0.15)' : 'rgba(255,255,255,0.03)',
              border: `1px solid ${showDatabases ? 'rgba(168,85,247,0.4)' : 'rgba(255,255,255,0.08)'}`,
              color: showDatabases ? '#a855f7' : '#64748b',
              padding: '5px 10px',
              borderRadius: '6px',
              fontSize: '11px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
            }}
          >
            {showDatabases ? <Eye size={12} /> : <EyeOff size={12} />}
            <span>DB Lineage</span>
          </button>
          
          {/* Toggle Table Nodes */}
          <button
            type="button"
            onClick={() => setShowTables(!showTables)}
            title={showTables ? 'Hide Table nodes' : 'Show Table nodes'}
            style={{
              background: showTables ? 'rgba(234,179,8,0.15)' : 'rgba(255,255,255,0.03)',
              border: `1px solid ${showTables ? 'rgba(234,179,8,0.4)' : 'rgba(255,255,255,0.08)'}`,
              color: showTables ? '#eab308' : '#64748b',
              padding: '5px 10px',
              borderRadius: '6px',
              fontSize: '11px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
            }}
          >
            {showTables ? <Eye size={12} /> : <EyeOff size={12} />}
            <span>Tables</span>
          </button>

          {/* Toggle Column Nodes */}
          <button
            type="button"
            onClick={() => setShowColumns(!showColumns)}
            title={showColumns ? 'Hide Column nodes' : 'Show Column nodes'}
            style={{
              background: showColumns ? 'rgba(244,63,94,0.15)' : 'rgba(255,255,255,0.03)',
              border: `1px solid ${showColumns ? 'rgba(244,63,94,0.4)' : 'rgba(255,255,255,0.08)'}`,
              color: showColumns ? '#f43f5e' : '#64748b',
              padding: '5px 10px',
              borderRadius: '6px',
              fontSize: '11px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
            }}
          >
            {showColumns ? <Eye size={12} /> : <EyeOff size={12} />}
            <span>Columns</span>
          </button>

          {/* Refresh Graph */}
          <button
            type="button"
            onClick={fetchGraph}
            disabled={graphLoading}
            style={{
              background: 'rgba(255,255,255,0.03)',
              border: '1px solid rgba(255,255,255,0.08)',
              color: '#94a3b8',
              padding: '5px 10px',
              borderRadius: '6px',
              fontSize: '11px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
            }}
          >
            <RefreshCw size={11} className={graphLoading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* ReactFlow Canvas */}
      <div style={{ flex: 1, position: 'relative', background: 'rgba(6,9,13,0.8)' }}>
        {graphLoading ? (
          <div style={{
            position: 'absolute', inset: 0,
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            gap: '12px', color: '#64748b',
          }}>
            <Loader2 size={28} className="animate-spin" style={{ color: '#a855f7' }} />
            <span style={{ fontSize: '12px' }}>Loading knowledge graph from Neo4j...</span>
          </div>
        ) : nodes.length === 0 ? (
          <div style={{
            position: 'absolute', inset: 0,
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            gap: '12px', color: '#64748b',
          }}>
            <GitBranch size={40} style={{ color: '#334155', opacity: 0.6 }} />
            <h3 style={{ margin: 0, color: '#94a3b8', fontSize: '14px' }}>No Graph Data</h3>
            <p style={{ margin: 0, fontSize: '12px', textAlign: 'center', maxWidth: '220px' }}>
              Onboard a database first to populate the knowledge graph.
            </p>
          </div>
        ) : (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            proOptions={{ hideAttribution: true }}
          >
            <Controls
              style={{
                background: 'rgba(14,18,26,0.9)',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: '8px',
              }}
            />
            <MiniMap
              style={{
                background: 'rgba(10,14,20,0.95)',
                border: '1px solid rgba(255,255,255,0.06)',
                borderRadius: '8px',
              }}
              nodeColor={(n) => {
                const labelText = n.data?.label || '';
                if (labelText.startsWith('[Database]') || n.type === 'input') return '#a855f7';
                if (labelText.startsWith('[Table]')) return '#eab308';
                if (labelText.startsWith('[Column]')) return '#f43f5e';
                return '#06b6d4';
              }}
              maskColor="rgba(0,0,0,0.6)"
            />
            <Background
              color="rgba(255,255,255,0.03)"
              gap={20}
              size={1}
            />
          </ReactFlow>
        )}
      </div>

      {/* Legend */}
      <div style={{
        padding: '8px 16px',
        borderTop: '1px solid rgba(255,255,255,0.04)',
        display: 'flex',
        flexWrap: 'wrap',
        gap: '16px',
        background: 'rgba(0,0,0,0.15)',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '10px', color: '#64748b' }}>
          <span style={{ width: '10px', height: '10px', borderRadius: '3px', background: 'rgba(168,85,247,0.5)', border: '1px solid #a855f7', display: 'inline-block' }} />
          Database
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '10px', color: '#64748b' }}>
          <span style={{ width: '10px', height: '10px', borderRadius: '3px', background: 'rgba(234,179,8,0.3)', border: '1px solid #eab308', display: 'inline-block' }} />
          Table
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '10px', color: '#64748b' }}>
          <span style={{ width: '10px', height: '10px', borderRadius: '3px', background: 'rgba(244,63,94,0.3)', border: '1px solid #f43f5e', display: 'inline-block' }} />
          Column
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '10px', color: '#64748b' }}>
          <span style={{ width: '10px', height: '10px', borderRadius: '3px', background: 'rgba(6,182,212,0.3)', border: '1px solid #06b6d4', display: 'inline-block' }} />
          Abstract Entity
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '10px', color: '#64748b' }}>
          <span style={{ width: '18px', height: '2px', background: 'rgba(168,85,247,0.5)', display: 'inline-block', borderRadius: '1px' }} />
          CONTAINS
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '10px', color: '#64748b' }}>
          <span style={{ width: '18px', height: '2px', background: 'rgba(6,182,212,0.5)', display: 'inline-block', borderRadius: '1px', borderBottom: '2px dashed rgba(6,182,212,0.5)' }} />
          RELATED_TO
        </div>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────
   Main MetadataRegistry Component
───────────────────────────────────────────────────────── */
export default function MetadataRegistry({ onLogout, adminActiveTab, setAdminActiveTab }) {
  const [stats, setStats] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [deletingId, setDeletingId] = useState(null);
  const [clearingGraph, setClearingGraph] = useState(false);
  const [graphRefreshKey, setGraphRefreshKey] = useState(0);
  const [deleteToast, setDeleteToast] = useState(null);

  const [leftWidth, setLeftWidth] = useState(550);
  const [isDragging, setIsDragging] = useState(false);
  const containerRef = useRef(null);

  const handleMouseDown = useCallback((e) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e) => {
      if (containerRef.current) {
        const containerRect = containerRef.current.getBoundingClientRect();
        const newWidth = e.clientX - containerRect.left;
        const minWidth = 250;
        const maxWidth = containerRect.width - 250;
        setLeftWidth(Math.max(minWidth, Math.min(newWidth, maxWidth)));
      }
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging]);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    setIsLoading(true);
    try {
      const response = await fetch('/api/v1/stats');
      if (!response.ok) throw new Error('Failed to fetch stats');
      const data = await response.json();
      setStats(data);
    } catch (error) {
      console.error('Failed to fetch registry stats:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async (id, name) => {
    if (!window.confirm(`Delete "${name}" schema? This removes its nodes from Neo4j and embeddings from Elasticsearch.`)) {
      return;
    }
    setDeletingId(id);
    try {
      const response = await fetch(`/api/v1/onboard/${id}`, { method: 'DELETE' });
      if (!response.ok) {
        const errText = await response.text();
        throw new Error(errText || 'Delete request failed');
      }
      // Refresh both the stats table and the knowledge graph
      await fetchStats();
      setGraphRefreshKey(k => k + 1);
      setDeleteToast(`"${name}" removed successfully.`);
      setTimeout(() => setDeleteToast(null), 3500);
    } catch (error) {
      console.error('Failed to delete database:', error);
      alert(`Delete failed: ${error.message}`);
    } finally {
      setDeletingId(null);
    }
  };

  const handleClearAll = async () => {
    if (!window.confirm('WARNING: Clear ALL database schemas from Neo4j, Elasticsearch, and the registry? This is irreversible.')) {
      return;
    }
    setClearingGraph(true);
    try {
      const response = await fetch('/api/v1/graph/clear', { method: 'DELETE' });
      if (!response.ok) {
        const errText = await response.text();
        throw new Error(errText || 'Clear request failed');
      }
      await fetchStats();
      setGraphRefreshKey(k => k + 1);
      setDeleteToast('All schemas cleared from graph.');
      setTimeout(() => setDeleteToast(null), 3500);
    } catch (error) {
      console.error('Failed to clear graph:', error);
      alert(`Clear failed: ${error.message}`);
    } finally {
      setClearingGraph(false);
    }
  };

  return (
    <div className="ace-onboarding-wrapper" style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>

      {/* ── Delete success toast ── */}
      {deleteToast && (
        <div style={{
          position: 'fixed', bottom: '24px', right: '24px', zIndex: 9999,
          background: 'rgba(16,185,129,0.15)', border: '1px solid rgba(16,185,129,0.35)',
          color: '#10b981', padding: '10px 18px', borderRadius: '8px', fontSize: '13px',
          fontWeight: '500', backdropFilter: 'blur(8px)', boxShadow: '0 4px 24px rgba(0,0,0,0.4)',
          display: 'flex', alignItems: 'center', gap: '8px',
        }}>
          <CheckCircle size={14} />
          {deleteToast}
        </div>
      )}

      {/* ── Shared Admin Header ── */}
      <header className="ace-dashboard-header flex-center" style={{ flexShrink: 0 }}>
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
            className="nav-tab-item flex-center"
            onClick={() => setAdminActiveTab('onboarding')}
          >
            <Server size={14} className="tab-icon" />
            <span>Admin • ACE Onboarding</span>
          </button>

          <button
            type="button"
            className="nav-tab-item active flex-center"
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
            className="logout-button flex-center"
            onClick={onLogout}
          >
            <LogOut size={16} />
            <span>Logout</span>
          </button>
        </div>
      </header>

      {/* ── Stats Widgets ── */}
      <div style={{
        flexShrink: 0,
        display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)',
        gap: '16px',
        padding: '16px 20px',
        borderBottom: '1px solid rgba(255,255,255,0.04)',
      }}>
        {/* Total Databases */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: '14px',
          background: 'rgba(20,25,35,0.6)', border: '1px solid rgba(255,255,255,0.05)',
          borderRadius: '10px', padding: '14px 18px',
        }}>
          <div style={{ width: '40px', height: '40px', borderRadius: '9px', background: 'rgba(168,85,247,0.12)', color: '#a855f7', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
            <Database size={20} />
          </div>
          <div>
            <p style={{ margin: 0, fontSize: '11px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: '600' }}>Total Databases</p>
            <h3 style={{ margin: '3px 0 0', fontSize: '26px', color: '#ffffff', fontWeight: '700', lineHeight: 1 }}>{stats?.total_databases ?? 0}</h3>
          </div>
        </div>

        {/* Entities Extracted */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: '14px',
          background: 'rgba(20,25,35,0.6)', border: '1px solid rgba(255,255,255,0.05)',
          borderRadius: '10px', padding: '14px 18px',
        }}>
          <div style={{ width: '40px', height: '40px', borderRadius: '9px', background: 'rgba(16,185,129,0.1)', color: '#10b981', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
            <Layers size={20} />
          </div>
          <div>
            <p style={{ margin: 0, fontSize: '11px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: '600' }}>Abstract Entities</p>
            <h3 style={{ margin: '3px 0 0', fontSize: '26px', color: '#10b981', fontWeight: '700', lineHeight: 1 }}>{stats?.entities_identified ?? 0}</h3>
          </div>
        </div>

        {/* Service Health */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: '14px',
          background: 'rgba(20,25,35,0.6)', border: '1px solid rgba(255,255,255,0.05)',
          borderRadius: '10px', padding: '14px 18px',
        }}>
          <div style={{ width: '40px', height: '40px', borderRadius: '9px', background: 'rgba(6,182,212,0.1)', color: '#06b6d4', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
            <Activity size={20} />
          </div>
          <div>
            <p style={{ margin: 0, fontSize: '11px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: '600' }}>Service Layer</p>
            <h3 style={{ margin: '3px 0 0', fontSize: '15px', color: '#06b6d4', fontWeight: '600', lineHeight: 1.3 }}>Active (Neo4j / ES)</h3>
          </div>
        </div>
      </div>

      {/* ── Split Pane: Registry Table (left) | Knowledge Graph (right) ── */}
      <div
        ref={containerRef}
        style={{
          flex: 1,
          display: 'grid',
          gridTemplateColumns: `${leftWidth}px 4px 1fr`,
          overflow: 'hidden',
          background: 'rgba(255,255,255,0.04)',
          position: 'relative'
        }}
      >

        {/* LEFT: Registered Databases Table */}
        <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden', background: 'rgba(10,14,20,0.95)' }}>
          {/* Panel Header */}
          <div style={{
            padding: '14px 18px',
            borderBottom: '1px solid rgba(255,255,255,0.05)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            background: 'rgba(0,0,0,0.2)', flexShrink: 0,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span className="panel-step-badge">IDB</span>
              <h2 className="panel-title" style={{ margin: 0, fontSize: '14px' }}>Registered Databases</h2>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <button
                type="button"
                onClick={fetchStats}
                disabled={isLoading}
                style={{
                  background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)',
                  color: '#94a3b8', padding: '5px 10px', borderRadius: '6px',
                  fontSize: '11px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '5px',
                }}
              >
                <RefreshCw size={11} className={isLoading ? 'animate-spin' : ''} />
                <span>Refresh</span>
              </button>
              <button
                type="button"
                onClick={handleClearAll}
                disabled={clearingGraph}
                style={{
                  background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)',
                  color: '#ef4444', padding: '5px 10px', borderRadius: '6px',
                  fontSize: '11px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '5px', fontWeight: '500',
                }}
              >
                {clearingGraph ? (
                  <><Loader2 size={11} className="animate-spin" /><span>Wiping...</span></>
                ) : (
                  <><AlertTriangle size={11} /><span>Clear All</span></>
                )}
              </button>
            </div>
          </div>

          {/* Table */}
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {isLoading ? (
              <div style={{ height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '12px', color: '#64748b' }}>
                <Loader2 size={28} className="animate-spin" style={{ color: '#a855f7' }} />
                <span style={{ fontSize: '12px' }}>Loading databases...</span>
              </div>
            ) : stats?.databases && stats.databases.length > 0 ? (
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '12px' }}>
                <thead>
                  <tr style={{ background: 'rgba(0,0,0,0.25)', color: '#64748b', borderBottom: '1px solid rgba(255,255,255,0.05)', position: 'sticky', top: 0, zIndex: 1 }}>
                    <th style={{ padding: '12px 16px', fontWeight: '600' }}>Name</th>
                    <th style={{ padding: '12px 16px', fontWeight: '600' }}>ID Hash</th>
                    <th style={{ padding: '12px 16px', fontWeight: '600' }}>Status</th>
                    <th style={{ padding: '12px 16px', fontWeight: '600', textAlign: 'right' }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.databases.map((db, idx) => (
                    <tr
                      key={db.id}
                      style={{
                        borderBottom: '1px solid rgba(255,255,255,0.03)',
                        background: idx % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)',
                        transition: 'background 0.15s',
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(168,85,247,0.04)'; }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = idx % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)'; }}
                    >
                      <td style={{ padding: '13px 16px', color: '#ffffff', fontWeight: '500' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <Database size={14} style={{ color: '#a855f7', flexShrink: 0 }} />
                          <span>{db.name}</span>
                        </div>
                      </td>
                      <td style={{ padding: '13px 16px', fontFamily: 'monospace', color: '#475569', fontSize: '10px' }}>
                        {db.id.slice(0, 12)}…
                      </td>
                      <td style={{ padding: '13px 16px' }}>
                        {db.status?.startsWith('failed') ? (
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '3px 7px', borderRadius: '4px', background: 'rgba(239,68,68,0.1)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.2)', fontSize: '10px' }}>
                            <XCircle size={11} /><span>Failed</span>
                          </span>
                        ) : db.status === 'running' ? (
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '3px 7px', borderRadius: '4px', background: 'rgba(59,130,246,0.1)', color: '#3b82f6', border: '1px solid rgba(59,130,246,0.2)', fontSize: '10px' }}>
                            <Loader2 size={11} className="animate-spin" /><span>Running</span>
                          </span>
                        ) : (
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '3px 7px', borderRadius: '4px', background: 'rgba(16,185,129,0.1)', color: '#10b981', border: '1px solid rgba(16,185,129,0.2)', fontSize: '10px' }}>
                            <CheckCircle size={11} /><span>Active</span>
                          </span>
                        )}
                      </td>
                      <td style={{ padding: '13px 16px', textAlign: 'right' }}>
                        <button
                          type="button"
                          onClick={() => handleDelete(db.id, db.name)}
                          disabled={deletingId === db.id}
                          title="Delete Schema"
                          style={{
                            background: 'transparent', border: 'none', color: '#ef4444',
                            cursor: 'pointer', padding: '5px', borderRadius: '4px',
                            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                            transition: 'all 0.15s',
                          }}
                          onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(239,68,68,0.1)'; }}
                          onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
                        >
                          {deletingId === db.id
                            ? <Loader2 size={14} className="animate-spin" />
                            : <Trash2 size={14} />
                          }
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div style={{ height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '12px', color: '#64748b' }}>
                <Database size={42} style={{ color: '#334155', opacity: 0.5 }} />
                <h3 style={{ margin: 0, color: '#94a3b8', fontSize: '14px' }}>No Connected Databases</h3>
                <p style={{ margin: 0, fontSize: '12px', textAlign: 'center', maxWidth: '260px' }}>
                  Go to the Onboarding tab to configure and onboard database schemas.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Divider / Splitter bar */}
        <div
          onMouseDown={handleMouseDown}
          style={{
            width: '4px',
            cursor: 'col-resize',
            background: isDragging ? '#a855f7' : 'rgba(255,255,255,0.08)',
            transition: 'background 0.2s',
            zIndex: 10,
            position: 'relative',
          }}
          onMouseEnter={(e) => { if (!isDragging) e.currentTarget.style.background = 'rgba(168,85,247,0.5)'; }}
          onMouseLeave={(e) => { if (!isDragging) e.currentTarget.style.background = 'rgba(255,255,255,0.08)'; }}
        />

        {/* RIGHT: Knowledge Graph Panel */}
        <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden', background: 'rgba(6,9,13,0.98)' }}>
          <KnowledgeGraphPanel refreshKey={graphRefreshKey} />
        </div>

      </div>
    </div>
  );
}
