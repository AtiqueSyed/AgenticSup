import { useEffect, useCallback, useState, useRef } from 'react';
import ReactFlow, {
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  Edge
} from 'reactflow';
import 'reactflow/dist/style.css';

export default function KnowledgeGraphExplorer() {
  const [rawGraphData, setRawGraphData] = useState<{nodes: any[], edges: any[]}>({ nodes: [], edges: [] });
  const [showDatabases, setShowDatabases] = useState(true);

  const [nodes, setNodes, onNodesChangeCore] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  
  // Persistent memory of node positions, even if they are removed from the canvas
  const savedPositions = useRef(new Map<string, {x: number, y: number}>());

  const onNodesChange = useCallback((changes: any) => {
    onNodesChangeCore(changes);
    // Intercept position changes from dragging to keep an absolute record
    changes.forEach((c: any) => {
      if (c.type === 'position' && c.position) {
        savedPositions.current.set(c.id, c.position);
      }
    });
  }, [onNodesChangeCore]);

  useEffect(() => {
    const fetchGraph = async () => {
      try {
        const response = await fetch("http://localhost:8000/api/v1/graph");
        const data = await response.json();
        setRawGraphData(data);
      } catch (err) {
        console.error("Failed to fetch graph:", err);
      }
    };
    fetchGraph();
  }, []);

  useEffect(() => {
    let filteredNodes = rawGraphData.nodes;
    let filteredEdges = rawGraphData.edges;

    if (!showDatabases) {
      filteredNodes = filteredNodes.filter((n: any) => n.type !== "input");
      const dbNodeIds = new Set(rawGraphData.nodes.filter((n: any) => n.type === "input").map((n: any) => n.id));
      filteredEdges = filteredEdges.filter((e: any) => !dbNodeIds.has(e.source) && !dbNodeIds.has(e.target));
    }

    setNodes((currentNodes) => {
      // Sync any current screen positions into memory before updating
      currentNodes.forEach(n => savedPositions.current.set(n.id, n.position));
      
      return filteredNodes.map((node: any, index: number) => ({
        ...node,
        position: savedPositions.current.get(node.id) || { 
          x: (index % 5) * 200, 
          y: Math.floor(index / 5) * 100 
        }
      }));
    });

    setEdges(filteredEdges);
  }, [rawGraphData, showDatabases, setNodes, setEdges]);

  const onConnect = useCallback(
    (params: Edge | Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges],
  );

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      <div className="mb-6 flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-semibold text-slate-900">Knowledge Graph Explorer</h2>
          <p className="text-slate-500">Visualize entities and relationships natively sourced from Neo4j.</p>
        </div>
        <label className="flex items-center cursor-pointer bg-white p-2 px-3 rounded-lg border border-slate-200 shadow-sm hover:bg-slate-50 transition-colors">
          <div className="relative">
            <input 
              type="checkbox" 
              className="sr-only" 
              checked={showDatabases} 
              onChange={(e) => setShowDatabases(e.target.checked)} 
            />
            <div className={`block w-10 h-6 rounded-full transition-colors ${showDatabases ? 'bg-blue-600' : 'bg-slate-300'}`}></div>
            <div className={`dot absolute left-1 top-1 bg-white w-4 h-4 rounded-full transition-transform ${showDatabases ? 'transform translate-x-4' : ''}`}></div>
          </div>
          <div className="ml-3 text-sm font-medium text-slate-700">
            Show Database Lineage
          </div>
        </label>
      </div>
      <div className="flex-1 bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          fitView
        >
          <Controls />
          <MiniMap />
          <Background gap={12} size={1} />
        </ReactFlow>
      </div>
    </div>
  );
}
