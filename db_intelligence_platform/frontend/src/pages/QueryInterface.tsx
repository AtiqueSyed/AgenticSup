import React, { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import ReactECharts from 'echarts-for-react'

export default function QueryInterface() {
  const [question, setQuestion] = useState("")
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle")
  const [result, setResult] = useState<any>(null)

  const handleAsk = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!question) return
    
    setStatus("loading")
    try {
      const response = await fetch("http://localhost:8000/api/v1/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ database_id: "selected-db-id", question })
      })
      if (!response.ok) throw new Error("Query failed")
      const data = await response.json()
      setResult(data)
      setStatus("success")
    } catch (err) {
      console.error(err)
      setStatus("error")
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      <div className="mb-6">
        <h2 className="text-2xl font-semibold text-slate-900">Natural Language Query</h2>
        <p className="text-slate-500">Ask business questions directly against your onboarded databases.</p>
      </div>

      <div className="flex-1 bg-white border border-slate-200 rounded-xl shadow-sm flex flex-col overflow-hidden">
        {/* Chat History / Results Area */}
        <div className="flex-1 p-6 overflow-y-auto bg-slate-50">
          {status === "idle" && (
            <div className="h-full flex items-center justify-center text-slate-400">
              Your generated SQL, answers, and charts will appear here.
            </div>
          )}
          {status === "loading" && (
            <div className="h-full flex items-center justify-center text-slate-500 animate-pulse">
              Agent is analyzing schema and generating SQL...
            </div>
          )}
          {status === "success" && result && (
            <div className="space-y-6">
              <div className="bg-blue-50 border border-blue-100 p-4 rounded-lg">
                <h4 className="text-xs font-semibold text-blue-800 uppercase tracking-wider mb-2">Synthesized Answer</h4>
                <p className="text-slate-800">{result.answer || "No text answer generated."}</p>
              </div>
              
              {result.sql && (
                <div className="bg-slate-900 rounded-lg p-4">
                  <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Generated SQL</h4>
                  <pre className="text-emerald-400 text-sm overflow-x-auto"><code>{result.sql}</code></pre>
                </div>
              )}

              {result.chart && result.chart.spec && (
                 <div className="bg-white border border-slate-200 rounded-lg p-4">
                    <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-4">Recommended Visualization</h4>
                    <ReactECharts option={result.chart.spec} style={{ height: '400px', width: '100%' }} />
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
            />
            <Button type="submit" disabled={status === "loading" || !question}>Ask Database</Button>
          </form>
        </div>
      </div>
    </div>
  )
}
