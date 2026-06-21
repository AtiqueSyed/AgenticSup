import React, { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import ReactECharts from 'echarts-for-react'
import { AlertCircle } from 'lucide-react'

interface DatabaseMeta {
  id: string;
  name: string;
  status: string;
}

export default function QueryInterface() {
  const [question, setQuestion] = useState("")
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle")
  const [result, setResult] = useState<any>(null)
  const [databases, setDatabases] = useState<DatabaseMeta[]>([])
  const [errorMessage, setErrorMessage] = useState<string>("")

  useEffect(() => {
    fetch("http://localhost:8000/api/v1/stats")
      .then(res => res.json())
      .then(data => {
        if (data.databases && data.databases.length > 0) {
          setDatabases(data.databases);
        }
      })
      .catch(console.error)
  }, [])

  const handleAsk = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!question) return
    
    setStatus("loading")
    try {
      const response = await fetch("http://localhost:8000/api/v1/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ database_id: null, question })
      })
      
      const data = await response.json()
      
      if (!response.ok) {
        throw new Error(data.detail || "Query failed")
      }
      
      setResult(data)
      setStatus("success")
    } catch (err: any) {
      console.error(err)
      setErrorMessage(err.message || "An unexpected error occurred.")
      setStatus("error")
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      <div className="mb-6 flex justify-between items-end">
        <div>
          <h2 className="text-2xl font-semibold text-slate-900">Natural Language Query</h2>
          <p className="text-slate-500">Ask business questions directly against your onboarded databases.</p>
        </div>
        
        {databases.length > 0 && (
          <div className="w-64 text-right">
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800">
              Global Routing Active ({databases.length} DBs)
            </span>
          </div>
        )}
      </div>

      <div className="flex-1 bg-white border border-slate-200 rounded-xl shadow-sm flex flex-col overflow-hidden">
        {/* Chat History / Results Area */}
        <div className="flex-1 p-6 overflow-y-auto bg-slate-50">
          {status === "idle" && (
            <div className="h-full flex items-center justify-center text-slate-400">
              {databases.length === 0 ? "No databases onboarded yet. Please onboard a database first." : "Your generated SQL, answers, and charts will appear here."}
            </div>
          )}
          {status === "loading" && (
            <div className="h-full flex items-center justify-center text-slate-500 animate-pulse">
              Agent is analyzing schema and generating SQL...
            </div>
          )}
          {status === "error" && (
            <div className="h-full flex flex-col items-center justify-center text-rose-500 max-w-lg mx-auto text-center">
              <AlertCircle className="w-10 h-10 mb-4 text-rose-400" />
              <h3 className="text-lg font-medium">Query Failed</h3>
              <p className="mt-2 text-sm text-rose-400 bg-rose-50 p-4 rounded-lg border border-rose-100">{errorMessage}</p>
            </div>
          )}
          {status === "success" && result && (
            <div className="space-y-6">
              <div className="bg-blue-50 border border-blue-100 p-4 rounded-lg">
                <h4 className="text-xs font-semibold text-blue-800 uppercase tracking-wider mb-2">Synthesized Answer</h4>
                <p className="text-slate-800">{result.answer || "No text answer generated."}</p>
              </div>
              
              {result.database_id && (
                <div className="bg-emerald-50 border border-emerald-100 p-4 rounded-lg">
                  <h4 className="text-xs font-semibold text-emerald-800 uppercase tracking-wider mb-2">Autonomously Routed To</h4>
                  <p className="text-slate-800 font-mono text-sm">{result.database_name || result.database_id}</p>
                </div>
              )}
              
              {result.sql_used && (
                <div className="bg-slate-900 rounded-lg p-4">
                  <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Generated SQL</h4>
                  <pre className="text-emerald-400 text-sm overflow-x-auto"><code>{result.sql_used}</code></pre>
                </div>
              )}

              {result.visualizations && result.visualizations.spec && (
                 <div className="bg-white border border-slate-200 rounded-lg p-4">
                    <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-4">Recommended Visualization</h4>
                    <ReactECharts option={result.visualizations.spec} style={{ height: '400px', width: '100%' }} />
                 </div>
              )}
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="p-4 bg-white border-t border-slate-200">
          <form onSubmit={handleAsk} className="flex gap-4">
            <Input 
              value={question}
              onChange={e => setQuestion(e.target.value)}
              placeholder="e.g., Show me the top 10 regions by transaction volume..." 
              className="flex-1 shadow-sm"
              disabled={databases.length === 0}
            />
            <Button type="submit" disabled={status === "loading" || !question || databases.length === 0}>Ask Database</Button>
          </form>
        </div>
      </div>
    </div>
  )
}
