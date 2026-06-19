import React, { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

export default function DatabaseOnboarding() {
  const [connectionString, setConnectionString] = useState("oracle+oracledb_async://agenticsupervisor_developer:agenticsupervisor@host.docker.internal:1521/?service_name=XEPDB1")
  const [dbName, setDbName] = useState("")
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle")

  const handleOnboard = async (e: React.FormEvent) => {
    e.preventDefault()
    setStatus("loading")
    try {
      const response = await fetch("http://localhost:8000/api/v1/onboard", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ connection_string: connectionString, database_name: dbName })
      })
      if (!response.ok) throw new Error("Failed to start onboarding")
      setStatus("success")
    } catch (err) {
      console.error(err)
      setStatus("error")
    }
  }

  return (
    <div className="max-w-2xl mx-auto mt-8">
      <div className="bg-white p-8 rounded-xl border border-slate-200 shadow-sm">
        <h2 className="text-2xl font-semibold text-slate-900 mb-2">Onboard New Database</h2>
        <p className="text-slate-500 mb-6">Connect a new database to introspect schemas and build the knowledge graph.</p>

        <form onSubmit={handleOnboard} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Database Name (Alias)</label>
            <Input 
              placeholder="e.g., core_banking_db" 
              value={dbName} 
              onChange={e => setDbName(e.target.value)} 
              required 
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Connection String</label>
            <Input 
              type="password"
              placeholder="oracle+oracledb_async://user:pass@host:port/service" 
              value={connectionString} 
              onChange={e => setConnectionString(e.target.value)} 
              required 
            />
          </div>
          
          <div className="pt-4">
            <Button type="submit" disabled={status === "loading"} className="w-full">
              {status === "loading" ? "Initializing Agentic Workflow..." : "Start Onboarding Workflow"}
            </Button>
          </div>
        </form>

        {status === "success" && (
          <div className="mt-6 p-4 bg-emerald-50 border border-emerald-200 rounded-md text-emerald-800 text-sm">
            <p className="font-semibold">Workflow Started Successfully!</p>
            <p>The AI agent is now introspecting the database, generating semantic descriptions, and building the Neo4j Knowledge Graph. This may take several minutes.</p>
          </div>
        )}
      </div>
    </div>
  )
}
