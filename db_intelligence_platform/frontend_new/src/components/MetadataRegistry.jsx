import React, { useState, useEffect, useCallback, useRef } from 'react';
import ReactFlow, {
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  useReactFlow,
  ReactFlowProvider,
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
  Sun,
  Moon,
  Search,
} from 'lucide-react';

/* ─────────────────────────────────────────────────────────
   Custom ReactFlow node styles generator (light/dark themed)
   ───────────────────────────────────────────────────────── */
const getRfNodeStyles = (theme) => ({
  Database: {
    background: theme === 'light'
      ? 'linear-gradient(135deg, rgba(168,85,247,0.15), rgba(109,40,217,0.05))'
      : 'linear-gradient(135deg, rgba(168,85,247,0.25), rgba(109,40,217,0.15))',
    border: theme === 'light' ? '1px solid rgba(168,85,247,0.6)' : '1px solid rgba(168,85,247,0.5)',
    borderRadius: '10px',
    color: theme === 'light' ? '#6d28d9' : '#e9d5ff',
    fontSize: '11px',
    fontWeight: '700',
    padding: '8px 14px',
    backdropFilter: 'blur(8px)',
    textAlign: 'center',
    minWidth: '90px',
  },
  Entity: {
    background: theme === 'light'
      ? 'linear-gradient(135deg, rgba(6,182,212,0.08), rgba(8,145,178,0.04))'
      : 'linear-gradient(135deg, rgba(6,182,212,0.12), rgba(8,145,178,0.08))',
    border: theme === 'light' ? '1px solid rgba(6,182,212,0.4)' : '1px solid rgba(6,182,212,0.3)',
    borderRadius: '8px',
    color: theme === 'light' ? '#0891b2' : '#a5f3fc',
    fontSize: '10px',
    fontWeight: '500',
    padding: '6px 10px',
    backdropFilter: 'blur(8px)',
    textAlign: 'center',
    minWidth: '72px',
  },
  Table: {
    background: theme === 'light'
      ? 'linear-gradient(135deg, rgba(234,179,8,0.08), rgba(202,138,4,0.04))'
      : 'linear-gradient(135deg, rgba(234,179,8,0.12), rgba(202,138,4,0.08))',
    border: theme === 'light' ? '1px solid rgba(234,179,8,0.4)' : '1px solid rgba(234,179,8,0.3)',
    borderRadius: '8px',
    color: theme === 'light' ? '#a16207' : '#fef08a',
    fontSize: '10px',
    fontWeight: '500',
    padding: '6px 10px',
    backdropFilter: 'blur(8px)',
    textAlign: 'center',
    minWidth: '72px',
  },
  Column: {
    background: theme === 'light'
      ? 'linear-gradient(135deg, rgba(244,63,94,0.08), rgba(225,29,72,0.04))'
      : 'linear-gradient(135deg, rgba(244,63,94,0.12), rgba(225,29,72,0.08))',
    border: theme === 'light' ? '1px solid rgba(244,63,94,0.4)' : '1px solid rgba(244,63,94,0.3)',
    borderRadius: '8px',
    color: theme === 'light' ? '#be123c' : '#fecdd3',
    fontSize: '10px',
    fontWeight: '500',
    padding: '6px 10px',
    backdropFilter: 'blur(8px)',
    textAlign: 'center',
    minWidth: '72px',
  },
});

/* ─────────────────────────────────────────────────────────
   Knowledge Graph Panel
   ───────────────────────────────────────────────────────── */
function KnowledgeGraphPanel({ refreshKey, theme }) {
  const [rawGraphData, setRawGraphData] = useState({ nodes: [], edges: [] });
  const [graphLoading, setGraphLoading] = useState(true);
  const [showDatabases, setShowDatabases] = useState(true);
  const [showTables, setShowTables] = useState(false);
  const [showColumns, setShowColumns] = useState(false);
  const [nodeCount, setNodeCount] = useState(0);
  const [edgeCount, setEdgeCount] = useState(0);

  const [nodes, setNodes, onNodesChangeCore] = useNodesState([]);

  // Search feature states & hooks
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const { setCenter } = useReactFlow();
  const dropdownRef = useRef(null);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const savedPositions = useRef(new Map());
  const draggedNodes = useRef(new Set());

  // Edit Mode states
  const [editMode, setEditMode] = useState(false);
  const [nodeCreateModal, setNodeCreateModal] = useState(null); // { type, position }
  const [edgeCreateModal, setEdgeCreateModal] = useState(null); // { source, target }
  const [newNodeName, setNewNodeName] = useState('');
  const [newNodeDesc, setNewNodeDesc] = useState('');
  const [newEdgeType, setNewEdgeType] = useState('RELATES_TO');
  const [reactFlowInstance, setReactFlowInstance] = useState(null);
  const reactFlowWrapper = useRef(null);
  const [deleteToast, setDeleteToast] = useState(null); // Local deletion toast

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

  // Search input change handler
  const handleSearchChange = (e) => {
    const query = e.target.value;
    setSearchQuery(query);
    if (query.trim() === '') {
      setSearchResults([]);
      setShowDropdown(false);
      return;
    }

    // Filter nodes by label or id
    const matches = nodes.filter(n => {
      const label = n.data?.label || '';
      return label.toLowerCase().includes(query.toLowerCase()) || n.id.toLowerCase().includes(query.toLowerCase());
    }).slice(0, 5); // limit to 5 results

    setSearchResults(matches);
    setShowDropdown(true);
  };

  // Click handler for suggestion
  const handleSelectNode = (node) => {
    setSearchQuery(node.data?.label ? node.data.label.replace(/^\[.*?\]\n/, '') : node.id);
    setShowDropdown(false);
    
    // Animate to node center
    const x = node.position.x + 75; // approximation of node center
    const y = node.position.y + 20;
    setCenter(x, y, { zoom: 1.5, duration: 800 });

    // Highlight node temporarily
    setNodes((nds) => nds.map((n) => {
      if (n.id === node.id) {
        return {
          ...n,
          selected: true,
          style: {
            ...n.style,
            boxShadow: theme === 'light' 
              ? '0 0 0 4px rgba(168,85,247,0.4), 0 0 16px rgba(168,85,247,0.3)' 
              : '0 0 0 4px rgba(168,85,247,0.6), 0 0 24px rgba(168,85,247,0.5)',
            transform: 'scale(1.05)',
            transition: 'all 0.2s ease-in-out'
          }
        };
      }
      return n;
    }));

    // Reset highlight after 2.5 seconds
    setTimeout(() => {
      setNodes((nds) => nds.map((n) => {
        if (n.id === node.id) {
          const styles = getRfNodeStyles(theme);
          let style = styles.Entity;
          const labelText = n.data?.label || '';
          if (labelText.startsWith('[Database]') || n.type === 'input') {
            style = styles.Database;
          } else if (labelText.startsWith('[Table]')) {
            style = styles.Table;
          } else if (labelText.startsWith('[Column]')) {
            style = styles.Column;
          }
          return {
            ...n,
            selected: false,
            style: {
              ...style,
              transition: 'all 0.3s ease-out'
            }
          };
        }
        return n;
      }));
    }, 2500);
  };

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // HTML5 Drag-and-Drop Handlers
  const onDragStart = (event, nodeType) => {
    event.dataTransfer.setData('application/reactflow', nodeType);
    event.dataTransfer.effectAllowed = 'move';
  };

  const onDragOver = useCallback((event) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback(
    (event) => {
      event.preventDefault();

      if (!reactFlowWrapper.current || !reactFlowInstance) return;

      const reactFlowBounds = reactFlowWrapper.current.getBoundingClientRect();
      const type = event.dataTransfer.getData('application/reactflow');

      if (!type) return;

      const position = reactFlowInstance.project({
        x: event.clientX - reactFlowBounds.left,
        y: event.clientY - reactFlowBounds.top,
      });

      setNodeCreateModal({
        type,
        position
      });
    },
    [reactFlowInstance]
  );

  // Submit node creation to backend
  const handleCreateNodeSubmit = async () => {
    if (!newNodeName.trim()) return;

    const id = `custom_${nodeCreateModal.type.toLowerCase()}_${Date.now()}`;
    const name = newNodeName.trim();
    const type = nodeCreateModal.type;
    const description = newNodeDesc.trim();

    try {
      const res = await fetch('/api/v1/graph/node', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, name, type, description })
      });
      if (!res.ok) throw new Error("Failed to save custom node on server");

      const styles = getRfNodeStyles(theme);
      let style = styles.Entity;
      if (type === 'Database') style = styles.Database;
      else if (type === 'Table') style = styles.Table;
      else if (type === 'Column') style = styles.Column;

      const newNode = {
        id,
        type: type === 'Database' ? 'input' : 'default',
        data: { label: `[${type}]\n${name}` },
        position: nodeCreateModal.position,
        style: { ...style, transition: 'all 0.3s ease-out' }
      };

      setNodes((nds) => [...nds, newNode]);
      setNodeCreateModal(null);
      setNewNodeName('');
      setNewNodeDesc('');
    } catch (err) {
      console.error(err);
      alert(`Create Node Failed: ${err.message}`);
    }
  };

  // Submit edge creation to backend
  const handleCreateEdgeSubmit = async () => {
    const source = edgeCreateModal.source;
    const target = edgeCreateModal.target;
    const type = newEdgeType;

    try {
      const res = await fetch('/api/v1/graph/edge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source, target, type })
      });
      if (!res.ok) throw new Error("Failed to save relationship on server");

      const newEdge = {
        id: `${source}-${target}-${type}`,
        source,
        target,
        label: type,
        animated: type !== 'CONTAINS',
        style: {
          stroke: theme === 'light' ? 'rgba(168,85,247,0.5)' : 'rgba(168,85,247,0.3)',
          strokeWidth: 1.5
        },
        labelStyle: { fill: theme === 'light' ? '#475569' : '#94a3b8', fontSize: 9 },
        labelBgStyle: {
          fill: theme === 'light' ? '#f1f5f9' : 'rgba(10,14,20,0.85)',
          fillOpacity: 0.9,
        },
        markerEnd: { type: 'arrowclosed', color: type === 'CONTAINS' ? '#a855f7' : '#06b6d4' }
      };

      setEdges((eds) => addEdge(newEdge, eds));
      setEdgeCreateModal(null);
      setNewEdgeType('RELATES_TO');
    } catch (err) {
      console.error(err);
      alert(`Create Relationship Failed: ${err.message}`);
    }
  };

  // Delete selected nodes/edges from canvas and Neo4j
  const handleDeleteSelected = async () => {
    const selectedNodes = nodes.filter((n) => n.selected);
    const selectedEdges = edges.filter((e) => e.selected);

    if (selectedNodes.length === 0 && selectedEdges.length === 0) return;

    if (!window.confirm("Are you sure you want to delete the selected elements from the Knowledge Graph?")) return;

    try {
      for (const node of selectedNodes) {
        const res = await fetch(`/api/v1/graph/node/${node.id}`, { method: 'DELETE' });
        if (!res.ok) throw new Error(`Failed to delete node ${node.id}`);
      }

      for (const edge of selectedEdges) {
        const type = edge.label || 'RELATES_TO';
        const res = await fetch(`/api/v1/graph/edge/${edge.source}/${edge.target}/${type}`, { method: 'DELETE' });
        if (!res.ok) throw new Error(`Failed to delete edge`);
      }

      setNodes((nds) => nds.filter((n) => !n.selected));
      setEdges((eds) => eds.filter((e) => !e.selected));

      setDeleteToast("Selected elements deleted successfully.");
      setTimeout(() => setDeleteToast(null), 3500);
    } catch (err) {
      console.error(err);
      alert(`Deletion failed: ${err.message}`);
    }
  };

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

  // Update node and edge styles dynamically on theme change
  useEffect(() => {
    const styles = getRfNodeStyles(theme);
    setNodes(prevNodes => prevNodes.map(node => {
      const labelText = node.data?.label || '';
      let style = styles.Entity;
      if (labelText.startsWith('[Database]') || node.type === 'input') {
        style = styles.Database;
      } else if (labelText.startsWith('[Table]')) {
        style = styles.Table;
      } else if (labelText.startsWith('[Column]')) {
        style = styles.Column;
      }
      return {
        ...node,
        style,
      };
    }));

    setEdges(prevEdges => prevEdges.map(edge => ({
      ...edge,
      style: {
        ...edge.style,
        stroke: edge.animated 
          ? (theme === 'light' ? 'rgba(6,182,212,0.8)' : 'rgba(6,182,212,0.5)')
          : (theme === 'light' ? 'rgba(168,85,247,0.5)' : 'rgba(168,85,247,0.3)'),
      },
      labelStyle: {
        ...edge.labelStyle,
        fill: theme === 'light' ? '#475569' : '#94a3b8',
      },
      labelBgStyle: {
        ...edge.labelBgStyle,
        fill: theme === 'light' ? '#f1f5f9' : 'rgba(10,14,20,0.85)',
      }
    })));
  }, [theme, setNodes, setEdges]);

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

      const styles = getRfNodeStyles(theme);

      return filteredNodes.map((node) => {
        const labelText = node.data?.label || '';
        let style = styles.Entity;
        let isDb = false;
        let x = 0;
        let y = 160;

        if (labelText.startsWith('[Database]') || node.type === 'input') {
          style = styles.Database;
          isDb = true;
          x = 300 + (dbCount % 3) * 320;
          y = dbStartY;
          dbCount++;
        } else if (labelText.startsWith('[Table]')) {
          style = styles.Table;
          x = (tableCount % tableColumns) * 240;
          y = tableStartY + Math.floor(tableCount / tableColumns) * 130;
          tableCount++;
        } else if (labelText.startsWith('[Column]')) {
          style = styles.Column;
          x = (columnCount % 6) * 180;
          y = columnStartY + Math.floor(columnCount / 6) * 130;
          columnCount++;
        } else {
          style = styles.Entity;
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
          stroke: e.animated 
            ? (theme === 'light' ? 'rgba(6,182,212,0.8)' : 'rgba(6,182,212,0.5)')
            : (theme === 'light' ? 'rgba(168,85,247,0.5)' : 'rgba(168,85,247,0.3)'),
          strokeWidth: 1.5,
        },
        labelStyle: { fill: theme === 'light' ? '#475569' : '#94a3b8', fontSize: 9 },
        labelBgStyle: {
          fill: theme === 'light' ? '#f1f5f9' : 'rgba(10,14,20,0.85)',
          fillOpacity: 0.9,
        },
        markerEnd: { type: 'arrowclosed', color: e.animated ? '#06b6d4' : '#a855f7' },
      }))
    );
  }, [rawGraphData, showDatabases, showTables, showColumns, setNodes, setEdges, theme]);

  const onConnect = useCallback(
    (params) => {
      if (!editMode) {
        setEdges((eds) => addEdge(params, eds));
        return;
      }
      setEdgeCreateModal({
        source: params.source,
        target: params.target
      });
    },
    [editMode, setEdges]
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 0 }}>
      {/* Graph Panel Header */}
      <div style={{
        padding: '14px 18px',
        borderBottom: theme === 'light' ? '1px solid #cbd5e1' : '1px solid rgba(255,255,255,0.05)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: theme === 'light' ? '#f8fafc' : 'rgba(0,0,0,0.2)',
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

        {/* Search Box */}
        <div ref={dropdownRef} style={{ position: 'relative', flex: 1, maxWidth: '200px', margin: '0 16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', position: 'relative' }}>
            <Search size={12} style={{ position: 'absolute', left: '10px', color: '#64748b', pointerEvents: 'none' }} />
            <input
              type="text"
              value={searchQuery}
              onChange={handleSearchChange}
              onFocus={() => { if (searchResults.length > 0) setShowDropdown(true); }}
              placeholder="Search graph nodes..."
              style={{
                width: '100%',
                background: theme === 'light' ? '#ffffff' : 'rgba(255, 255, 255, 0.04)',
                border: theme === 'light' ? '1px solid #cbd5e1' : '1px solid rgba(255, 255, 255, 0.08)',
                borderRadius: '6px',
                padding: '6px 10px 6px 28px',
                fontSize: '11px',
                color: theme === 'light' ? '#0f172a' : '#ffffff',
                outline: 'none',
                transition: 'border-color 0.2s',
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && searchResults.length > 0) {
                  handleSelectNode(searchResults[0]);
                }
              }}
            />
          </div>

          {/* Dropdown Suggestions */}
          {showDropdown && searchResults.length > 0 && (
            <div style={{
              position: 'absolute',
              top: '100%',
              left: 0,
              right: 0,
              background: theme === 'light' ? '#ffffff' : '#1e293b',
              border: theme === 'light' ? '1px solid #cbd5e1' : '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: '6px',
              marginTop: '4px',
              boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.3)',
              zIndex: 1000,
              maxHeight: '200px',
              overflowY: 'auto',
            }}>
              {searchResults.map((node) => {
                const labelText = node.data?.label || '';
                const type = labelText.match(/^\[(.*?)\]/)?.[1] || 'Node';
                const name = labelText.replace(/^\[.*?\]\n/, '');
                
                let badgeBg = 'rgba(6,182,212,0.1)';
                let badgeColor = '#06b6d4';
                if (type === 'Database') { badgeBg = 'rgba(168,85,247,0.1)'; badgeColor = '#a855f7'; }
                else if (type === 'Table') { badgeBg = 'rgba(234,179,8,0.1)'; badgeColor = '#eab308'; }
                else if (type === 'Column') { badgeBg = 'rgba(244,63,94,0.1)'; badgeColor = '#f43f5e'; }

                return (
                  <div
                    key={node.id}
                    onClick={() => handleSelectNode(node)}
                    style={{
                      padding: '8px 12px',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      fontSize: '11px',
                      borderBottom: theme === 'light' ? '1px solid #f1f5f9' : '1px solid rgba(255,255,255,0.03)',
                      transition: 'background 0.15s',
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = theme === 'light' ? '#f1f5f9' : 'rgba(255,255,255,0.05)'; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
                  >
                    <span style={{ fontWeight: '500', color: theme === 'light' ? '#0f172a' : '#f8fafc', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '110px' }}>
                      {name || node.id}
                    </span>
                    <span style={{
                      fontSize: '9px',
                      padding: '2px 6px',
                      borderRadius: '4px',
                      background: badgeBg,
                      color: badgeColor,
                      fontWeight: '600',
                      flexShrink: 0
                    }}>
                      {type}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {/* Toggle DB Nodes */}
          <button
            type="button"
            onClick={() => setShowDatabases(!showDatabases)}
            title={showDatabases ? 'Hide DB nodes' : 'Show DB nodes'}
            style={{
              background: showDatabases ? 'rgba(168,85,247,0.15)' : (theme === 'light' ? '#ffffff' : 'rgba(255,255,255,0.03)'),
              border: `1px solid ${showDatabases ? 'rgba(168,85,247,0.4)' : (theme === 'light' ? '#cbd5e1' : 'rgba(255,255,255,0.08)')}`,
              color: showDatabases ? '#a855f7' : (theme === 'light' ? '#475569' : '#64748b'),
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
              background: showTables ? 'rgba(234,179,8,0.15)' : (theme === 'light' ? '#ffffff' : 'rgba(255,255,255,0.03)'),
              border: `1px solid ${showTables ? 'rgba(234,179,8,0.4)' : (theme === 'light' ? '#cbd5e1' : 'rgba(255,255,255,0.08)')}`,
              color: showTables ? '#eab308' : (theme === 'light' ? '#475569' : '#64748b'),
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
              background: showColumns ? 'rgba(244,63,94,0.15)' : (theme === 'light' ? '#ffffff' : 'rgba(255,255,255,0.03)'),
              border: `1px solid ${showColumns ? 'rgba(244,63,94,0.4)' : (theme === 'light' ? '#cbd5e1' : 'rgba(255,255,255,0.08)')}`,
              color: showColumns ? '#f43f5e' : (theme === 'light' ? '#475569' : '#64748b'),
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
              background: theme === 'light' ? '#ffffff' : 'rgba(255,255,255,0.03)',
              border: theme === 'light' ? '1px solid #cbd5e1' : '1px solid rgba(255,255,255,0.08)',
              color: theme === 'light' ? '#475569' : '#94a3b8',
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

          {/* Edit Mode Toggle */}
          <button
            type="button"
            onClick={() => {
              setEditMode(!editMode);
              if (editMode) {
                setNodes((nds) => nds.map((n) => ({ ...n, selected: false })));
                setEdges((eds) => eds.map((e) => ({ ...e, selected: false })));
              }
            }}
            style={{
              background: editMode ? 'rgba(168,85,247,0.15)' : (theme === 'light' ? '#ffffff' : 'rgba(255,255,255,0.03)'),
              border: `1px solid ${editMode ? 'rgba(168,85,247,0.5)' : (theme === 'light' ? '#cbd5e1' : 'rgba(255,255,255,0.08)')}`,
              color: editMode ? '#a855f7' : (theme === 'light' ? '#475569' : '#94a3b8'),
              padding: '5px 10px',
              borderRadius: '6px',
              fontSize: '11px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
              fontWeight: editMode ? '600' : 'normal'
            }}
          >
            <span>{editMode ? 'Edit Mode ON' : 'Edit Mode OFF'}</span>
          </button>
        </div>
      </div>

      {/* ReactFlow Canvas */}
      <div 
        ref={reactFlowWrapper} 
        style={{ flex: 1, position: 'relative', background: theme === 'light' ? '#f8fafc' : 'rgba(6,9,13,0.8)' }}
      >
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
            onInit={setReactFlowInstance}
            onDragOver={onDragOver}
            onDrop={onDrop}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            proOptions={{ hideAttribution: true }}
          >
            <Controls
              style={{
                background: theme === 'light' ? '#ffffff' : 'rgba(14,18,26,0.9)',
                border: theme === 'light' ? '1px solid #cbd5e1' : '1px solid rgba(255,255,255,0.08)',
                borderRadius: '8px',
                color: theme === 'light' ? '#0f172a' : '#ffffff',
              }}
            />
            <MiniMap
              style={{
                background: theme === 'light' ? '#ffffff' : 'rgba(10,14,20,0.95)',
                border: theme === 'light' ? '1px solid #cbd5e1' : '1px solid rgba(255,255,255,0.06)',
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
              color={theme === 'light' ? 'rgba(0,0,0,0.06)' : "rgba(255,255,255,0.03)"}
              gap={20}
              size={1}
            />
          </ReactFlow>
        )}

        {/* Drag-and-Drop Side Palette */}
        {editMode && (
          <div style={{
            position: 'absolute',
            top: '16px',
            left: '16px',
            zIndex: 100,
            background: theme === 'light' ? '#ffffff' : 'rgba(10,14,20,0.95)',
            border: theme === 'light' ? '1px solid #cbd5e1' : '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: '8px',
            padding: '12px',
            width: '140px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
            display: 'flex',
            flexDirection: 'column',
            gap: '10px',
            color: theme === 'light' ? '#0f172a' : '#f8fafc',
            textAlign: 'left'
          }}>
            <h4 style={{ margin: '0 0 4px 0', fontSize: '11px', textTransform: 'uppercase', color: '#64748b', fontWeight: '700', letterSpacing: '0.04em' }}>Palette</h4>
            
            <div 
              draggable
              onDragStart={(e) => onDragStart(e, 'Database')}
              style={{
                padding: '6px 10px',
                borderRadius: '6px',
                background: theme === 'light' ? 'rgba(168,85,247,0.08)' : 'rgba(168,85,247,0.15)',
                border: '1px dashed #a855f7',
                color: '#a855f7',
                fontSize: '10px',
                fontWeight: '600',
                cursor: 'grab',
                textAlign: 'center'
              }}
            >
              + Database
            </div>
            
            <div 
              draggable
              onDragStart={(e) => onDragStart(e, 'Table')}
              style={{
                padding: '6px 10px',
                borderRadius: '6px',
                background: theme === 'light' ? 'rgba(234,179,8,0.08)' : 'rgba(234,179,8,0.15)',
                border: '1px dashed #eab308',
                color: '#eab308',
                fontSize: '10px',
                fontWeight: '600',
                cursor: 'grab',
                textAlign: 'center'
              }}
            >
              + Table
            </div>

            <div 
              draggable
              onDragStart={(e) => onDragStart(e, 'Column')}
              style={{
                padding: '6px 10px',
                borderRadius: '6px',
                background: theme === 'light' ? 'rgba(244,63,94,0.08)' : 'rgba(244,63,94,0.15)',
                border: '1px dashed #f43f5e',
                color: '#f43f5e',
                fontSize: '10px',
                fontWeight: '600',
                cursor: 'grab',
                textAlign: 'center'
              }}
            >
              + Column
            </div>

            <div 
              draggable
              onDragStart={(e) => onDragStart(e, 'Entity')}
              style={{
                padding: '6px 10px',
                borderRadius: '6px',
                background: theme === 'light' ? 'rgba(6,182,212,0.08)' : 'rgba(6,182,212,0.15)',
                border: '1px dashed #06b6d4',
                color: '#06b6d4',
                fontSize: '10px',
                fontWeight: '600',
                cursor: 'grab',
                textAlign: 'center'
              }}
            >
              + Entity
            </div>

            <hr style={{ margin: '4px 0', border: 0, borderTop: theme === 'light' ? '1px solid #cbd5e1' : '1px solid rgba(255,255,255,0.08)' }} />

            <button
              type="button"
              disabled={!(nodes.some(n => n.selected) || edges.some(e => e.selected))}
              onClick={handleDeleteSelected}
              style={{
                width: '100%',
                padding: '6px 10px',
                borderRadius: '6px',
                background: (nodes.some(n => n.selected) || edges.some(e => e.selected)) ? 'rgba(239,68,68,0.1)' : 'transparent',
                border: `1px solid ${(nodes.some(n => n.selected) || edges.some(e => e.selected)) ? '#ef4444' : (theme === 'light' ? '#cbd5e1' : 'rgba(255,255,255,0.08)')}`,
                color: (nodes.some(n => n.selected) || edges.some(e => e.selected)) ? '#ef4444' : '#64748b',
                fontSize: '10px',
                fontWeight: '600',
                cursor: (nodes.some(n => n.selected) || edges.some(e => e.selected)) ? 'pointer' : 'not-allowed',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '4px'
              }}
            >
              <Trash2 size={10} />
              <span>Delete Selected</span>
            </button>
          </div>
        )}

        {/* Node Create Modal */}
        {nodeCreateModal && (
          <div style={{
            position: 'absolute',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.6)',
            backdropFilter: 'blur(3px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}>
            <div style={{
              background: theme === 'light' ? '#ffffff' : '#111827',
              border: theme === 'light' ? '1px solid #cbd5e1' : '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '10px',
              padding: '20px',
              width: '320px',
              boxShadow: '0 10px 25px rgba(0,0,0,0.3)',
              color: theme === 'light' ? '#0f172a' : '#ffffff',
              textAlign: 'left'
            }}>
              <h4 style={{ margin: '0 0 14px 0', fontSize: '13px', fontWeight: '600' }}>
                Create Custom {nodeCreateModal.type}
              </h4>
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div>
                  <label style={{ fontSize: '10px', color: '#64748b', fontWeight: '600', display: 'block', marginBottom: '4px' }}>Name</label>
                  <input
                    type="text"
                    value={newNodeName}
                    onChange={(e) => setNewNodeName(e.target.value)}
                    placeholder="Enter name..."
                    style={{
                      width: '100%',
                      background: theme === 'light' ? '#ffffff' : 'rgba(255,255,255,0.03)',
                      border: theme === 'light' ? '1px solid #cbd5e1' : '1px solid rgba(255, 255, 255, 0.08)',
                      borderRadius: '6px',
                      padding: '6px 10px',
                      fontSize: '11px',
                      color: theme === 'light' ? '#0f172a' : '#ffffff',
                      outline: 'none'
                    }}
                  />
                </div>
                
                <div>
                  <label style={{ fontSize: '10px', color: '#64748b', fontWeight: '600', display: 'block', marginBottom: '4px' }}>Description</label>
                  <textarea
                    value={newNodeDesc}
                    onChange={(e) => setNewNodeDesc(e.target.value)}
                    placeholder="Enter description..."
                    rows={3}
                    style={{
                      width: '100%',
                      background: theme === 'light' ? '#ffffff' : 'rgba(255,255,255,0.03)',
                      border: theme === 'light' ? '1px solid #cbd5e1' : '1px solid rgba(255, 255, 255, 0.08)',
                      borderRadius: '6px',
                      padding: '6px 10px',
                      fontSize: '11px',
                      color: theme === 'light' ? '#0f172a' : '#ffffff',
                      outline: 'none',
                      resize: 'none'
                    }}
                  />
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '16px' }}>
                <button
                  type="button"
                  onClick={() => { setNodeCreateModal(null); setNewNodeName(''); setNewNodeDesc(''); }}
                  style={{
                    background: theme === 'light' ? '#f3f4f6' : 'rgba(255,255,255,0.03)',
                    border: theme === 'light' ? '1px solid #cbd5e1' : '1px solid rgba(255,255,255,0.08)',
                    color: theme === 'light' ? '#475569' : '#94a3b8',
                    padding: '5px 12px',
                    borderRadius: '5px',
                    fontSize: '11px',
                    cursor: 'pointer'
                  }}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleCreateNodeSubmit}
                  disabled={!newNodeName.trim()}
                  style={{
                    background: '#a855f7',
                    border: 'none',
                    color: '#ffffff',
                    padding: '5px 12px',
                    borderRadius: '5px',
                    fontSize: '11px',
                    cursor: 'pointer',
                    fontWeight: '600'
                  }}
                >
                  Create
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Edge Create Modal */}
        {edgeCreateModal && (
          <div style={{
            position: 'absolute',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.6)',
            backdropFilter: 'blur(3px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}>
            <div style={{
              background: theme === 'light' ? '#ffffff' : '#111827',
              border: theme === 'light' ? '1px solid #cbd5e1' : '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '10px',
              padding: '20px',
              width: '300px',
              boxShadow: '0 10px 25px rgba(0,0,0,0.3)',
              color: theme === 'light' ? '#0f172a' : '#ffffff',
              textAlign: 'left'
            }}>
              <h4 style={{ margin: '0 0 14px 0', fontSize: '13px', fontWeight: '600' }}>
                Add Relationship
              </h4>
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div>
                  <label style={{ fontSize: '10px', color: '#64748b', fontWeight: '600', display: 'block', marginBottom: '4px' }}>Relationship Type</label>
                  <select
                    value={newEdgeType}
                    onChange={(e) => setNewEdgeType(e.target.value)}
                    style={{
                      width: '100%',
                      background: theme === 'light' ? '#ffffff' : '#1e293b',
                      border: theme === 'light' ? '1px solid #cbd5e1' : '1px solid rgba(255, 255, 255, 0.08)',
                      borderRadius: '6px',
                      padding: '6px 10px',
                      fontSize: '11px',
                      color: theme === 'light' ? '#0f172a' : '#ffffff',
                      outline: 'none'
                    }}
                  >
                    <option value="RELATES_TO">RELATES_TO</option>
                    <option value="CONTAINS">CONTAINS</option>
                    <option value="HAS_TABLE">HAS_TABLE</option>
                    <option value="HAS_COLUMN">HAS_COLUMN</option>
                    <option value="MAPS_TO">MAPS_TO</option>
                  </select>
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '16px' }}>
                <button
                  type="button"
                  onClick={() => { setEdgeCreateModal(null); setNewEdgeType('RELATES_TO'); }}
                  style={{
                    background: theme === 'light' ? '#f3f4f6' : 'rgba(255,255,255,0.03)',
                    border: theme === 'light' ? '1px solid #cbd5e1' : '1px solid rgba(255,255,255,0.08)',
                    color: theme === 'light' ? '#475569' : '#94a3b8',
                    padding: '5px 12px',
                    borderRadius: '5px',
                    fontSize: '11px',
                    cursor: 'pointer'
                  }}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleCreateEdgeSubmit}
                  style={{
                    background: '#a855f7',
                    border: 'none',
                    color: '#ffffff',
                    padding: '5px 12px',
                    borderRadius: '5px',
                    fontSize: '11px',
                    cursor: 'pointer',
                    fontWeight: '600'
                  }}
                >
                  Connect
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Local Delete Toast */}
        {deleteToast && (
          <div style={{
            position: 'absolute', bottom: '16px', right: '16px', zIndex: 1000,
            background: 'rgba(16,185,129,0.15)', border: '1px solid rgba(16,185,129,0.35)',
            color: '#10b981', padding: '8px 14px', borderRadius: '6px', fontSize: '11px',
            fontWeight: '500', backdropFilter: 'blur(8px)',
            display: 'flex', alignItems: 'center', gap: '6px',
          }}>
            <CheckCircle size={12} />
            {deleteToast}
          </div>
        )}
      </div>

      {/* Legend */}
      <div style={{
        padding: '8px 16px',
        borderTop: theme === 'light' ? '1px solid #cbd5e1' : '1px solid rgba(255,255,255,0.04)',
        display: 'flex',
        flexWrap: 'wrap',
        gap: '16px',
        background: theme === 'light' ? '#f8fafc' : 'rgba(0,0,0,0.15)',
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
export default function MetadataRegistry({ onLogout, adminActiveTab, setAdminActiveTab, theme, toggleTheme }) {
  const [stats, setStats] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [deletingId, setDeletingId] = useState(null);
  const [clearingGraph, setClearingGraph] = useState(false);
  const [graphRefreshKey, setGraphRefreshKey] = useState(0);
  const [deleteToast, setDeleteToast] = useState(null);
  const [confirmModal, setConfirmModal] = useState(null); // Custom confirmation modal state

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

  const executeDelete = async (id, name) => {
    console.log("[DELETE] executeDelete triggered for:", { id, name });
    setDeletingId(id);
    try {
      const response = await fetch(`/api/v1/onboard/${id}`, { method: 'DELETE' });
      console.log("[DELETE] API response status:", response.status);
      if (!response.ok) {
        const errText = await response.text();
        throw new Error(errText || 'Delete request failed');
      }
      // Refresh both the stats table and the knowledge graph
      console.log("[DELETE] Deletion successful, refreshing stats...");
      await fetchStats();
      setGraphRefreshKey(k => k + 1);
      setDeleteToast(`"${name}" removed successfully.`);
      setTimeout(() => setDeleteToast(null), 3500);
    } catch (error) {
      console.error('[DELETE] Failed to delete database:', error);
      alert(`Delete failed: ${error.message}`);
    } finally {
      setDeletingId(null);
    }
  };

  const handleDelete = (id, name) => {
    setConfirmModal({ type: 'delete', id, name });
  };

  const executeClearAll = async () => {
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

  const handleClearAll = () => {
    setConfirmModal({ type: 'clearAll' });
  };

  return (
    <div className={`ace-onboarding-wrapper ${theme}-theme`} style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>

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
        borderBottom: theme === 'light' ? '1px solid #cbd5e1' : '1px solid rgba(255,255,255,0.04)',
      }}>
        {/* Total Databases */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: '14px',
          background: theme === 'light' ? '#ffffff' : 'rgba(20,25,35,0.6)',
          border: theme === 'light' ? '1px solid #cbd5e1' : '1px solid rgba(255,255,255,0.05)',
          borderRadius: '10px', padding: '14px 18px',
          boxShadow: theme === 'light' ? '0 1px 3px rgba(0,0,0,0.05)' : 'none',
        }}>
          <div style={{ width: '40px', height: '40px', borderRadius: '9px', background: 'rgba(168,85,247,0.12)', color: '#a855f7', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
            <Database size={20} />
          </div>
          <div>
            <p style={{ margin: 0, fontSize: '11px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: '600' }}>Total Databases</p>
            <h3 style={{ margin: '3px 0 0', fontSize: '26px', color: theme === 'light' ? '#0f172a' : '#ffffff', fontWeight: '700', lineHeight: 1 }}>{stats?.total_databases ?? 0}</h3>
          </div>
        </div>

        {/* Entities Extracted */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: '14px',
          background: theme === 'light' ? '#ffffff' : 'rgba(20,25,35,0.6)',
          border: theme === 'light' ? '1px solid #cbd5e1' : '1px solid rgba(255,255,255,0.05)',
          borderRadius: '10px', padding: '14px 18px',
          boxShadow: theme === 'light' ? '0 1px 3px rgba(0,0,0,0.05)' : 'none',
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
          background: theme === 'light' ? '#ffffff' : 'rgba(20,25,35,0.6)',
          border: theme === 'light' ? '1px solid #cbd5e1' : '1px solid rgba(255,255,255,0.05)',
          borderRadius: '10px', padding: '14px 18px',
          boxShadow: theme === 'light' ? '0 1px 3px rgba(0,0,0,0.05)' : 'none',
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
          background: theme === 'light' ? '#f1f5f9' : 'rgba(255,255,255,0.04)',
          position: 'relative'
        }}
      >

        {/* LEFT: Registered Databases Table */}
        <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden', background: theme === 'light' ? '#ffffff' : 'rgba(10,14,20,0.95)' }}>
          {/* Panel Header */}
          <div style={{
            padding: '14px 18px',
            borderBottom: theme === 'light' ? '1px solid #cbd5e1' : '1px solid rgba(255,255,255,0.05)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            background: theme === 'light' ? '#f8fafc' : 'rgba(0,0,0,0.2)', flexShrink: 0,
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
                  background: theme === 'light' ? '#ffffff' : 'rgba(255,255,255,0.03)',
                  border: theme === 'light' ? '1px solid #cbd5e1' : '1px solid rgba(255,255,255,0.08)',
                  color: theme === 'light' ? '#475569' : '#94a3b8', padding: '5px 10px', borderRadius: '6px',
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
                  <tr style={{
                    background: theme === 'light' ? '#f1f5f9' : 'rgba(0,0,0,0.25)',
                    color: theme === 'light' ? '#475569' : '#64748b',
                    borderBottom: theme === 'light' ? '1px solid #cbd5e1' : '1px solid rgba(255,255,255,0.05)',
                    position: 'sticky', top: 0, zIndex: 1
                  }}>
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
                        borderBottom: theme === 'light' ? '1px solid #cbd5e1' : '1px solid rgba(255,255,255,0.03)',
                        background: idx % 2 === 0 ? 'transparent' : (theme === 'light' ? '#f8fafc' : 'rgba(255,255,255,0.01)'),
                        transition: 'background 0.15s',
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.background = theme === 'light' ? 'rgba(168,85,247,0.08)' : 'rgba(168,85,247,0.04)'; }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = idx % 2 === 0 ? 'transparent' : (theme === 'light' ? '#f8fafc' : 'rgba(255,255,255,0.01)'); }}
                    >
                      <td style={{ padding: '13px 16px', color: theme === 'light' ? '#0f172a' : '#ffffff', fontWeight: '500' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <Database size={14} style={{ color: '#a855f7', flexShrink: 0 }} />
                          <span>{db.name}</span>
                        </div>
                      </td>
                      <td style={{ padding: '13px 16px', fontFamily: 'monospace', color: theme === 'light' ? '#64748b' : '#475569', fontSize: '10px' }}>
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
                <Database size={42} style={{ color: theme === 'light' ? '#cbd5e1' : '#334155', opacity: 0.5 }} />
                <h3 style={{ margin: 0, color: theme === 'light' ? '#475569' : '#94a3b8', fontSize: '14px' }}>No Connected Databases</h3>
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
            background: isDragging ? '#a855f7' : (theme === 'light' ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.08)'),
            transition: 'background 0.2s',
            zIndex: 10,
            position: 'relative',
          }}
          onMouseEnter={(e) => { if (!isDragging) e.currentTarget.style.background = theme === 'light' ? 'rgba(0,0,0,0.15)' : 'rgba(168,85,247,0.5)'; }}
          onMouseLeave={(e) => { if (!isDragging) e.currentTarget.style.background = theme === 'light' ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.08)'; }}
        />

        {/* RIGHT: Knowledge Graph Panel */}
        <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden', background: theme === 'light' ? '#ffffff' : 'rgba(6,9,13,0.98)' }}>
          <ReactFlowProvider>
            <KnowledgeGraphPanel refreshKey={graphRefreshKey} theme={theme} />
          </ReactFlowProvider>
        </div>

      </div>

      {/* ── Custom Confirmation Modal ── */}
      {confirmModal && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0, 0, 0, 0.7)',
          backdropFilter: 'blur(5px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 99999,
        }}>
          <div style={{
            background: theme === 'light' ? '#ffffff' : '#111827',
            border: theme === 'light' ? '1px solid #e2e8f0' : '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: '12px',
            padding: '24px',
            width: '100%',
            maxWidth: '440px',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.3), 0 10px 10px -5px rgba(0, 0, 0, 0.2)',
            color: theme === 'light' ? '#1f2937' : '#f3f4f6',
            textAlign: 'left'
          }}>
            <div style={{ display: 'flex', gap: '16px', alignItems: 'flex-start' }}>
              <div style={{
                background: 'rgba(239, 68, 68, 0.1)',
                color: '#ef4444',
                padding: '10px',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0
              }}>
                <AlertTriangle size={24} />
              </div>
              <div style={{ flex: 1 }}>
                <h3 style={{
                  margin: '0 0 8px 0',
                  fontSize: '16px',
                  fontWeight: '600',
                  color: theme === 'light' ? '#111827' : '#ffffff'
                }}>
                  {confirmModal.type === 'delete' ? 'Delete Database Schema?' : 'Clear All Database Schemas?'}
                </h3>
                <p style={{
                  margin: 0,
                  fontSize: '13px',
                  lineHeight: '1.5',
                  color: theme === 'light' ? '#4b5563' : '#9ca3af'
                }}>
                  {confirmModal.type === 'delete' ? (
                    <>
                      Are you sure you want to delete the schema for <strong>"{confirmModal.name}"</strong>? This will permanently remove its metadata registry, Neo4j knowledge graph nodes, and Elasticsearch vector embeddings.
                    </>
                  ) : (
                    <>
                      Are you sure you want to clear <strong>ALL</strong> database schemas? This will permanently wipe all metadata, Neo4j graph nodes, and Elasticsearch vector indices.
                    </>
                  )}
                </p>
              </div>
            </div>

            <div style={{
              display: 'flex',
              justifyContent: 'flex-end',
              gap: '12px',
              marginTop: '24px'
            }}>
              <button
                type="button"
                onClick={() => setConfirmModal(null)}
                style={{
                  background: theme === 'light' ? '#f3f4f6' : 'rgba(255, 255, 255, 0.05)',
                  border: theme === 'light' ? '1px solid #d1d5db' : '1px solid rgba(255, 255, 255, 0.08)',
                  color: theme === 'light' ? '#374151' : '#d1d5db',
                  padding: '8px 16px',
                  borderRadius: '6px',
                  fontSize: '13px',
                  fontWeight: '500',
                  cursor: 'pointer',
                  transition: 'background 0.2s',
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = theme === 'light' ? '#e5e7eb' : 'rgba(255, 255, 255, 0.1)'; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = theme === 'light' ? '#f3f4f6' : 'rgba(255, 255, 255, 0.05)'; }}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={async () => {
                  const modal = confirmModal;
                  setConfirmModal(null);
                  if (modal.type === 'delete') {
                    await executeDelete(modal.id, modal.name);
                  } else if (modal.type === 'clearAll') {
                    await executeClearAll();
                  }
                }}
                style={{
                  background: '#ef4444',
                  border: 'none',
                  color: '#ffffff',
                  padding: '8px 16px',
                  borderRadius: '6px',
                  fontSize: '13px',
                  fontWeight: '500',
                  cursor: 'pointer',
                  transition: 'background 0.2s',
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = '#dc2626'; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = '#ef4444'; }}
              >
                {confirmModal.type === 'delete' ? 'Delete' : 'Wipe All'}
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
