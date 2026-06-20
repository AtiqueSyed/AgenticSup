import React, { useState, useEffect } from "react"
import { BrowserRouter, Routes, Route, Link } from "react-router-dom"
import { Button } from "@/components/ui/button"

function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-50 flex">
      {/* Sidebar Navigation */}
      <aside className="w-64 bg-white border-r border-slate-200 flex flex-col h-screen sticky top-0">
        <div className="p-6">
          <h1 className="text-xl font-bold text-slate-900 leading-tight">Agentic DB Platform</h1>
        </div>
        <nav className="flex-1 px-4 space-y-2">
          <Link to="/" className="block px-3 py-2 text-sm font-medium text-slate-700 rounded-md hover:bg-slate-100">Dashboard</Link>
          <Link to="/onboard" className="block px-3 py-2 text-sm font-medium text-slate-700 rounded-md hover:bg-slate-100">DB Onboarding</Link>
          <Link to="/query" className="block px-3 py-2 text-sm font-medium text-slate-700 rounded-md hover:bg-slate-100">Query Interface</Link>
          <Link to="/registry" className="block px-3 py-2 text-sm font-medium text-slate-700 rounded-md hover:bg-slate-100">Metadata Registry</Link>
          <Link to="/knowledge-graph" className="block px-3 py-2 text-sm font-medium text-slate-700 rounded-md hover:bg-slate-100">Knowledge Graph</Link>
        </nav>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 overflow-auto">
        <div className="p-8 max-w-7xl mx-auto">
          {children}
        </div>
      </main>
    </div>
  )
}

function Dashboard() {
  const [stats, setStats] = useState<{ total_databases: number, database_names?: string[], entities_identified: number, queries_today: number }>({ total_databases: 0, entities_identified: 0, queries_today: 0 })
  const [showDbNames, setShowDbNames] = useState(false)

  useEffect(() => {
    fetch("http://localhost:8000/api/v1/stats")
      .then(res => res.json())
      .then(data => setStats(data))
      .catch(console.error)
  }, [])

  return (
    <div>
      <h2 className="text-3xl font-semibold text-slate-900 mb-6">Welcome to Enterprise DB Intelligence</h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div 
          className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm cursor-pointer hover:shadow-md transition-all duration-200"
          onClick={() => setShowDbNames(!showDbNames)}
        >
          <h3 className="font-medium text-lg text-slate-900 flex justify-between items-center">
            Total Databases
            <span className="text-xs font-normal text-slate-400 bg-slate-100 px-2 py-1 rounded-full">Click to view</span>
          </h3>
          <p className="text-4xl font-light text-blue-600 mt-2">{stats.total_databases}</p>
          
          {showDbNames && stats.database_names && stats.database_names.length > 0 && (
            <div className="mt-4 pt-4 border-t border-slate-100">
              <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Onboarded Sources</h4>
              <ul className="space-y-1.5 max-h-32 overflow-y-auto pr-2">
                {stats.database_names.map((name, idx) => (
                  <li key={idx} className="text-sm text-slate-700 bg-slate-50 border border-slate-100 px-2.5 py-1.5 rounded-md truncate" title={name}>
                    {name}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
          <h3 className="font-medium text-lg text-slate-900">Entities Identified</h3>
          <p className="text-4xl font-light text-emerald-600 mt-2">{stats.entities_identified}</p>
        </div>
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
          <h3 className="font-medium text-lg text-slate-900">Queries Today</h3>
          <p className="text-4xl font-light text-violet-600 mt-2">{stats.queries_today}</p>
        </div>
      </div>
      <div className="mt-8 flex gap-4">
        <Link to="/onboard"><Button variant="default">Onboard New Database</Button></Link>
        <Link to="/query"><Button variant="outline">Ask a Question</Button></Link>
      </div>
    </div>
  )
}

import DatabaseOnboarding from "@/pages/DatabaseOnboarding"
import QueryInterface from "@/pages/QueryInterface"
import KnowledgeGraphExplorer from "@/pages/KnowledgeGraphExplorer"

// Placeholders for other pages
const PlaceholderPage = ({ title }: { title: string }) => (
  <div>
    <h2 className="text-2xl font-semibold text-slate-900 mb-4">{title}</h2>
    <p className="text-slate-600">This feature is currently under development.</p>
  </div>
)

function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/onboard" element={<DatabaseOnboarding />} />
          <Route path="/query" element={<QueryInterface />} />
          <Route path="/registry" element={<PlaceholderPage title="Metadata Registry" />} />
          <Route path="/knowledge-graph" element={<KnowledgeGraphExplorer />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}

export default App
