import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
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
import { palette, radius, space, fontSize } from '../theme';

/* ─────────────────────────────────────────────────────────
   Custom ReactFlow node styles — one factory driven by the
   four --graph-* tokens instead of four hand-tuned gradients.
   ───────────────────────────────────────────────────────── */
const NODE_KIND_TOKEN = {
  Database: 'graphDb',
  Table: 'graphTable',
  Column: 'graphColumn',
  Entity: 'graphEntity',
};

function buildNodeStyle(kind, c) {
  const hue = c[NODE_KIND_TOKEN[kind]];
  const isDb = kind === 'Database';
  return {
    background: `color-mix(in srgb, ${hue} 12%, ${c.surface1})`,
    border: `1px solid ${hue}`,
    borderRadius: radius.md,
    color: c.text,
    fontSize: isDb ? fontSize[2] : fontSize[1],
    fontWeight: isDb ? '600' : '500',
    padding: isDb ? `${space[2]} ${space[4]}` : `${space[2]} ${space[3]}`,
    textAlign: 'center',
    minWidth: isDb ? '90px' : '72px',
    boxShadow: c.e1,
  };
}

const getRfNodeStyles = (theme) => {
  const c = palette(theme);
  return {
    Database: buildNodeStyle('Database', c),
    Entity: buildNodeStyle('Entity', c),
    Table: buildNodeStyle('Table', c),
    Column: buildNodeStyle('Column', c),
  };
};

/* Edge visual (stroke/label/marker) — single source used by every place
   that (re)styles edges: initial load, theme change, and manual creation. */
function buildEdgeVisual(edge, c) {
  const stroke = edge.animated ? c.graphEdgeActive : c.graphEdge;
  return {
    style: { stroke, strokeWidth: 1.5 },
    labelStyle: { fill: c.textSecondary, fontSize: 9 },
    labelBgStyle: { fill: c.surface1, fillOpacity: 0.9 },
    markerEnd: { type: 'arrowclosed', color: stroke },
  };
}

const NODE_BADGE_CLASS = {
  Database: 'kg-badge--database',
  Table: 'kg-badge--table',
  Column: 'kg-badge--column',
};

/* ─────────────────────────────────────────────────────────
   Knowledge Graph Panel
   ───────────────────────────────────────────────────────── */
function KnowledgeGraphPanel({ refreshKey, theme }) {
  const c = useMemo(() => palette(theme), [theme]);
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

    // Highlight node temporarily — a single calm accent ring, no glow/scale.
    setNodes((nds) => nds.map((n) => {
      if (n.id === node.id) {
        return {
          ...n,
          selected: true,
          style: {
            ...n.style,
            boxShadow: `0 0 0 3px ${c.accentRing}`,
            transition: 'box-shadow 0.2s ease-in-out'
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
              transition: 'box-shadow 0.3s ease-out'
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

      const newEdgeBase = {
        id: `${source}-${target}-${type}`,
        source,
        target,
        label: type,
        animated: type !== 'CONTAINS',
      };
      const newEdge = { ...newEdgeBase, ...buildEdgeVisual(newEdgeBase, c) };

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
      ...buildEdgeVisual(edge, c),
    })));
  }, [theme, c, setNodes, setEdges]);

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
        ...buildEdgeVisual(e, c),
      }))
    );
  }, [rawGraphData, showDatabases, showTables, showColumns, setNodes, setEdges, theme, c]);

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
      <div className="panel-titlebar">
        <span className="panel-titlebar-dots" aria-hidden="true"><i /><i /><i /></span>
        <span className="panel-titlebar-crumb">Registry / Knowledge Graph</span>
        <span className="panel-titlebar-status">{editMode ? 'Editing' : 'Ready'}</span>
      </div>
      <div className="kg-panel-header">

        {/* Search Box */}
        <div ref={dropdownRef} className="kg-search">
          <div className="kg-search-input-wrap">
            <Search size={12} className="kg-search-icon" />
            <input
              type="text"
              className="kg-search-input"
              value={searchQuery}
              onChange={handleSearchChange}
              onFocus={() => { if (searchResults.length > 0) setShowDropdown(true); }}
              placeholder="Search graph nodes..."
              onKeyDown={(e) => {
                if (e.key === 'Enter' && searchResults.length > 0) {
                  handleSelectNode(searchResults[0]);
                }
              }}
            />
          </div>

          {/* Dropdown Suggestions */}
          {showDropdown && searchResults.length > 0 && (
            <div className="kg-search-dropdown">
              {searchResults.map((node) => {
                const labelText = node.data?.label || '';
                const type = labelText.match(/^\[(.*?)\]/)?.[1] || 'Node';
                const name = labelText.replace(/^\[.*?\]\n/, '');
                const badgeClass = NODE_BADGE_CLASS[type] || 'kg-badge--entity';

                return (
                  <div
                    key={node.id}
                    className="kg-search-result"
                    onClick={() => handleSelectNode(node)}
                  >
                    <span className="kg-search-result-name">
                      {name || node.id}
                    </span>
                    <span className={`kg-badge ${badgeClass}`}>
                      {type}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="kg-toolbar">
          {/* Toggle DB Nodes */}
          <button
            type="button"
            className={`kg-toggle-btn kg-toggle-btn--db ${showDatabases ? 'active' : ''}`}
            onClick={() => setShowDatabases(!showDatabases)}
            title={showDatabases ? 'Hide DB nodes' : 'Show DB nodes'}
          >
            {showDatabases ? <Eye size={12} /> : <EyeOff size={12} />}
            <span>DB Lineage</span>
          </button>

          {/* Toggle Table Nodes */}
          <button
            type="button"
            className={`kg-toggle-btn kg-toggle-btn--table ${showTables ? 'active' : ''}`}
            onClick={() => setShowTables(!showTables)}
            title={showTables ? 'Hide Table nodes' : 'Show Table nodes'}
          >
            {showTables ? <Eye size={12} /> : <EyeOff size={12} />}
            <span>Tables</span>
          </button>

          {/* Toggle Column Nodes */}
          <button
            type="button"
            className={`kg-toggle-btn kg-toggle-btn--column ${showColumns ? 'active' : ''}`}
            onClick={() => setShowColumns(!showColumns)}
            title={showColumns ? 'Hide Column nodes' : 'Show Column nodes'}
          >
            {showColumns ? <Eye size={12} /> : <EyeOff size={12} />}
            <span>Columns</span>
          </button>

          {/* Refresh Graph */}
          <button
            type="button"
            className="kg-toggle-btn"
            onClick={fetchGraph}
            disabled={graphLoading}
          >
            <RefreshCw size={11} className={graphLoading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>

          {/* Edit Mode Toggle */}
          <button
            type="button"
            className={`kg-toggle-btn kg-toggle-btn--edit ${editMode ? 'active' : ''}`}
            onClick={() => {
              setEditMode(!editMode);
              if (editMode) {
                setNodes((nds) => nds.map((n) => ({ ...n, selected: false })));
                setEdges((eds) => eds.map((e) => ({ ...e, selected: false })));
              }
            }}
          >
            <span>{editMode ? 'Edit Mode ON' : 'Edit Mode OFF'}</span>
          </button>
        </div>
      </div>

      {/* ReactFlow Canvas */}
      <div ref={reactFlowWrapper} className="kg-canvas-wrap">
        {graphLoading ? (
          <div className="kg-canvas-loading">
            <Loader2 size={28} className="animate-spin graph-loader-icon" />
            <span>Loading knowledge graph from Neo4j...</span>
          </div>
        ) : nodes.length === 0 ? (
          <div className="kg-canvas-empty">
            <GitBranch size={40} className="idle-network-icon" />
            <h3 className="kg-canvas-empty-title">No Graph Data</h3>
            <p className="kg-canvas-empty-desc">
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
                background: c.surface1,
                border: `1px solid ${c.border}`,
                borderRadius: radius.md,
                color: c.text,
              }}
            />
            <MiniMap
              style={{
                background: c.surface1,
                border: `1px solid ${c.border}`,
                borderRadius: radius.md,
              }}
              nodeColor={(n) => {
                const labelText = n.data?.label || '';
                if (labelText.startsWith('[Database]') || n.type === 'input') return c.graphDb;
                if (labelText.startsWith('[Table]')) return c.graphTable;
                if (labelText.startsWith('[Column]')) return c.graphColumn;
                return c.graphEntity;
              }}
              maskColor={c.scrim}
            />
            <Background color={c.border} gap={22} size={1.4} />
          </ReactFlow>
        )}

        {/* Drag-and-Drop Side Palette */}
        {editMode && (
          <div className="kg-palette">
            <h4 className="kg-palette-title">Palette</h4>

            <div
              draggable
              onDragStart={(e) => onDragStart(e, 'Database')}
              className="kg-palette-item kg-palette-item--database"
            >
              + Database
            </div>

            <div
              draggable
              onDragStart={(e) => onDragStart(e, 'Table')}
              className="kg-palette-item kg-palette-item--table"
            >
              + Table
            </div>

            <div
              draggable
              onDragStart={(e) => onDragStart(e, 'Column')}
              className="kg-palette-item kg-palette-item--column"
            >
              + Column
            </div>

            <div
              draggable
              onDragStart={(e) => onDragStart(e, 'Entity')}
              className="kg-palette-item kg-palette-item--entity"
            >
              + Entity
            </div>

            <hr className="kg-palette-divider" />

            <button
              type="button"
              disabled={!(nodes.some(n => n.selected) || edges.some(e => e.selected))}
              onClick={handleDeleteSelected}
              className="kg-palette-delete-btn"
            >
              <Trash2 size={10} />
              <span>Delete Selected</span>
            </button>
          </div>
        )}

        {/* Node Create Modal */}
        {nodeCreateModal && (
          <div className="admin-modal-overlay">
            <div className="admin-modal">
              <h4 className="admin-modal-title">
                Create Custom {nodeCreateModal.type}
              </h4>

              <div className="admin-modal-fields">
                <div>
                  <label className="admin-modal-field-label">Name</label>
                  <input
                    type="text"
                    className="admin-modal-input"
                    value={newNodeName}
                    onChange={(e) => setNewNodeName(e.target.value)}
                    placeholder="Enter name..."
                  />
                </div>

                <div>
                  <label className="admin-modal-field-label">Description</label>
                  <textarea
                    className="admin-modal-textarea"
                    value={newNodeDesc}
                    onChange={(e) => setNewNodeDesc(e.target.value)}
                    placeholder="Enter description..."
                    rows={3}
                  />
                </div>
              </div>

              <div className="admin-modal-actions">
                <button
                  type="button"
                  className="admin-modal-btn admin-modal-btn--secondary"
                  onClick={() => { setNodeCreateModal(null); setNewNodeName(''); setNewNodeDesc(''); }}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="admin-modal-btn admin-modal-btn--primary"
                  onClick={handleCreateNodeSubmit}
                  disabled={!newNodeName.trim()}
                >
                  Create
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Edge Create Modal */}
        {edgeCreateModal && (
          <div className="admin-modal-overlay">
            <div className="admin-modal">
              <h4 className="admin-modal-title">
                Add Relationship
              </h4>

              <div className="admin-modal-fields">
                <div>
                  <label className="admin-modal-field-label">Relationship Type</label>
                  <select
                    className="admin-modal-select"
                    value={newEdgeType}
                    onChange={(e) => setNewEdgeType(e.target.value)}
                  >
                    <option value="RELATES_TO">RELATES_TO</option>
                    <option value="CONTAINS">CONTAINS</option>
                    <option value="HAS_TABLE">HAS_TABLE</option>
                    <option value="HAS_COLUMN">HAS_COLUMN</option>
                    <option value="MAPS_TO">MAPS_TO</option>
                  </select>
                </div>
              </div>

              <div className="admin-modal-actions">
                <button
                  type="button"
                  className="admin-modal-btn admin-modal-btn--secondary"
                  onClick={() => { setEdgeCreateModal(null); setNewEdgeType('RELATES_TO'); }}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="admin-modal-btn admin-modal-btn--primary"
                  onClick={handleCreateEdgeSubmit}
                >
                  Connect
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Local Delete Toast */}
        {deleteToast && (
          <div className="admin-toast admin-toast--panel">
            <CheckCircle size={12} />
            {deleteToast}
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="kg-legend">
        <div className="kg-legend-item">
          <span className="kg-legend-swatch kg-legend-swatch--database" />
          Database
        </div>
        <div className="kg-legend-item">
          <span className="kg-legend-swatch kg-legend-swatch--table" />
          Table
        </div>
        <div className="kg-legend-item">
          <span className="kg-legend-swatch kg-legend-swatch--column" />
          Column
        </div>
        <div className="kg-legend-item">
          <span className="kg-legend-swatch kg-legend-swatch--entity" />
          Abstract Entity
        </div>
        <div className="kg-legend-item">
          <span className="kg-legend-line kg-legend-line--contains" />
          CONTAINS
        </div>
        <div className="kg-legend-item">
          <span className="kg-legend-line kg-legend-line--related" />
          RELATED_TO
        </div>
      </div>

      <div className="fig-caption">
        <span>Fig. 01 — {nodeCount} nodes, {edgeCount} edges</span>
        <span className="fig-caption-right">Neo4j &middot; live</span>
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
    <div className={`ace-onboarding-wrapper ${theme}-theme`} style={{ height: '100vh', overflow: 'hidden' }}>

      {/* ── Delete success toast ── */}
      {deleteToast && (
        <div className="admin-toast admin-toast--fixed">
          <CheckCircle size={14} />
          {deleteToast}
        </div>
      )}

      {/* ── Shared Admin Header ── */}
      <header className="ace-dashboard-header flex-center">
        <div className="header-logo-section flex-center">
          <div className="header-logo-icon flex-center">
            <Layers size={18} />
          </div>
          <div>
            <h1 className="header-title">Metadata Registry</h1>
            <p className="header-subtitle">Onboarded schemas and knowledge graph</p>
          </div>
        </div>

        <nav className="header-tab-nav flex-center">
          <button
            type="button"
            className="nav-tab-item flex-center"
            onClick={() => setAdminActiveTab('onboarding')}
          >
            <Server size={14} className="tab-icon" />
            <span>ACE Onboarding</span>
          </button>

          <button
            type="button"
            className="nav-tab-item active flex-center"
          >
            <Database size={14} className="tab-icon" />
            <span>Metadata Registry</span>
          </button>

          <button
            type="button"
            className="nav-tab-item flex-center"
            onClick={() => setAdminActiveTab('query')}
          >
            <BookOpen size={14} className="tab-icon" />
            <span>Query Execution</span>
          </button>
        </nav>

        <div className="header-profile-section flex-center">
          <div className="profile-badge flex-center">
            <div className="profile-avatar flex-center">C</div>
            <span className="profile-name">Chirag Admin</span>
          </div>
          <button
            type="button"
            className="theme-toggle-btn-admin flex-center"
            onClick={toggleTheme}
            title={theme === 'dark' ? "Switch to Light Mode" : "Switch to Dark Mode"}
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
      <div className="registry-stats-grid">
        {/* Total Databases */}
        <div className="stat-card">
          <h3 className="stat-value">{stats?.total_databases ?? 0}</h3>
          <p className="stat-label"><Database size={13} /> Total Databases</p>
        </div>

        {/* Entities Extracted */}
        <div className="stat-card">
          <h3 className="stat-value">{stats?.entities_identified ?? 0}</h3>
          <p className="stat-label"><Layers size={13} /> Abstract Entities</p>
        </div>

        {/* Service Health */}
        <div className="stat-card">
          <h3 className="stat-value stat-value--service">Active (Neo4j / ES)</h3>
          <p className="stat-label"><Activity size={13} /> Service Layer</p>
        </div>
      </div>

      {/* ── Split Pane: Registry Table (left) | Knowledge Graph (right) ── */}
      <div
        ref={containerRef}
        className="registry-split"
        style={{ gridTemplateColumns: `${leftWidth}px 4px 1fr` }}
      >

        {/* LEFT: Registered Databases Table */}
        <div className="registry-left">
          {/* Panel Header */}
          <div className="registry-panel-header">
            <div className="kg-panel-heading">
              <h2 className="panel-title">Registered Databases</h2>
            </div>
            <div className="registry-toolbar">
              <button
                type="button"
                className="registry-toolbar-btn"
                onClick={fetchStats}
                disabled={isLoading}
              >
                <RefreshCw size={11} className={isLoading ? 'animate-spin' : ''} />
                <span>Refresh</span>
              </button>
              <button
                type="button"
                className="registry-toolbar-btn registry-toolbar-btn--danger"
                onClick={handleClearAll}
                disabled={clearingGraph}
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
          <div className="registry-table-scroll">
            {isLoading ? (
              <div className="registry-empty-state">
                <Loader2 size={28} className="animate-spin graph-loader-icon" />
                <span>Loading databases...</span>
              </div>
            ) : stats?.databases && stats.databases.length > 0 ? (
              <table className="registry-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>ID Hash</th>
                    <th>Status</th>
                    <th className="align-right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.databases.map((db) => (
                    <tr key={db.id}>
                      <td>
                        <div className="registry-name-cell">
                          <Database size={14} className="registry-name-icon" />
                          <span>{db.name}</span>
                        </div>
                      </td>
                      <td className="registry-id-cell">
                        {db.id.slice(0, 12)}…
                      </td>
                      <td>
                        {db.status?.startsWith('failed') ? (
                          <span className="status-pill status-pill--failed">
                            <XCircle size={11} /><span>Failed</span>
                          </span>
                        ) : db.status === 'running' ? (
                          <span className="status-pill status-pill--running">
                            <Loader2 size={11} className="animate-spin" /><span>Running</span>
                          </span>
                        ) : (
                          <span className="status-pill status-pill--active">
                            <CheckCircle size={11} /><span>Active</span>
                          </span>
                        )}
                      </td>
                      <td className="align-right">
                        <button
                          type="button"
                          className="registry-delete-btn"
                          onClick={() => handleDelete(db.id, db.name)}
                          disabled={deletingId === db.id}
                          title="Delete Schema"
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
              <div className="registry-empty-state">
                <Database size={42} className="registry-empty-icon" />
                <h3 className="registry-empty-title">No Connected Databases</h3>
                <p className="registry-empty-desc">
                  Go to the Onboarding tab to configure and onboard database schemas.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Divider / Splitter bar */}
        <div
          onMouseDown={handleMouseDown}
          className={`split-divider ${isDragging ? 'dragging' : ''}`}
        />

        {/* RIGHT: Knowledge Graph Panel */}
        <div className="registry-right">
          <ReactFlowProvider>
            <KnowledgeGraphPanel refreshKey={graphRefreshKey} theme={theme} />
          </ReactFlowProvider>
        </div>

      </div>

      {/* ── Custom Confirmation Modal ── */}
      {confirmModal && (
        <div className="confirm-modal-overlay">
          <div className="confirm-modal">
            <div className="confirm-modal-body">
              <div className="confirm-modal-icon">
                <AlertTriangle size={24} />
              </div>
              <div style={{ flex: 1 }}>
                <h3 className="confirm-modal-title">
                  {confirmModal.type === 'delete' ? 'Delete Database Schema?' : 'Clear All Database Schemas?'}
                </h3>
                <p className="confirm-modal-desc">
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

            <div className="confirm-modal-actions">
              <button
                type="button"
                className="admin-modal-btn admin-modal-btn--secondary"
                onClick={() => setConfirmModal(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="admin-modal-btn admin-modal-btn--danger"
                onClick={async () => {
                  const modal = confirmModal;
                  setConfirmModal(null);
                  if (modal.type === 'delete') {
                    await executeDelete(modal.id, modal.name);
                  } else if (modal.type === 'clearAll') {
                    await executeClearAll();
                  }
                }}
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
