import { useEffect, useCallback } from 'react';
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
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  useEffect(() => {
    const fetchGraph = async () => {
      try {
        const response = await fetch("http://localhost:8000/api/v1/graph");
        const data = await response.json();
        
        // Simple layout: space out nodes so they aren't all at 0,0
        const spacedNodes = data.nodes.map((node: any, index: number) => ({
          ...node,
          position: { 
            x: (index % 5) * 200, 
            y: Math.floor(index / 5) * 100 
          }
        }));

        setNodes(spacedNodes);
        setEdges(data.edges);
      } catch (err) {
        console.error("Failed to fetch graph:", err);
      }
    };
    fetchGraph();
  }, [setNodes, setEdges]);

  const onConnect = useCallback(
    (params: Edge | Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges],
  );

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      <div className="mb-6">
        <h2 className="text-2xl font-semibold text-slate-900">Knowledge Graph Explorer</h2>
        <p className="text-slate-500">Visualize entities and relationships natively sourced from Neo4j.</p>
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
