// Mock Database Schema and Engine for Agentic NL2QL

export const databaseSchema = {
  bank_penalties: {
    description: "Contains details on monetary penalties imposed on commercial banks by the RBI for compliance failures.",
    columns: [
      { name: "id", type: "INTEGER", key: "PRIMARY KEY" },
      { name: "bank_name", type: "VARCHAR(100)", description: "Name of the commercial bank" },
      { name: "penalty_amount_cr", type: "DECIMAL(5,2)", description: "Monetary penalty amount in Crores INR" },
      { name: "violation", type: "TEXT", description: "Reason/nature of the regulatory violation" },
      { name: "action_date", type: "DATE", description: "Date of the penalty notification" },
      { name: "category", type: "VARCHAR(50)", description: "Broad category of compliance failure (e.g., KYC, Cyber Security, Deposits)" }
    ]
  },
  supervisory_evaluations: {
    description: "Supervisory performance appraisals, numerical grades, and assessment comments for RBI officers.",
    columns: [
      { name: "id", type: "INTEGER", key: "PRIMARY KEY" },
      { name: "officer_name", type: "VARCHAR(100)", description: "Name of the officer under review" },
      { name: "final_grade", type: "INTEGER", description: "Supervisory grade out of 10" },
      { name: "evaluation_date", type: "DATE", description: "Evaluation reporting date" },
      { name: "comments", type: "TEXT", description: "Reporting Officer's competency assessment comments" }
    ]
  },
  compliance_logs: {
    description: "Audit ratings, monitoring status, and cumulative violation counts for supervised banks in 2023.",
    columns: [
      { name: "id", type: "INTEGER", key: "PRIMARY KEY" },
      { name: "bank_name", type: "VARCHAR(100)", description: "Name of the bank" },
      { name: "audit_year", type: "INTEGER", description: "Calender year of inspection" },
      { name: "rating", type: "VARCHAR(50)", description: "Inspection rating (e.g., High Compliant, Satisfactory, Needs Improvement)" },
      { name: "status", type: "VARCHAR(50)", description: "Current regulatory status" },
      { name: "violations_count", type: "INTEGER", description: "Count of minor and major compliance violations logged" }
    ]
  }
};

export const initialDatabase = {
  bank_penalties: [
    { id: 1, bank_name: "State Bank of India (SBI)", penalty_amount_cr: 5.0, violation: "Failed to credit unauthorized electronic transactions (shadow reversal) to customer accounts within 10 days and compensate within 90 days. Also maintained current accounts in contravention of regulatory guidelines.", action_date: "2023-03-31", category: "Operations" },
    { id: 2, bank_name: "HDFC Bank", penalty_amount_cr: 1.9, violation: "Non-compliance with directives on interest rates on deposits and customer identification (KYC) compliance reviews.", action_date: "2023-11-20", category: "Compliance Audit" },
    { id: 3, bank_name: "ICICI Bank", penalty_amount_cr: 12.19, violation: "Failure to report cyber incidents, delays in reporting frauds, and running loan programs for directors without board clearances.", action_date: "2023-10-18", category: "Financial Discipline" },
    { id: 4, bank_name: "Bank of Baroda", penalty_amount_cr: 4.34, violation: "Deficiencies in regulatory compliance regarding current account operations and interest rates rules on saving funds.", action_date: "2023-12-07", category: "Operations" },
    { id: 5, bank_name: "Axis Bank", penalty_amount_cr: 0.9, violation: "Breach of KYC guidelines, failure to verify customer identities during high-value transfers, and anti-money laundering policy laxity.", action_date: "2023-06-15", category: "Compliance Audit" },
    { id: 6, bank_name: "Punjab National Bank", penalty_amount_cr: 0.72, violation: "Delay in reporting cyber-security breach incident on secondary treasury systems.", action_date: "2023-09-02", category: "Cyber Security" }
  ],
  supervisory_evaluations: [
    { 
      id: 1, 
      officer_name: "Tej", 
      final_grade: 10, 
      evaluation_date: "2023-03-31", 
      comments: "Encouraging and Leveraging Diversity: 'The officer has excellent team working skills.'\n\nImplementation and Execution Excellence: 'Demonstrated outstanding execution skills.'\n\nAbility to Analyze and Improve Systems and Procedures: 'Proven analytical and problem solving abilities.'\n\nDetailed Knowledge of Work Process Flow: 'Outstanding knowledge of work processes.'\n\nUnderstanding of General Administration Processes: 'Excellent understanding.'" 
    }
  ],
  compliance_logs: [
    { id: 1, bank_name: "State Bank of India (SBI)", audit_year: 2023, rating: "Satisfactory", status: "Active Monitoring", violations_count: 3 },
    { id: 2, bank_name: "HDFC Bank", audit_year: 2023, rating: "High Compliant", status: "Closed", violations_count: 1 },
    { id: 3, bank_name: "ICICI Bank", audit_year: 2023, rating: "Needs Improvement", status: "Under Review", violations_count: 5 },
    { id: 4, bank_name: "Axis Bank", audit_year: 2023, rating: "Satisfactory", status: "Active Monitoring", violations_count: 2 },
    { id: 5, bank_name: "Bank of Baroda", audit_year: 2023, rating: "Needs Improvement", status: "Under Review", violations_count: 4 }
  ]
};

// Global DB state holding dynamic user uploaded tables too
let currentDb = { ...initialDatabase };
let currentSchemas = { ...databaseSchema };

export const resetDatabase = () => {
  currentDb = { ...initialDatabase };
  currentSchemas = { ...databaseSchema };
};

// Register a new table dynamically from uploaded files (CSV/JSON parsing)
export const registerDynamicTable = (name, columns, data) => {
  const formattedTableName = name.toLowerCase().replace(/[^a-z0-9]/g, "_");
  
  currentSchemas[formattedTableName] = {
    description: `User uploaded knowledge base file: ${name}`,
    columns: columns.map(c => ({ name: c, type: "VARCHAR(255)", description: `Field ${c} from uploaded data` }))
  };

  currentDb[formattedTableName] = data;
  return formattedTableName;
};

export const getRegisteredSchemas = () => currentSchemas;

// Standard agentic reasoning trace
const getReasoningSteps = (table, query) => [
  { step: "Intent Identification", desc: `Analyzing NL input: "${query}". Detected request related to: ${table}.` },
  { step: "Schema Binding & Resolution", desc: `Inspecting tables: Selected [${table}]. Matching columns: ${Object.keys(currentDb[table]?.[0] || {}).join(", ")}.` },
  { step: "Syntax Compilation (NL2QL)", desc: `Synthesizing SQL dialect. Ensuring correct filters and aggregations.` },
  { step: "Execution & Validation", desc: `Executing compiled SQL query against active database node. 0 errors, fetching rows...` }
];

// Parser & Query execution mock engine
export const executeNL2QL = (naturalQuery) => {
  const q = naturalQuery.toLowerCase().trim();

  // Helper matching functions
  const matches = (words) => words.some(w => q.includes(w));

  // --- QUERY 1: SBI PENALTY DETAILS (Matches image 4 and 5) ---
  if (matches(["sbi", "state bank"]) && matches(["penalised", "penalty", "penalties", "issues"])) {
    const table = "bank_penalties";
    const sbiRecord = currentDb.bank_penalties.find(p => p.bank_name.includes("State Bank"));
    
    return {
      success: true,
      table,
      thoughts: getReasoningSteps(table, naturalQuery),
      sql: `SELECT violation, action_date FROM bank_penalties WHERE bank_name = 'State Bank of India (SBI)';`,
      columns: ["violation", "action_date"],
      rows: [
        { 
          violation: sbiRecord.violation, 
          action_date: sbiRecord.action_date 
        }
      ],
      chartData: null,
      answerText: `Based on the statutory inspection, the issues for which **State Bank of India (SBI)** has been penalised by the RBI in the recent past include:\n\n* **Shadow Reversal Failure:** The bank failed to credit the amount involved in unauthorised electronic transactions (shadow reversal) to certain customer accounts within **10 working days** from the date of notification by the customer.\n* **Compensation Delay:** The bank failed to compensate certain customers within **90 days** from the date of receipt of the complaint.\n* **Opening of Current Accounts - Need for Discipline:** The bank opened or maintained certain **current accounts** in contravention of regulatory requirements.\n\nThis action was taken following a statutory inspection for supervisory evaluation (ISE 2023) with reference to the bank's financial position as on **March 31, 2023**.`
    };
  }

  // --- QUERY 2: SUPERVISORY ASSESSMENT/EVALUATION (Matches image 3) ---
  if (matches(["supervisory", "evaluation", "competency", "officer", "grade", "my appraisal", "tej"])) {
    const table = "supervisory_evaluations";
    const tejRecord = currentDb.supervisory_evaluations[0];
    
    return {
      success: true,
      table,
      thoughts: getReasoningSteps(table, naturalQuery),
      sql: `SELECT final_grade, comments FROM supervisory_evaluations WHERE officer_name = 'Tej';`,
      columns: ["officer_name", "final_grade", "comments"],
      rows: [
        { officer_name: "Tej", final_grade: tejRecord.final_grade, comments: tejRecord.comments }
      ],
      chartData: null,
      answerText: `Here is the competency assessment summary for RBI Officer **Tej** as of the appraisal cycle ending **March 31, 2023**:\n\n### Competency Assessment Comments:\n* **Encouraging and Leveraging Diversity:** "The officer has excellent team working skills."\n* **Implementation and Execution Excellence:** "Demonstrated outstanding execution skills."\n* **Ability to Analyze and Improve Systems and Procedures:** "Proven analytical and problem solving abilities."\n* **Detailed Knowledge of Work Process Flow:** "Outstanding knowledge of work processes."\n* **Understanding of General Administration Processes:** "Excellent understanding."\n\nYour Reporting Officer awarded you a **Final Numerical Grade of 10**.`
    };
  }

  // --- QUERY 3: COMPARE ALL PENALTIES (AGGREGATION + CHART) ---
  if (matches(["compare", "chart", "graph", "all penalties", "total penalty", "highest penalty", "average penalty"])) {
    const table = "bank_penalties";
    const rows = currentDb.bank_penalties.map(p => ({
      bank: p.bank_name.split(" (")[0], // Shorten name for chart display
      penalty_cr: p.penalty_amount_cr,
      category: p.category
    })).sort((a, b) => b.penalty_cr - a.penalty_cr);

    return {
      success: true,
      table,
      thoughts: getReasoningSteps(table, naturalQuery),
      sql: `SELECT bank_name, penalty_amount_cr FROM bank_penalties ORDER BY penalty_amount_cr DESC;`,
      columns: ["bank", "penalty_cr", "category"],
      rows,
      chartData: rows.map(r => ({ label: r.bank, value: r.penalty_cr })),
      answerText: `A total comparative analysis of RBI penalties shows that **ICICI Bank** received the highest monetary penalty of **12.19 Crores**, followed by **State Bank of India (SBI)** at **5.0 Crores**, and **Bank of Baroda** at **4.34 Crores**. The total penalised amount across the top commercial banks is **${rows.reduce((sum, r) => sum + r.penalty_cr, 0).toFixed(2)} Crores INR**.`
    };
  }

  // --- QUERY 4: LIST COMPLIANCE STATUS ---
  if (matches(["compliance", "rating", "status", "inspections", "audit"])) {
    const table = "compliance_logs";
    const rows = currentDb.compliance_logs;

    return {
      success: true,
      table,
      thoughts: getReasoningSteps(table, naturalQuery),
      sql: `SELECT bank_name, rating, status, violations_count FROM compliance_logs;`,
      columns: ["bank_name", "rating", "status", "violations_count"],
      rows,
      chartData: rows.map(r => ({ label: r.bank_name.split(" (")[0], value: r.violations_count })),
      answerText: `Here is the current regulatory compliance breakdown for 2023:\n\n* **State Bank of India (SBI)**: Satisfactory rating. Currently under **Active Monitoring** with 3 logged violations.\n* **HDFC Bank**: **High Compliant** rating. Audit is closed with only 1 logged violation.\n* **ICICI Bank**: **Needs Improvement** rating. Currently **Under Review** with 5 logged violations.\n* **Bank of Baroda**: **Needs Improvement** rating. Currently **Under Review** with 4 logged violations.\n* **Axis Bank**: Satisfactory rating. Currently under **Active Monitoring** with 2 violations.`
    };
  }

  // --- CHECK DYNAMIC UPLOADED FILES ---
  for (const tableName of Object.keys(currentDb)) {
    if (tableName !== "bank_penalties" && tableName !== "supervisory_evaluations" && tableName !== "compliance_logs") {
      if (q.includes(tableName.replace(/_/g, " ")) || q.includes(tableName) || q.includes("file") || q.includes("uploaded") || q.includes("data")) {
        const table = tableName;
        const rows = currentDb[table];
        if (rows && rows.length > 0) {
          const cols = Object.keys(rows[0]);
          return {
            success: true,
            table,
            thoughts: getReasoningSteps(table, naturalQuery),
            sql: `SELECT ${cols.slice(0, 4).join(", ")} FROM ${table} LIMIT 10;`,
            columns: cols,
            rows: rows.slice(0, 10),
            chartData: null,
            answerText: `Successfully parsed and queried your uploaded knowledge base file (**${table}**). Found **${rows.length} rows** of data in total. Displaying the top records matching schema headers.`
          };
        }
      }
    }
  }

  // --- DEFAULT FALLBACK / GENERIC TEXT CHAT ---
  return {
    success: false,
    thoughts: [
      { step: "Intent Identification", desc: "No direct SQL database matches detected. Routing to general knowledge base." }
    ],
    sql: null,
    columns: null,
    rows: null,
    chartData: null,
    answerText: `I parsed your query but couldn't map it directly to a database schema table. \n\nHowever, I can tell you about general RBI regulatory parameters:\n* Try asking about **SBI penalties** to inspect regulatory actions.\n* Try asking to **compare penalties** or ask for a **chart** of penalty values.\n* Try asking for **compliance ratings** of commercial banks.\n* Upload a CSV file on the **Build Knowledge** panel to query custom datasets!`
  };
};
