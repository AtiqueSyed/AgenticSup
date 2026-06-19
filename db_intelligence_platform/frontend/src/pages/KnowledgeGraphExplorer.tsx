import React, { useState, useCallback } from 'react';
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

const initialNodes = [
  { id: '1', position: { x: 250, y: 5 }, data: { label: 'Customers (Table)' } },
  { id: '2', position: { x: 100, y: 100 }, data: { label: 'Orders (Table)' } },
  { id: '3', position: { x: 400, y: 100 }, data: { label: 'Addresses (Table)' } },
];

const initialEdges = [
  { id: 'e1-2', source: '1', target: '2', label: '1:N (customer_id)' },
  { id: 'e1-3', source: '1', target: '3', label: '1:1 (address_id)' },
];

export default function KnowledgeGraphExplorer() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  const onConnect = useCallback(
    (params: Edge | Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges],
  );

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      <div className="mb-6">
        <h2 className="text-2xl font-semibold text-slate-900">Knowledge Graph Explorer</h2>
        <p className="text-slate-500">Visualize entities and relationships mapped by the AI during onboarding.</p>
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
