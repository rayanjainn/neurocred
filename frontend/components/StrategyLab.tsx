"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { useAuth } from "@/dib/authContext";
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  Edge,
  MarkerType,
  Handle,
  Position,
  Panel,
  ConnectionLineType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import { 
  Play, 
  Activity, 
  TrendingUp, 
  TrendingDown, 
  DollarSign, 
  AlertTriangle,
  Zap,
  Briefcase,
  PiggyBank,
  BrainCircuit,
  Plus,
  Percent,
  Scissors,
  PauseCircle,
  Lightbulb,
  UserX,
  Target,
  ChevronLeft,
  ChevronRight
} from "lucide-react";
import { cn } from "@/dib/utils";

export function StrategyLab() {
  const { user } = useAuth();

  if (!user || user.role === "admin") {
    return <div className="p-6">Not available for this role.</div>;
  }

  if (user.role === "msme") {
    return <MSMEStrategyLab />;
  }

  if (user.role === "loan_officer") {
    return <LoanOfficerStrategyLab />;
  }

  return <CanvasStrategyLab user={user} />;
}

// ------ MSME UI ------
function MSMEStrategyLab() {
  const { user } = useAuth();
  const [incomeChange, setIncomeChange] = useState([0]);
  const [expenseChange, setExpenseChange] = useState([0]);
  const [savingsPct, setSavingsPct] = useState([10]);
  const [isSimulating, setIsSimulating] = useState(false);
  const [results, setResults] = useState<{ risk: number; savings: number } | null>(null);
  const [strategies, setStrategies] = useState<any[]>([]);
  const [appliedStrategies, setAppliedStrategies] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (!user?.gstin) return;
    fetch(`/api/strategy/${encodeURIComponent(user.gstin)}`)
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => setStrategies(Array.isArray(data) ? data : []))
      .catch(() => setStrategies([]));
  }, [user?.gstin]);

  const handleSimulate = () => {
    setIsSimulating(true);
    setResults(null);
    setTimeout(() => {
      const riskDelta = Math.floor(Math.random() * 20 - 10);
      const savingsDelta = Math.floor(Math.random() * 15 + 5);
      setResults({
        risk: 65 + riskDelta,
        savings: 20000 + savingsDelta * 1000,
      });
      setIsSimulating(false);
    }, 1200);
  };

  const applyStrategy = (strategy: any) => {
    const reduction = Number(strategy?.impact?.risk_reduction ?? 0);
    setResults((prev) => {
      const baseRisk = prev?.risk ?? 65;
      const baseSavings = prev?.savings ?? 20000;
      return {
        risk: Math.max(0, baseRisk - Math.max(0, reduction)),
        savings: baseSavings,
      };
    });
    setAppliedStrategies((prev) => ({ ...prev, [strategy.strategy_id]: true }));
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-white to-white/60 bg-clip-text text-transparent">Strategy Builder</h1>
        <p className="text-muted-foreground mt-2">Adjust your financial drivers and see projected outcomes.</p>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <Card className="p-6 bg-white/5 border-white/10 backdrop-blur-md space-y-8">
          <div>
            <div className="flex justify-between mb-2">
              <label className="text-sm font-medium text-foreground/80">Projected Income Change (%)</label>
              <span className="text-sm font-semibold text-primary">{incomeChange[0]}%</span>
            </div>
            <Slider value={incomeChange} onValueChange={setIncomeChange} min={-50} max={50} step={1} className="py-2" />
          </div>

          <div>
            <div className="flex justify-between mb-2">
              <label className="text-sm font-medium text-foreground/80">Projected Expense Change (%)</label>
              <span className="text-sm font-semibold text-destructive">{expenseChange[0]}%</span>
            </div>
            <Slider value={expenseChange} onValueChange={setExpenseChange} min={-50} max={50} step={1} className="py-2" />
          </div>

          <div>
            <div className="flex justify-between mb-2">
              <label className="text-sm font-medium text-foreground/80">Target Savings Rate (%)</label>
              <span className="text-sm font-semibold text-green-400">{savingsPct[0]}%</span>
            </div>
            <Slider value={savingsPct} onValueChange={setSavingsPct} min={0} max={50} step={1} className="py-2" />
          </div>

          <Button 
            className="w-full text-base font-semibold py-6 h-auto mt-4 bg-primary text-primary-foreground hover:bg-primary/90"
            onClick={handleSimulate}
            disabled={isSimulating}
          >
            {isSimulating ? "Running Simulation..." : "Simulate Projection"}
          </Button>
        </Card>

        {/* ... MSME Results implementation omitted for brevity ... */}
        <Card className="p-6 bg-white/5 border-white/10 backdrop-blur-md flex items-center justify-center">
            {results ? (
                 <div className="text-center">
                    <p className="text-lg">Risk: <span className={results.risk < 50 ? "text-green-400" : "text-red-400"}>{results.risk}</span></p>
                    <p className="text-lg mt-4">Savings: <span className="text-primary">${results.savings.toLocaleString()}</span></p>
                 </div>
            ) : <p className="text-muted-foreground">Run simulation to see results.</p>}
        </Card>
      </div>

      <Card className="p-6 bg-white/5 border border-white/10 rounded-xl backdrop-blur-md">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold">Recommended Strategies</h2>
          <span className="text-xs text-muted-foreground">Dynamic from analyst</span>
        </div>

        {strategies.length === 0 ? (
          <p className="text-sm text-muted-foreground">No suggestions available yet.</p>
        ) : (
          <div className="grid md:grid-cols-2 gap-3">
            {strategies.map((strategy: any) => {
              const applied = !!appliedStrategies[strategy.strategy_id];
              const riskReduction = Number(strategy?.impact?.risk_reduction ?? 0);
              const liquidity = strategy?.impact?.liquidity ?? "-";
              return (
                <div
                  key={strategy.strategy_id}
                  className="rounded-xl border border-white/10 bg-white/5 p-4 transition-all hover:shadow-[0_0_18px_rgba(255,255,255,0.10)]"
                >
                  <p className="text-sm font-semibold">{strategy.title}</p>
                  <p className="text-xs text-muted-foreground mt-1">{strategy.description}</p>
                  <div className="mt-3 text-xs text-foreground/80 space-y-1">
                    <p>Risk ↓ {riskReduction}%</p>
                    <p>Liquidity ↑ {liquidity}</p>
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    className="mt-3"
                    disabled={applied}
                    onClick={() => applyStrategy(strategy)}
                  >
                    {applied ? "Applied" : "Apply Strategy"}
                  </Button>
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}

// ------ LOAN OFFICER UI ------
function LoanOfficerStrategyLab() {
  return (
    <div className="p-10 flex flex-col items-center">
        <h1 className="text-2xl font-bold mb-4">View Only Strategy</h1>
        <p className="text-muted-foreground">MSME has not published a finalized dashboard layout yet.</p>
    </div>
  );
}

// ------ CANVAS BUILDER (RISK MGR / ANALYST) ------

const nodeStyles: any = {
  input: "bg-blue-950/40 border border-blue-500/80 shadow-[0_0_15px_rgba(59,130,246,0.3)] text-blue-50",
  condition: "bg-orange-950/40 border border-orange-500/80 shadow-[0_0_15px_rgba(249,115,22,0.3)] text-orange-50",
  action: "bg-green-950/40 border border-green-500/80 shadow-[0_0_15px_rgba(34,197,94,0.3)] text-green-50",
  result: "bg-purple-950/60 border border-purple-400 shadow-[0_0_30px_rgba(192,132,252,0.6)] text-purple-50",
};

const nodeTypes = {
  inputNode: ({ data }: any) => (
    <div className={cn("px-4 py-2.5 rounded-full flex items-center gap-3 min-w-[200px] backdrop-blur-md", nodeStyles.input)}>
      <Handle type="source" position={Position.Bottom} className="h-3 w-3 rounded-full border border-cyan-300/80 bg-cyan-400/80 shadow-[0_0_8px_rgba(34,211,238,0.9)]" />
      <Activity className="w-4 h-4 text-blue-400 shrink-0" />
      <div className="text-sm font-semibold flex-1">{data.label}</div>
      {data.value && <div className="text-xs bg-blue-500/20 px-2 py-0.5 rounded text-blue-200">{data.value}</div>}
    </div>
  ),
  conditionNode: ({ data }: any) => (
    <div className={cn("px-4 py-2.5 rounded-full flex items-center gap-2 min-w-[200px] backdrop-blur-md", nodeStyles.condition)}>
      <Handle type="target" position={Position.Top} className="h-3 w-3 rounded-full border border-amber-300/80 bg-amber-400/80 shadow-[0_0_8px_rgba(251,191,36,0.9)]" />
      <Handle type="source" position={Position.Bottom} className="h-3 w-3 rounded-full border border-amber-300/80 bg-amber-400/80 shadow-[0_0_8px_rgba(251,191,36,0.9)]" />
      <AlertTriangle className="w-4 h-4 text-orange-400 shrink-0" />
      <div className="text-sm font-semibold">{data.label}</div>
    </div>
  ),
  actionNode: ({ data }: any) => (
    <div className={cn("px-4 py-2.5 rounded-full flex items-center gap-2 min-w-[200px] backdrop-blur-md", nodeStyles.action)}>
      <Handle type="target" position={Position.Top} className="h-3 w-3 rounded-full border border-emerald-300/80 bg-emerald-400/80 shadow-[0_0_8px_rgba(52,211,153,0.9)]" />
      <Handle type="source" position={Position.Bottom} className="h-3 w-3 rounded-full border border-emerald-300/80 bg-emerald-400/80 shadow-[0_0_8px_rgba(52,211,153,0.9)]" />
      <Zap className="w-4 h-4 text-green-400 shrink-0" />
      <div className="text-sm font-semibold">{data.label}</div>
    </div>
  ),
  resultNode: ({ data }: any) => (
    <div className={cn("px-6 py-4 rounded-xl flex flex-col items-center justify-center min-w-[240px] text-center backdrop-blur-xl relative overflow-hidden", nodeStyles.result)}>
      <div className="absolute inset-0 bg-gradient-to-r from-purple-600/20 to-fuchsia-600/20" />
      <div className="absolute inset-0 border-2 border-purple-400/50 rounded-xl" />
      <Handle type="target" position={Position.Top} className="h-3 w-3 rounded-full border border-purple-300/80 bg-purple-400/80 shadow-[0_0_8px_rgba(196,181,253,0.95)]" />
      <Activity className="w-6 h-6 text-purple-300 mb-2 relative z-10" />
      <div className="text-base font-bold uppercase tracking-widest relative z-10">{data.label}</div>
      <div className="text-[10px] text-purple-300/70 mt-1 uppercase relative z-10">Simulation Endpoint</div>
    </div>
  ),
  customNode: ({ data }: any) => (
    <div className="min-w-[210px] rounded-xl border border-cyan-400/40 bg-cyan-950/30 px-4 py-3 shadow-[0_0_18px_rgba(34,211,238,0.25)] backdrop-blur-md">
      <Handle type="target" position={Position.Top} className="h-3 w-3 rounded-full border border-cyan-300/80 bg-cyan-400/80 shadow-[0_0_8px_rgba(34,211,238,0.9)]" />
      <Handle type="source" position={Position.Bottom} className="h-3 w-3 rounded-full border border-cyan-300/80 bg-cyan-400/80 shadow-[0_0_8px_rgba(34,211,238,0.9)]" />
      <p className="text-[10px] uppercase tracking-[0.12em] text-cyan-300/80">{String(data?.nodeType || "custom")}</p>
      <p className="mt-1 text-sm font-semibold text-cyan-100">{data?.label || "Custom Node"}</p>
      {data?.params && Object.keys(data.params).length > 0 && (
        <p className="mt-1 text-[11px] text-cyan-100/75">{JSON.stringify(data.params)}</p>
      )}
    </div>
  ),
};

const initialNodes = [
  { id: '1', type: 'inputNode', position: { x: 300, y: 50 }, data: { label: 'Income Change', value: '-25%' } },
  { id: '2', type: 'conditionNode', position: { x: 200, y: 150 }, data: { label: 'If Liquidity < 4 Months' } },
  { id: '3', type: 'conditionNode', position: { x: 450, y: 150 }, data: { label: 'If Risk > Medium' } },
  { id: '4', type: 'actionNode', position: { x: 150, y: 250 }, data: { label: 'Restructure EMI' } },
  { id: '5', type: 'actionNode', position: { x: 400, y: 250 }, data: { label: 'Reduce Expenses' } },
  { id: '6', type: 'resultNode', position: { x: 275, y: 400 }, data: { label: 'Run Simulation' } },
];

const initialEdges = [
  { id: 'e1-2', source: '1', target: '2', animated: true, type: 'smoothstep', style: { stroke: '#3b82f6', strokeWidth: 3, filter: 'drop-shadow(0 0 5px #3b82f6)' } },
  { id: 'e1-3', source: '1', target: '3', animated: true, type: 'smoothstep', style: { stroke: '#3b82f6', strokeWidth: 3, filter: 'drop-shadow(0 0 5px #3b82f6)' } },
  { id: 'e2-4', source: '2', target: '4', animated: true, type: 'smoothstep', style: { stroke: '#f97316', strokeWidth: 3, filter: 'drop-shadow(0 0 5px #f97316)' } },
  { id: 'e3-5', source: '3', target: '5', animated: true, type: 'smoothstep', style: { stroke: '#f97316', strokeWidth: 3, filter: 'drop-shadow(0 0 5px #f97316)' } },
  { id: 'e2-5', source: '2', target: '5', animated: true, type: 'smoothstep', style: { stroke: '#f97316', strokeWidth: 3, filter: 'drop-shadow(0 0 5px #f97316)' } },
  { id: 'e4-6', source: '4', target: '6', animated: true, type: 'smoothstep', style: { stroke: '#22c55e', strokeWidth: 3, filter: 'drop-shadow(0 0 5px #22c55e)' } },
  { id: 'e5-6', source: '5', target: '6', animated: true, type: 'smoothstep', style: { stroke: '#22c55e', strokeWidth: 3, filter: 'drop-shadow(0 0 5px #22c55e)' } },
];

const MSME_GSTIN_OPTIONS = [
  "19HLPRM4249Z3Z1",
  "09EXVAF9205D6Z0",
  "27AAAAA0000A1Z5",
];

const CHAT_PROMPT_TEMPLATES = [
  "Reduce expenses by 20% and pause EMI if liquidity is low",
];

const semanticTypeFromNode = (node: any): "condition" | "action" | "trigger" | "result" => {
  if (!node) return "trigger";
  if (node.type === "conditionNode") return "condition";
  if (node.type === "actionNode") return "action";
  if (node.type === "resultNode") return "result";
  if (node.type === "customNode") {
    const nt = String(node.data?.nodeType || "trigger").toLowerCase();
    if (nt === "condition" || nt === "action" || nt === "result") return nt;
    return "trigger";
  }
  return "trigger";
};

const isValidConnection = (sourceNode: any, targetNode: any) => {
  const sourceType = semanticTypeFromNode(sourceNode);
  const targetType = semanticTypeFromNode(targetNode);
  if (sourceType === "action" && targetType === "condition") return false;
  if (sourceType === "condition" && targetType === "action") return true;
  if (sourceType === "action" && targetType === "result") return true;
  if (sourceType === "trigger" && targetType === "condition") return true;
  if (sourceType === "trigger" && targetType === "action") return true;
  if (sourceType === "condition" && targetType === "result") return true;
  if (sourceType === "action" && targetType === "action") return true;
  if (sourceType === "condition" && targetType === "condition") return true;
  return false;
};

const parsePromptToBlueprint = (prompt: string) => {
  const text = prompt.toLowerCase();
  const parsed: Array<{ kind: "trigger" | "condition" | "action"; label: string; params?: Record<string, any> }> = [];
  const percentMatch = text.match(/(\d{1,2})\s*%/);
  const pct = percentMatch ? Number(percentMatch[1]) : 0;

  parsed.push({ kind: "trigger", label: "User Goal Input", params: { source: "chat" } });

  if (text.includes("liquidity") && (text.includes("low") || text.includes("below"))) {
    parsed.push({
      kind: "condition",
      label: "If Liquidity is Low",
      params: { field: "liquidity", operator: "<", value: "LOW" },
    });
  }

  if (text.includes("reduce expense") || text.includes("reduce expenses") || text.includes("cut expense")) {
    parsed.push({
      kind: "action",
      label: `Reduce Expenses ${pct ? `(${pct}%)` : ""}`.trim(),
      params: { type: "expense", value: pct ? -pct : -20 },
    });
  }

  if (text.includes("pause emi") || text.includes("emi pause")) {
    parsed.push({
      kind: "action",
      label: "Pause EMI",
      params: { type: "emi", value: "pause" },
    });
  }

  if (parsed.length === 1) {
    parsed.push({ kind: "action", label: "Reduce Discretionary Spend (15%)", params: { type: "expense", value: -15 } });
  }

  parsed.push({ kind: "trigger", label: "Run Simulation", params: { stage: "result" } });
  return parsed;
};

const explainStrategy = (nodes: any[], edges: any[], logs: string[]) => {
  const actionCount = nodes.filter((n) => semanticTypeFromNode(n) === "action").length;
  const conditionCount = nodes.filter((n) => semanticTypeFromNode(n) === "condition").length;
  const edgeCount = edges.length;
  const lastLog = logs.length ? logs[logs.length - 1] : "Simulation not run yet.";
  return `This strategy uses ${actionCount} action node(s) and ${conditionCount} condition node(s) connected through ${edgeCount} edge(s). ${lastLog}`;
};

function CanvasStrategyLab({ user }: { user: any }) {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [simRunning, setSimRunning] = useState(false);
  const [simResults, setSimResults] = useState<{risk: number, netWorth: number[], liquidity: string, stress: string} | null>(null);
  const [targetGstin, setTargetGstin] = useState(MSME_GSTIN_OPTIONS[0]);
  const [pushStatus, setPushStatus] = useState<"idle" | "sending" | "sent" | "failed">("idle");
  const [pushMessage, setPushMessage] = useState("");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [simulationSteps, setSimulationSteps] = useState<string[]>([]);
  const [chatPrompt, setChatPrompt] = useState("");
  const [aiSuggestion, setAiSuggestion] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const [connectMessage, setConnectMessage] = useState("");
  const [showCustomModal, setShowCustomModal] = useState(false);
  const [customName, setCustomName] = useState("");
  const [customType, setCustomType] = useState<"condition" | "action" | "trigger">("action");
  const [customParams, setCustomParams] = useState("");
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);

  const selectedNode = useMemo(() => nodes.find((n) => n.id === selectedNodeId) ?? null, [nodes, selectedNodeId]);

  const handlePanelWheel = (event: React.WheelEvent<HTMLDivElement>) => {
    const el = event.currentTarget;
    if (el.scrollHeight > el.clientHeight) {
      el.scrollTop += event.deltaY;
      event.preventDefault();
    }
  };
  
  // Set initial mock data to match image
  useEffect(() => {
    setSimResults({
      risk: 52,
      netWorth: [20, 30, 25, 45, 60, 50, 80],
      liquidity: 'Medium',
      stress: 'Low'
    });
  }, []);

  const onConnect = useCallback(
    (params: Connection) => {
      const sourceNode = nodes.find((n) => n.id === params.source);
      const targetNode = nodes.find((n) => n.id === params.target);
      if (!sourceNode || !targetNode || !isValidConnection(sourceNode, targetNode)) {
        setConnectMessage("Invalid connection: Action -> Condition is not allowed.");
        window.setTimeout(() => setConnectMessage(""), 2200);
        return;
      }
      setEdges((eds) => addEdge({ ...params, animated: true, style: { stroke: '#94a3b8', strokeWidth: 2, filter: 'none' } } as any, eds));
      setConnectMessage("");
    },
    [nodes, setEdges],
  );

  const addCustomNode = () => {
    if (!customName.trim()) return;
    const parsedParams = customParams.trim()
      ? customParams.split(",").reduce((acc, pair) => {
          const [k, v] = pair.split(":").map((s) => s.trim());
          if (!k) return acc;
          const asNum = Number(v);
          acc[k] = Number.isNaN(asNum) ? v : asNum;
          return acc;
        }, {} as Record<string, any>)
      : {};

    const nodeId = `custom_${Date.now()}`;
    setNodes((nds) => [
      ...nds,
      {
        id: nodeId,
        type: "customNode",
        position: { x: 260 + Math.floor(Math.random() * 260), y: 80 + Math.floor(Math.random() * 280) },
        data: {
          label: customName,
          nodeType: customType,
          params: parsedParams,
        },
      } as any,
    ]);

    setCustomName("");
    setCustomType("action");
    setCustomParams("");
    setShowCustomModal(false);
  };

  const saveStrategy = () => {
    const payload = {
      nodes,
      edges,
      savedAt: new Date().toISOString(),
    };
    window.localStorage.setItem("strategyLab:last", JSON.stringify(payload));
    setConnectMessage("Strategy saved locally");
    window.setTimeout(() => setConnectMessage(""), 1800);
  };

  const loadStrategy = () => {
    const raw = window.localStorage.getItem("strategyLab:last");
    if (!raw) {
      setConnectMessage("No saved strategy found");
      window.setTimeout(() => setConnectMessage(""), 1800);
      return;
    }
    try {
      const data = JSON.parse(raw);
      if (Array.isArray(data.nodes)) setNodes(data.nodes);
      if (Array.isArray(data.edges)) setEdges(data.edges);
      setConnectMessage("Loaded saved strategy");
      window.setTimeout(() => setConnectMessage(""), 1800);
    } catch {
      setConnectMessage("Saved strategy is invalid");
      window.setTimeout(() => setConnectMessage(""), 1800);
    }
  };

  const loadStrategyTemplate = (id: string) => {
    let newNodes: any[] = [];
    let newEdges: any[] = [];
    if (id === 'job_loss') {
      newNodes = [
        { id: '1', type: 'inputNode', position: { x: 300, y: 50 }, data: { label: 'Income Drops', value: '50%' } },
        { id: '2', type: 'conditionNode', position: { x: 300, y: 150 }, data: { label: 'If Liquidity < 3 Months' } },
        { id: '3', type: 'actionNode', position: { x: 150, y: 250 }, data: { label: 'Pause Equipment EMI' } },
        { id: '4', type: 'actionNode', position: { x: 450, y: 250 }, data: { label: 'Liquidate FDs' } },
        { id: '5', type: 'resultNode', position: { x: 300, y: 350 }, data: { label: 'Run Simulation' } },
      ];
      newEdges = [
        { id: 'e1-2', source: '1', target: '2', animated: true, type: 'smoothstep', style: { stroke: '#3b82f6', strokeWidth: 3, filter: 'drop-shadow(0 0 5px #3b82f6)' } },
        { id: 'e2-3', source: '2', target: '3', animated: true, type: 'smoothstep', style: { stroke: '#f97316', strokeWidth: 3, filter: 'drop-shadow(0 0 5px #f97316)' } },
        { id: 'e2-4', source: '2', target: '4', animated: true, type: 'smoothstep', style: { stroke: '#f97316', strokeWidth: 3, filter: 'drop-shadow(0 0 5px #f97316)' } },
        { id: 'e3-5', source: '3', target: '5', animated: true, type: 'smoothstep', style: { stroke: '#22c55e', strokeWidth: 3, filter: 'drop-shadow(0 0 5px #22c55e)' } },
        { id: 'e4-5', source: '4', target: '5', animated: true, type: 'smoothstep', style: { stroke: '#22c55e', strokeWidth: 3, filter: 'drop-shadow(0 0 5px #22c55e)' } },
      ];
    } else if (id === 'debt_reduction') {
      newNodes = [
        { id: '1', type: 'inputNode', position: { x: 300, y: 50 }, data: { label: 'Consolidate Loans', value: '-10% EMI' } },
        { id: '2', type: 'conditionNode', position: { x: 200, y: 150 }, data: { label: 'If High Interest' } },
        { id: '4', type: 'actionNode', position: { x: 200, y: 250 }, data: { label: 'Prepay Loan A' } },
        { id: '5', type: 'actionNode', position: { x: 450, y: 150 }, data: { label: 'Cut Discretionary Spend' } },
        { id: '6', type: 'resultNode', position: { x: 325, y: 350 }, data: { label: 'Run Simulation' } },
      ];
      newEdges = [
        { id: 'e1-2', source: '1', target: '2', animated: true, type: 'smoothstep', style: { stroke: '#3b82f6', strokeWidth: 3, filter: 'drop-shadow(0 0 5px #3b82f6)' } },
        { id: 'e1-5', source: '1', target: '5', animated: true, type: 'smoothstep', style: { stroke: '#3b82f6', strokeWidth: 3, filter: 'drop-shadow(0 0 5px #3b82f6)' } },
        { id: 'e2-4', source: '2', target: '4', animated: true, type: 'smoothstep', style: { stroke: '#f97316', strokeWidth: 3, filter: 'drop-shadow(0 0 5px #f97316)' } },
        { id: 'e4-6', source: '4', target: '6', animated: true, type: 'smoothstep', style: { stroke: '#22c55e', strokeWidth: 3, filter: 'drop-shadow(0 0 5px #22c55e)' } },
        { id: 'e5-6', source: '5', target: '6', animated: true, type: 'smoothstep', style: { stroke: '#22c55e', strokeWidth: 3, filter: 'drop-shadow(0 0 5px #22c55e)' } },
      ];
    } else if (id === 'investment_optimization') {
      newNodes = [
        { id: '1', type: 'inputNode', position: { x: 300, y: 50 }, data: { label: 'Surplus Capital', value: '+15%' } },
        { id: '2', type: 'conditionNode', position: { x: 300, y: 150 }, data: { label: 'If Liquidity > 6 Months' } },
        { id: '3', type: 'actionNode', position: { x: 300, y: 250 }, data: { label: 'Invest in Machinery' } },
        { id: '4', type: 'resultNode', position: { x: 300, y: 350 }, data: { label: 'Run Simulation' } },
      ];
      newEdges = [
        { id: 'e1-2', source: '1', target: '2', animated: true, type: 'smoothstep', style: { stroke: '#3b82f6', strokeWidth: 3, filter: 'drop-shadow(0 0 5px #3b82f6)' } },
        { id: 'e2-3', source: '2', target: '3', animated: true, type: 'smoothstep', style: { stroke: '#f97316', strokeWidth: 3, filter: 'drop-shadow(0 0 5px #f97316)' } },
        { id: 'e3-4', source: '3', target: '4', animated: true, type: 'smoothstep', style: { stroke: '#22c55e', strokeWidth: 3, filter: 'drop-shadow(0 0 5px #22c55e)' } },
      ];
    } else if (id === 'cash_flow_crisis') {
      newNodes = [
        { id: '1', type: 'inputNode', position: { x: 300, y: 50 }, data: { label: 'Client Payment Delayed', value: '-30% Cash' } },
        { id: '2', type: 'conditionNode', position: { x: 300, y: 150 }, data: { label: 'If Balance < Minimum' } },
        { id: '3', type: 'actionNode', position: { x: 150, y: 250 }, data: { label: 'Avail Overdraft' } },
        { id: '4', type: 'actionNode', position: { x: 450, y: 250 }, data: { label: 'Delay Vendor Pay' } },
        { id: '5', type: 'resultNode', position: { x: 300, y: 350 }, data: { label: 'Run Simulation' } },
      ];
      newEdges = [
        { id: 'e1-2', source: '1', target: '2', animated: true, type: 'smoothstep', style: { stroke: '#3b82f6', strokeWidth: 3, filter: 'drop-shadow(0 0 5px #3b82f6)' } },
        { id: 'e2-3', source: '2', target: '3', animated: true, type: 'smoothstep', style: { stroke: '#f97316', strokeWidth: 3, filter: 'drop-shadow(0 0 5px #f97316)' } },
        { id: 'e2-4', source: '2', target: '4', animated: true, type: 'smoothstep', style: { stroke: '#f97316', strokeWidth: 3, filter: 'drop-shadow(0 0 5px #f97316)' } },
        { id: 'e3-5', source: '3', target: '5', animated: true, type: 'smoothstep', style: { stroke: '#22c55e', strokeWidth: 3, filter: 'drop-shadow(0 0 5px #22c55e)' } },
        { id: 'e4-5', source: '4', target: '5', animated: true, type: 'smoothstep', style: { stroke: '#22c55e', strokeWidth: 3, filter: 'drop-shadow(0 0 5px #22c55e)' } },
      ];
    } else if (id === 'expansion_growth') {
      newNodes = [
        { id: '1', type: 'inputNode', position: { x: 300, y: 50 }, data: { label: 'Increase Ad Spend', value: '+40%' } },
        { id: '2', type: 'conditionNode', position: { x: 300, y: 150 }, data: { label: 'If ROI > 2x' } },
        { id: '3', type: 'actionNode', position: { x: 300, y: 250 }, data: { label: 'Hire 5 New Staff' } },
        { id: '4', type: 'resultNode', position: { x: 300, y: 350 }, data: { label: 'Run Simulation' } },
      ];
      newEdges = [
        { id: 'e1-2', source: '1', target: '2', animated: true, type: 'smoothstep', style: { stroke: '#3b82f6', strokeWidth: 3, filter: 'drop-shadow(0 0 5px #3b82f6)' } },
        { id: 'e2-3', source: '2', target: '3', animated: true, type: 'smoothstep', style: { stroke: '#f97316', strokeWidth: 3, filter: 'drop-shadow(0 0 5px #f97316)' } },
        { id: 'e3-4', source: '3', target: '4', animated: true, type: 'smoothstep', style: { stroke: '#22c55e', strokeWidth: 3, filter: 'drop-shadow(0 0 5px #22c55e)' } },
      ];
    } else if (id === 'seasonal_demand_dip') {
      newNodes = [
        { id: '1', type: 'inputNode', position: { x: 300, y: 50 }, data: { label: 'Seasonal Demand Dip', value: '-18%' } },
        { id: '2', type: 'conditionNode', position: { x: 300, y: 150 }, data: { label: 'If Receivables Delay > 30d' } },
        { id: '3', type: 'actionNode', position: { x: 180, y: 250 }, data: { label: 'Tighten Credit Window' } },
        { id: '4', type: 'actionNode', position: { x: 430, y: 250 }, data: { label: 'Shift to Low-cost Channels' } },
        { id: '5', type: 'resultNode', position: { x: 300, y: 350 }, data: { label: 'Run Simulation' } },
      ];
      newEdges = [
        { id: 'e1-2', source: '1', target: '2', animated: true, type: 'smoothstep', style: { stroke: '#3b82f6', strokeWidth: 3, filter: 'drop-shadow(0 0 5px #3b82f6)' } },
        { id: 'e2-3', source: '2', target: '3', animated: true, type: 'smoothstep', style: { stroke: '#f97316', strokeWidth: 3, filter: 'drop-shadow(0 0 5px #f97316)' } },
        { id: 'e2-4', source: '2', target: '4', animated: true, type: 'smoothstep', style: { stroke: '#f97316', strokeWidth: 3, filter: 'drop-shadow(0 0 5px #f97316)' } },
        { id: 'e3-5', source: '3', target: '5', animated: true, type: 'smoothstep', style: { stroke: '#22c55e', strokeWidth: 3, filter: 'drop-shadow(0 0 5px #22c55e)' } },
        { id: 'e4-5', source: '4', target: '5', animated: true, type: 'smoothstep', style: { stroke: '#22c55e', strokeWidth: 3, filter: 'drop-shadow(0 0 5px #22c55e)' } },
      ];
    } else if (id === 'working_capital_guard') {
      newNodes = [
        { id: '1', type: 'inputNode', position: { x: 300, y: 50 }, data: { label: 'Raw Material Cost Up', value: '+12%' } },
        { id: '2', type: 'conditionNode', position: { x: 300, y: 150 }, data: { label: 'If Cash Buffer < 4 Months' } },
        { id: '3', type: 'actionNode', position: { x: 300, y: 250 }, data: { label: 'Activate WC Line + Trim Spend' } },
        { id: '4', type: 'resultNode', position: { x: 300, y: 350 }, data: { label: 'Run Simulation' } },
      ];
      newEdges = [
        { id: 'e1-2', source: '1', target: '2', animated: true, type: 'smoothstep', style: { stroke: '#3b82f6', strokeWidth: 3, filter: 'drop-shadow(0 0 5px #3b82f6)' } },
        { id: 'e2-3', source: '2', target: '3', animated: true, type: 'smoothstep', style: { stroke: '#f97316', strokeWidth: 3, filter: 'drop-shadow(0 0 5px #f97316)' } },
        { id: 'e3-4', source: '3', target: '4', animated: true, type: 'smoothstep', style: { stroke: '#22c55e', strokeWidth: 3, filter: 'drop-shadow(0 0 5px #22c55e)' } },
      ];
    }
    
    if (newNodes.length > 0) {
      setNodes(newNodes);
      setEdges(newEdges);
      setSimResults(null); 
    }
  };

  const runSimulation = async () => {
    setSimRunning(true);
    setSimResults(null);
    setSimulationSteps([]);
    
    // Save current edges
    const currentEdges = edges;

    // Simulate edges flowing super fast
    setEdges((eds) => eds.map(e => ({ ...e, style: { ...e.style, stroke: '#10b981', strokeWidth: 4, filter: 'drop-shadow(0 0 8px #10b981)' } })));

    const orderedNodes = [...nodes].sort((a, b) => a.position.y - b.position.y || a.position.x - b.position.x);
    let riskScore = 52;
    let liquidityScore = 55;
    const logs: string[] = [];

    for (let i = 0; i < orderedNodes.length; i += 1) {
      const node = orderedNodes[i];
      const label = String(node.data?.label || "").toLowerCase();
      const semantic = semanticTypeFromNode(node);
      if (semantic === "condition" && label.includes("liquidity") && label.includes("low")) {
        riskScore += 4;
        logs.push(`Step ${i + 1}: Liquidity condition triggered -> Risk increased`);
      } else if (semantic === "action" && (label.includes("reduce expense") || label.includes("expense"))) {
        riskScore -= 6;
        liquidityScore += 7;
        logs.push(`Step ${i + 1}: Expense reduction applied -> Risk decreased`);
      } else if (semantic === "action" && label.includes("emi")) {
        riskScore -= 4;
        liquidityScore += 5;
        logs.push(`Step ${i + 1}: EMI action applied -> Stress reduced`);
      } else if (semantic === "trigger" && label.includes("income") && label.includes("-")) {
        riskScore += 7;
        liquidityScore -= 6;
        logs.push(`Step ${i + 1}: Income dropped -> Risk increased`);
      } else {
        logs.push(`Step ${i + 1}: ${node.data?.label || "Node"} evaluated`);
      }
      setSimulationSteps([...logs]);
      // deliberate step-by-step visual progression
      await new Promise((resolve) => setTimeout(resolve, 260));
    }

    riskScore = Math.max(0, Math.min(100, riskScore));
    liquidityScore = Math.max(0, Math.min(100, liquidityScore));

    setSimRunning(false);
    setSimResults({
      risk: riskScore,
      netWorth: Array.from({length: 7}, (_, idx) => Math.max(15, 18 + idx * 7 + Math.floor((100 - riskScore) / 8))),
      liquidity: liquidityScore < 40 ? "Low" : liquidityScore < 70 ? "Medium" : "High",
      stress: riskScore > 70 ? "High" : riskScore > 45 ? "Medium" : "Low"
    });

    // Reset edges color to original
    setEdges(currentEdges);
  };

  const updateSelectedNode = (patch: Record<string, any>) => {
    if (!selectedNodeId) return;
    setNodes((nds) =>
      nds.map((n) =>
        n.id === selectedNodeId
          ? {
              ...n,
              data: {
                ...n.data,
                ...patch,
              },
            }
          : n,
      ),
    );
  };

  const generateFromChat = () => {
    if (!chatPrompt.trim()) return;
    const blueprint = parsePromptToBlueprint(chatPrompt);
    const startX = 260;
    const startY = 70;
    const generatedNodes = blueprint.map((item, idx) => {
      const id = `gen_${Date.now()}_${idx}`;
      const nodeType = item.kind === "condition" ? "conditionNode" : item.kind === "action" ? "actionNode" : idx === blueprint.length - 1 ? "resultNode" : "inputNode";
      return {
        id,
        type: nodeType,
        position: { x: startX + (idx % 2) * 210, y: startY + idx * 90 },
        data: {
          label: item.label,
          nodeType: item.kind,
          params: item.params || {},
        },
      };
    });
    const generatedEdges = generatedNodes.slice(0, -1).map((n, idx) => ({
      id: `ge_${n.id}_${generatedNodes[idx + 1].id}`,
      source: n.id,
      target: generatedNodes[idx + 1].id,
      animated: true,
      type: "smoothstep",
      style: { stroke: '#22c55e', strokeWidth: 2 },
    }));
    setNodes(generatedNodes as any);
    setEdges(generatedEdges as any);
    setConnectMessage("Strategy generated from chat");
    window.setTimeout(() => setConnectMessage(""), 1800);
  };

  const fetchGroqSuggestion = async () => {
    if (!chatPrompt.trim()) return;
    try {
      setAiLoading(true);
      const res = await fetch("/api/twin-chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: `You are a financial strategy assistant. Convert this into a short strategy suggestion with concrete actions: ${chatPrompt}`,
          dataContext: { role: user?.role || "credit_analyst", mode: "strategy_lab" },
        }),
      });
      const data = await res.json();
      setAiSuggestion(data?.reply || data?.error || "No suggestion generated.");
    } catch {
      setAiSuggestion("Could not fetch AI suggestion right now.");
    } finally {
      setAiLoading(false);
    }
  };

  const pushStrategyToMsme = async () => {
    const gstin = targetGstin.trim().toUpperCase();
    if (!gstin) {
      setPushStatus("failed");
      setPushMessage("Please enter MSME GSTIN");
      return;
    }

    const strategy = {
      strategy_id: Date.now().toString(),
      user_id: gstin,
      created_by: user?.role === "credit_analyst" ? "analyst" : (user?.role || "analyst"),
      title: "Debt Reduction Plan",
      description: "Reduce expenses and EMI",
      steps: [
        { type: "expense", value: -20 },
        { type: "emi", value: -30 },
      ],
      impact: {
        risk_reduction: simResults ? Math.max(5, Math.min(30, 100 - simResults.risk)) : 12,
        liquidity: simResults?.liquidity?.toUpperCase() || "MEDIUM",
      },
      created_at: new Date().toISOString(),
    };

    try {
      setPushStatus("sending");
      setPushMessage("");
      const res = await fetch("/api/strategy/add", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: gstin, strategy }),
      });
      if (!res.ok) {
        const txt = await res.text().catch(() => "");
        throw new Error(txt || "push failed");
      }
      setPushStatus("sent");
      setPushMessage("Suggestion sent");
      window.setTimeout(() => setPushStatus("idle"), 2400);
      window.setTimeout(() => setPushMessage(""), 2400);
    } catch (e: any) {
      setPushStatus("failed");
      setPushMessage(e?.message ? "Failed to send strategy" : "Failed to send strategy");
      window.setTimeout(() => setPushStatus("idle"), 2400);
      window.setTimeout(() => setPushMessage(""), 2400);
    }
  };

  return (
    <div className="absolute inset-0 flex bg-[#0d0f12] text-foreground font-sans overflow-hidden">
      
      {/* LEFT SIDEBAR - TEMPLATES & PALETTE */}
      <div className={cn(
        "h-full flex flex-col bg-[#111418] border-r border-white/5 z-20 shrink-0 transition-all duration-300",
        leftCollapsed ? "w-[56px]" : "w-[320px]"
      )}>
        
        {/* Header */}
        <div className={cn("shrink-0", leftCollapsed ? "px-2 py-4" : "p-6 pb-2")}>
          <div className="mb-2 flex items-center justify-between gap-2">
            <div className={cn("flex items-center gap-2", leftCollapsed && "justify-center w-full") }>
              <BrainCircuit className="w-5 h-5 text-blue-400" />
              {!leftCollapsed && <h1 className="text-xl font-bold tracking-tight text-white">Strategy Lab</h1>}
            </div>
            {!leftCollapsed && (
              <button
                type="button"
                onClick={() => setLeftCollapsed(true)}
                className="rounded-md border border-white/10 bg-white/5 p-1 text-white/70 hover:bg-white/10"
                aria-label="Collapse left panel"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
            )}
          </div>
          {!leftCollapsed && (
            <p className="text-xs text-muted-foreground leading-relaxed">
              Design & simulate MSME financial stress pathways.
            </p>
          )}
          {leftCollapsed && (
            <button
              type="button"
              onClick={() => setLeftCollapsed(false)}
              className="mt-2 flex w-full items-center justify-center rounded-md border border-white/10 bg-white/5 p-1 text-white/70 hover:bg-white/10"
              aria-label="Expand left panel"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          )}
        </div>

        {/* Templates */}
        {!leftCollapsed && (
        <div onWheelCapture={handlePanelWheel} className="p-5 flex-1 min-h-0 overflow-y-scroll overscroll-contain space-y-8 [scrollbar-gutter:stable] [scrollbar-width:auto] [scrollbar-color:rgba(52,211,153,0.85)_rgba(255,255,255,0.08)] [&::-webkit-scrollbar]:w-3 [&::-webkit-scrollbar-track]:bg-white/5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-emerald-400/60 hover:[&::-webkit-scrollbar-thumb]:bg-emerald-300/80">
          
          <div className="space-y-3">
            <p className="text-[10px] font-bold text-white/40 uppercase tracking-widest pl-1">Templates</p>
            <div className="space-y-2">
              <TemplateButton icon={<UserX className="w-4 h-4 text-red-400" />} label="Job Loss Survival Plan" border="border-red-500/30" bg="hover:bg-red-950/20" onClick={() => loadStrategyTemplate('job_loss')} />
              <TemplateButton icon={<Percent className="w-4 h-4 text-rose-400" />} label="Debt Reduction Strategy" border="border-rose-500/30" bg="hover:bg-rose-950/20" onClick={() => loadStrategyTemplate('debt_reduction')} />
              <TemplateButton icon={<TrendingUp className="w-4 h-4 text-emerald-400" />} label="Investment Optimization" border="border-emerald-500/30" bg="hover:bg-emerald-950/20" onClick={() => loadStrategyTemplate('investment_optimization')} />
              <TemplateButton icon={<AlertTriangle className="w-4 h-4 text-orange-400" />} label="Cash Flow Crisis" border="border-orange-500/30" bg="hover:bg-orange-950/20" onClick={() => loadStrategyTemplate('cash_flow_crisis')} />
              <TemplateButton icon={<Plus className="w-4 h-4 text-blue-400" />} label="Expansion Growth Plan" border="border-blue-500/30" bg="hover:bg-blue-950/20" onClick={() => loadStrategyTemplate('expansion_growth')} />
              <TemplateButton icon={<TrendingDown className="w-4 h-4 text-cyan-400" />} label="Seasonal Demand Dip" border="border-cyan-500/30" bg="hover:bg-cyan-950/20" onClick={() => loadStrategyTemplate('seasonal_demand_dip')} />
              <TemplateButton icon={<Briefcase className="w-4 h-4 text-lime-400" />} label="Working Capital Guard" border="border-lime-500/30" bg="hover:bg-lime-950/20" onClick={() => loadStrategyTemplate('working_capital_guard')} />
            </div>
          </div>

          <div className="space-y-3">
            <p className="text-[10px] font-bold text-white/40 uppercase tracking-widest pl-1">Node Palette</p>
            
            <div className="grid grid-cols-2 gap-3">
              {/* Input Node */}
              <PaletteCard 
                icon={<TrendingDown className="w-4 h-4 text-blue-400" />} 
                title="Income Change"
                colorClass="text-blue-200 border-blue-500/30 bg-[#172033]"
              />
              
              {/* Condition Node */}
               <PaletteCard 
                icon={<AlertTriangle className="w-4 h-4 text-orange-400" />} 
                title="Risk Threshold"
                colorClass="text-orange-200 border-orange-500/30 bg-[#291b14]"
              />

              {/* Action Nodes */}
              <PaletteCard 
                icon={<PauseCircle className="w-4 h-4 text-green-400" />} 
                title="EMI Pause"
                colorClass="text-green-200 border-green-500/30 bg-[#14241a]"
              />

               <PaletteCard 
                icon={<Scissors className="w-4 h-4 text-green-400" />} 
                title="Expense Cut"
                colorClass="text-green-200 border-green-500/30 bg-[#14241a]"
              />
            </div>

            {/* Run Node */}
            <div className="mt-3">
              <PaletteCard 
                icon={<Activity className="w-4 h-4 text-purple-400" />} 
                title="RUN SIMULATION"
                fullWidth
                colorClass="text-purple-200 border-purple-500/50 bg-[#241433] shadow-[0_0_15px_rgba(168,85,247,0.15)]"
              />
            </div>
          </div>

        </div>
        )}

        {/* AI Button Bottom */}
        {!leftCollapsed && (
        <div className="p-5 border-t border-white/5 shrink-0">
          <div className="mb-3 grid grid-cols-2 gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setShowCustomModal(true)}
              className="h-10 rounded-lg border border-cyan-500/30 bg-cyan-950/20 text-cyan-100 hover:bg-cyan-900/30"
            >
              Add Node
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={saveStrategy}
              className="h-10 rounded-lg border border-blue-500/30 bg-blue-950/20 text-blue-100 hover:bg-blue-900/30"
            >
              Save
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={loadStrategy}
              className="col-span-2 h-10 rounded-lg border border-purple-500/30 bg-purple-950/20 text-purple-100 hover:bg-purple-900/30"
            >
              Load Last Strategy
            </Button>
          </div>

          <Button variant="outline" className="w-full bg-emerald-950/40 border-emerald-500/30 hover:bg-emerald-900/40 text-emerald-100 rounded-xl h-12 flex items-center justify-center gap-2" onClick={() => loadStrategyTemplate('expansion_growth')}>
            <BrainCircuit className="w-4 h-4 text-emerald-400" />
            Generate Strategy (AI)
          </Button>
          {connectMessage && <p className="mt-2 text-xs text-cyan-300">{connectMessage}</p>}
          {aiSuggestion && (
            <div className="mt-3 rounded-xl border border-fuchsia-500/20 bg-fuchsia-950/20 p-3">
              <p className="text-[10px] uppercase tracking-[0.15em] text-fuchsia-300/80">AI Strategy Suggestion</p>
              <p className="mt-1 text-xs text-fuchsia-100/90 leading-relaxed">{aiSuggestion}</p>
            </div>
          )}
        </div>
        )}

      </div>

      {/* MIDDLE CANVAS */}
      <div className="flex-1 relative bg-[#090b0e] overflow-hidden">
        
        {/* Glow behind canvas */}
        <div className="absolute inset-x-0 top-0 h-[200px] bg-emerald-900/10 blur-[100px] pointer-events-none" />
        <div className="absolute inset-y-0 left-0 w-[200px] bg-blue-900/10 blur-[100px] pointer-events-none" />

        {/* The React Flow Canvas */}
        <div className="absolute inset-4 rounded-2xl border border-white/10 bg-[#0d0f12]/80 backdrop-blur-sm overflow-hidden shadow-2xl flex items-center justify-center">
            <div className="absolute left-4 right-4 top-4 z-50 rounded-xl border border-white/10 bg-black/45 p-3 backdrop-blur-md">
              <p className="mb-2 text-[10px] font-bold uppercase tracking-[0.15em] text-white/60">Chat to Strategy Generator</p>
              <div className="mb-2 flex flex-wrap gap-2">
                {CHAT_PROMPT_TEMPLATES.map((template) => (
                  <button
                    key={template}
                    type="button"
                    onClick={() => setChatPrompt(template)}
                    className="rounded-full border border-cyan-400/35 bg-cyan-500/10 px-3 py-1 text-[10px] font-semibold tracking-wide text-cyan-100 hover:bg-cyan-500/20"
                  >
                    {template}
                  </button>
                ))}
              </div>
              <div className="flex flex-col gap-2 md:flex-row md:items-center">
                <input
                  value={chatPrompt}
                  onChange={(e) => setChatPrompt(e.target.value)}
                  placeholder="Reduce expenses by 20% and pause EMI if liquidity is low"
                  className="h-10 flex-1 rounded-lg border border-white/10 bg-black/30 px-3 text-xs text-white outline-none focus:border-emerald-400/60"
                />
                <Button
                  type="button"
                  size="sm"
                  onClick={generateFromChat}
                  className="h-10 rounded-lg border border-emerald-400/40 bg-emerald-500/20 text-emerald-100 hover:bg-emerald-500/30"
                >
                  Generate Nodes
                </Button>
                <Button
                  type="button"
                  size="sm"
                  onClick={fetchGroqSuggestion}
                  disabled={aiLoading}
                  className="h-10 rounded-lg border border-fuchsia-500/40 bg-fuchsia-500/20 text-fuchsia-100 hover:bg-fuchsia-500/30"
                >
                  {aiLoading ? "Thinking..." : "AI Suggest"}
                </Button>
              </div>
            </div>

            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              onNodeClick={(_, node) => setSelectedNodeId(node.id)}
              nodeTypes={nodeTypes}
              fitView
              connectionLineType={ConnectionLineType.SmoothStep}
              connectionLineStyle={{ stroke: "#22d3ee", strokeWidth: 2 }}
              defaultEdgeOptions={{
                animated: true,
                type: "smoothstep",
                style: { stroke: "#94a3b8", strokeWidth: 2 },
                markerEnd: {
                  type: MarkerType.ArrowClosed,
                  color: "#94a3b8",
                },
              }}
              className="w-full h-full"
            >
              <Background gap={40} size={1} color="rgba(255,255,255,0.03)" />
              <Controls 
                className="bg-[#1a1d24] border-white/10 fill-white text-white rounded-lg overflow-hidden [&>button]:border-b-white/5 [&>button:hover]:bg-white/10 shadow-xl m-4" 
                showInteractive={false} 
              />
            </ReactFlow>

            {/* Floating RUN Button */}
            <div className="absolute bottom-10 left-1/2 -translate-x-1/2 z-50">
              <Button
                  size="lg"
                  className={cn(
                    "rounded-full px-10 py-7 text-lg font-bold transition-all duration-300 border border-emerald-400/50 shadow-[0_0_40px_rgba(16,185,129,0.4)]",
                    simRunning 
                      ? "bg-emerald-900/80 text-emerald-200 cursor-wait outline-none ring-4 ring-emerald-600/30" 
                      : "bg-emerald-600 hover:bg-emerald-500 text-white hover:scale-105 hover:shadow-[0_0_60px_rgba(16,185,129,0.6)]"
                  )}
                  onClick={runSimulation}
                  disabled={simRunning}
                >
                  {simRunning ? (
                    <span className="flex items-center gap-2">
                       <Activity className="w-5 h-5 animate-pulse" />
                       Simulating...
                    </span>
                  ) : (
                    <span className="flex items-center gap-2">
                      <Play className="w-5 h-5 fill-current" />
                      Run Simulation
                    </span>
                  )}
              </Button>
            </div>
        </div>

      </div>

      {/* RIGHT SIDEBAR - RESULTS */}
      <div className={cn(
        "h-full bg-[#111418] border-l border-white/5 z-20 shrink-0 flex flex-col transition-all duration-300",
        rightCollapsed ? "w-[56px]" : "w-[360px]"
      )}>
          <div className={cn("shrink-0 border-b border-white/5", rightCollapsed ? "px-2 py-4" : "p-3") }>
            <div className="flex items-center justify-between">
              {!rightCollapsed && <p className="text-xs font-semibold uppercase tracking-[0.15em] text-white/50">Results Panel</p>}
              <button
                type="button"
                onClick={() => setRightCollapsed((prev) => !prev)}
                className="rounded-md border border-white/10 bg-white/5 p-1 text-white/70 hover:bg-white/10"
                aria-label={rightCollapsed ? "Expand right panel" : "Collapse right panel"}
              >
                {rightCollapsed ? <ChevronLeft className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              </button>
            </div>
          </div>

          {!rightCollapsed && (
          
          <div onWheelCapture={handlePanelWheel} className="flex flex-col gap-8 flex-1 min-h-0 overflow-y-scroll overscroll-contain p-6 pr-4 [scrollbar-gutter:stable] [scrollbar-width:auto] [scrollbar-color:rgba(52,211,153,0.85)_rgba(255,255,255,0.08)] [&::-webkit-scrollbar]:w-3 [&::-webkit-scrollbar-track]:bg-white/5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-emerald-400/60 hover:[&::-webkit-scrollbar-thumb]:bg-emerald-300/80">
            
            {/* Header */}
            <div>
              <div className="mb-3 flex items-center gap-2">
                <h2 className="flex items-center gap-2 text-lg font-semibold text-white">
                  <Activity className="w-5 h-5 text-emerald-400" />
                  Simulation Results
                </h2>
              </div>

              {["credit_analyst", "risk_manager"].includes(user?.role || "") && (
                <div className="mb-3 rounded-xl border border-white/10 bg-white/5 p-2.5">
                  <p className="mb-2 text-[10px] uppercase tracking-[0.16em] text-white/45">Send Suggestion To MSME</p>
                  <div className="flex items-center gap-2">
                    <select
                      value={targetGstin}
                      onChange={(e) => setTargetGstin(e.target.value)}
                      className="h-9 flex-1 rounded-lg border border-white/10 bg-[#0d1320] px-2 text-xs text-white outline-none focus:border-emerald-400/60"
                    >
                      {MSME_GSTIN_OPTIONS.map((gstin) => (
                        <option key={gstin} value={gstin}>
                          {gstin}
                        </option>
                      ))}
                    </select>
                    <Button
                      type="button"
                      size="sm"
                      onClick={pushStrategyToMsme}
                      disabled={pushStatus === "sending"}
                      className="h-9 rounded-lg border border-emerald-400/40 bg-emerald-500/20 px-3 text-emerald-100 hover:bg-emerald-500/30"
                    >
                      {pushStatus === "sending" ? "Sending..." : "Give Suggestion"}
                    </Button>
                  </div>
                </div>
              )}

              {pushStatus === "sent" && <p className="mb-2 text-xs text-emerald-400">{pushMessage || "Suggestion sent"}</p>}
              {pushStatus === "failed" && <p className="mb-2 text-xs text-red-400">{pushMessage || "Failed to send strategy"}</p>}

              {/* RISK SCORE */}
              <div className="space-y-4">
                <p className="text-[10px] font-bold text-white/40 uppercase tracking-widest">Risk Score</p>
                <div className="flex items-end gap-2">
                  <span className={cn(
                    "text-6xl font-black tracking-tighter leading-none transition-colors",
                    simResults ? (simResults.risk <= 40 ? "text-emerald-400" : simResults.risk <= 60 ? "text-amber-400" : "text-rose-400") : "text-white/20"
                  )}>
                    {simResults?.risk || "--"}
                  </span>
                  <span className="text-sm font-medium text-white/40 pb-1">/ 100</span>
                </div>
                
                {/* Progress bar */}
                <div className="h-1.5 w-full bg-[#1e2329] rounded-full overflow-hidden mt-2">
                  <div 
                    className="h-full bg-gradient-to-r from-amber-500 to-amber-300 rounded-full transition-all duration-1000"
                    style={{ width: `${simResults?.risk || 0}%` }}
                  />
                </div>
                <p className="text-sm font-semibold text-amber-400 mt-1">Medium Risk</p>
                
                <div className="flex items-start gap-2 mt-2 bg-white/5 rounded-lg p-3 border border-white/5">
                  <TrendingDown className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                  <p className="text-xs text-white/70 leading-relaxed">
                    Risk Score decreased by 3 points after simulation.
                  </p>
                </div>
              </div>
            </div>

            <div className="h-px bg-white/5 w-full" />

            {/* LIQUIDITY STATUS */}
            <div className="space-y-4">
              <p className="text-[10px] font-bold text-white/40 uppercase tracking-widest">Liquidity Status</p>
              
              {/* Complex Bar Indicator Mockup */}
              <div className="relative pt-2">
                <div className="flex h-4 gap-0.5 items-end justify-between px-1">
                  {Array.from({length: 40}).map((_, i) => (
                    <div 
                      key={i} 
                      className={cn(
                        "w-1.5 rounded-full transition-all",
                        i < 10 ? "bg-rose-500/50 h-3" : i < 25 ? "bg-amber-400/80 h-4" : "bg-emerald-500/40 h-2.5"
                      )}
                    />
                  ))}
                </div>
                {/* Indicator thumb */}
                <div className="absolute top-0 left-[60%] -translate-x-1/2 w-1.5 h-6 bg-white rounded-full shadow-[0_0_10px_rgba(255,255,255,0.8)]" />
                
                <div className="flex justify-between text-[10px] text-white/40 mt-1.5 font-medium px-1">
                  <span>Low</span>
                  <span>Medium</span>
                  <span>High</span>
                </div>
              </div>

              <p className="text-sm font-medium text-amber-400">Adequate Liquidity for 5 Months</p>
            </div>

            <div className="h-px bg-white/5 w-full" />

            {/* NET WORTH PROJECTION */}
            <div className="space-y-4">
              <p className="text-[10px] font-bold text-white/40 uppercase tracking-widest">Net Worth Projection</p>
              
              <div className="relative h-24 w-full mt-2 border-b border-white/10 flex items-end">
                {/* 3 lines for graph mockups */}
                <svg className="absolute inset-0 h-full w-full overflow-visible" preserveAspectRatio="none">
                   {/* Background dim line */}
                   <path d="M0,80 Q50,70 100,50 T200,40 T300,10" fill="none" stroke="rgba(59, 130, 246, 0.3)" strokeWidth="2" vectorEffect="non-scaling-stroke" />
                   {/* Main bright line */}
                   <path d="M0,90 Q40,80 80,85 T160,50 T250,40 T320,5" fill="none" stroke="#2dd4bf" strokeWidth="2.5" filter="drop-shadow(0 0 4px rgba(45,212,191,0.6))" vectorEffect="non-scaling-stroke" />
                   {/* Middle line */}
                   <path d="M0,85 Q60,60 120,70 T220,30 T320,20" fill="none" stroke="#60a5fa" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
                </svg>
              </div>
              <div className="flex justify-between text-[10px] text-white/30 font-mono mt-1">
                <span>Am</span>
                <span>8</span>
                <span>12</span>
                <span>20</span>
                <span>24</span>
              </div>
            </div>

            <div className="h-px bg-white/5 w-full" />

            {/* EMI STRESS LEVEL */}
            <div className="space-y-4 mb-4">
              <p className="text-[10px] font-bold text-white/40 uppercase tracking-widest">EMI Stress Level</p>
              
              <div className="flex gap-1 h-3 w-full rounded-full overflow-hidden">
                 <div className="h-full bg-emerald-500 w-1/4" />
                 <div className="h-full bg-yellow-500 w-1/4" />
                 <div className="h-full bg-orange-500 w-1/4 opacity-30" />
                 <div className="h-full bg-red-500 w-1/4 opacity-30" />
              </div>
              
              <p className="text-sm text-white/60">
                [Stress: <span className="text-emerald-400 font-semibold">{simResults?.stress || "--"}</span>]
              </p>
            </div>

            <div className="h-px bg-white/5 w-full" />

            <div className="space-y-3">
              <p className="text-[10px] font-bold text-white/40 uppercase tracking-widest">Step-by-Step Simulation</p>
              <div className="max-h-28 space-y-1 overflow-y-auto rounded-lg border border-white/10 bg-white/5 p-2">
                {simulationSteps.length === 0 ? (
                  <p className="text-xs text-white/45">Run simulation to view ordered steps.</p>
                ) : (
                  simulationSteps.map((step, idx) => (
                    <p key={`${step}-${idx}`} className="text-xs text-white/75">{step}</p>
                  ))
                )}
              </div>
            </div>

            <div className="h-px bg-white/5 w-full" />

            <div className="space-y-3">
              <p className="text-[10px] font-bold text-white/40 uppercase tracking-widest">Node Config Panel</p>
              {!selectedNode ? (
                <p className="text-xs text-white/45">Click a node on canvas to configure label/params.</p>
              ) : (
                <div className="rounded-lg border border-white/10 bg-white/5 p-3 space-y-2">
                  <p className="text-xs text-white/60">Node: {selectedNode.id}</p>
                  <input
                    value={selectedNode.data?.label || ""}
                    onChange={(e) => updateSelectedNode({ label: e.target.value })}
                    className="w-full rounded-md border border-white/10 bg-black/30 px-2 py-1 text-xs text-white outline-none focus:border-cyan-400/60"
                    placeholder="Node label"
                  />
                  <textarea
                    value={JSON.stringify(selectedNode.data?.params || {}, null, 0)}
                    onChange={(e) => {
                      try {
                        const parsed = JSON.parse(e.target.value || "{}");
                        updateSelectedNode({ params: parsed });
                      } catch {
                        // ignore invalid partial JSON while typing
                      }
                    }}
                    className="h-16 w-full resize-none rounded-md border border-white/10 bg-black/30 px-2 py-1 text-xs text-white outline-none focus:border-cyan-400/60"
                    placeholder='{"threshold": 20}'
                  />
                </div>
              )}
            </div>

            <div className="h-px bg-white/5 w-full" />

            <div className="space-y-2 rounded-xl border border-cyan-500/20 bg-cyan-950/10 p-3">
              <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-cyan-300/80">Strategy Explainer</p>
              <p className="text-xs text-cyan-100/85 leading-relaxed">{explainStrategy(nodes, edges, simulationSteps)}</p>
            </div>

            {/* AI INSIGHT */}
            <div className="mt-auto bg-[#181622] border border-purple-500/20 rounded-xl p-4 relative overflow-hidden group">
              <div className="absolute right-0 bottom-0 text-7xl text-purple-500/10 -mr-4 -mb-4 transition-transform group-hover:scale-110">✦</div>
              <div className="flex items-start gap-3 relative z-10">
                <Lightbulb className="w-5 h-5 text-purple-400 shrink-0 mt-0.5" />
                <p className="text-xs text-purple-100/70 leading-relaxed">
                  <strong className="text-purple-300 font-semibold">AI Insight:</strong> Current strategy balances debt reduction and cash preservation well. Focus on expense reduction in discretionary spending. Maintain existing plan.
                </p>
              </div>
            </div>

          </div>
            )}
      </div>

      <CustomNodeModal
        open={showCustomModal}
        name={customName}
        type={customType}
        params={customParams}
        onClose={() => setShowCustomModal(false)}
        onSubmit={addCustomNode}
        onNameChange={setCustomName}
        onTypeChange={setCustomType}
        onParamsChange={setCustomParams}
      />

    </div>
  );
}

function CustomNodeModal({
  open,
  name,
  type,
  params,
  onClose,
  onSubmit,
  onNameChange,
  onTypeChange,
  onParamsChange,
}: {
  open: boolean;
  name: string;
  type: "condition" | "action" | "trigger";
  params: string;
  onClose: () => void;
  onSubmit: () => void;
  onNameChange: (v: string) => void;
  onTypeChange: (v: "condition" | "action" | "trigger") => void;
  onParamsChange: (v: string) => void;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-md rounded-2xl border border-white/10 bg-[#101620] p-5 shadow-2xl">
        <p className="text-lg font-semibold text-white">Add Custom Node</p>
        <p className="mb-4 text-xs text-white/50">Create a condition/action/trigger node with custom params.</p>
        <div className="space-y-3">
          <input
            value={name}
            onChange={(e) => onNameChange(e.target.value)}
            placeholder="Node Name"
            className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-white outline-none focus:border-cyan-400/60"
          />
          <select
            value={type}
            onChange={(e) => onTypeChange(e.target.value as "condition" | "action" | "trigger")}
            className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-white outline-none focus:border-cyan-400/60"
          >
            <option value="condition">condition</option>
            <option value="action">action</option>
            <option value="trigger">trigger</option>
          </select>
          <input
            value={params}
            onChange={(e) => onParamsChange(e.target.value)}
            placeholder="Parameters e.g. threshold:20, mode:strict"
            className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-white outline-none focus:border-cyan-400/60"
          />
        </div>
        <div className="mt-4 flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="button" onClick={onSubmit} className="bg-cyan-600 hover:bg-cyan-500 text-white">Create Node</Button>
        </div>
      </div>
    </div>
  );
}

// ------ Sidebar Components ------

function TemplateButton({ icon, label, border, bg, onClick }: { icon: React.ReactNode; label: string; border: string; bg: string; onClick?: () => void }) {
  return (
    <button onClick={onClick} className={cn(
      "w-full flex items-center justify-between p-3 rounded-xl border bg-black/20 text-left transition-colors",
      border, bg
    )}>
      <span className="text-xs font-medium text-white/80">{label}</span>
      <div className="bg-white/5 p-1.5 rounded-lg">
        {icon}
      </div>
    </button>
  );
}

function PaletteCard({ icon, title, colorClass, fullWidth = false }: { icon: React.ReactNode; title: string; colorClass: string; fullWidth?: boolean }) {
  return (
    <div className={cn(
      "border rounded-xl p-3 flex flex-col items-center justify-center text-center gap-2 cursor-grab active:cursor-grabbing hover:bg-opacity-80 transition-opacity",
      colorClass,
      fullWidth ? "col-span-2 w-full py-4 text-sm" : "aspect-[4/3]"
    )}>
      {icon}
      <div className={cn("font-bold tracking-tight leading-tight", fullWidth ? "text-sm" : "text-[11px]")}>{title}</div>
      <div className="text-[9px] text-white/40 mt-auto">Drag to add<br/>(Simulation)</div>
    </div>
  );
}
