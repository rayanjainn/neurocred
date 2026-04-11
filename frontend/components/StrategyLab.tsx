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
  Target
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

  return <CanvasStrategyLab />;
}

// ------ MSME UI ------
function MSMEStrategyLab() {
  const [incomeChange, setIncomeChange] = useState([0]);
  const [expenseChange, setExpenseChange] = useState([0]);
  const [savingsPct, setSavingsPct] = useState([10]);
  const [isSimulating, setIsSimulating] = useState(false);
  const [results, setResults] = useState<{ risk: number; savings: number } | null>(null);

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
      <Handle type="source" position={Position.Bottom} className="w-2 h-2 opacity-0" />
      <Activity className="w-4 h-4 text-blue-400 shrink-0" />
      <div className="text-sm font-semibold flex-1">{data.label}</div>
      {data.value && <div className="text-xs bg-blue-500/20 px-2 py-0.5 rounded text-blue-200">{data.value}</div>}
    </div>
  ),
  conditionNode: ({ data }: any) => (
    <div className={cn("px-4 py-2.5 rounded-full flex items-center gap-2 min-w-[200px] backdrop-blur-md", nodeStyles.condition)}>
      <Handle type="target" position={Position.Top} className="w-2 h-2 opacity-0" />
      <Handle type="source" position={Position.Bottom} className="w-2 h-2 opacity-0" />
      <AlertTriangle className="w-4 h-4 text-orange-400 shrink-0" />
      <div className="text-sm font-semibold">{data.label}</div>
    </div>
  ),
  actionNode: ({ data }: any) => (
    <div className={cn("px-4 py-2.5 rounded-full flex items-center gap-2 min-w-[200px] backdrop-blur-md", nodeStyles.action)}>
      <Handle type="target" position={Position.Top} className="w-2 h-2 opacity-0" />
      <Handle type="source" position={Position.Bottom} className="w-2 h-2 opacity-0" />
      <Zap className="w-4 h-4 text-green-400 shrink-0" />
      <div className="text-sm font-semibold">{data.label}</div>
    </div>
  ),
  resultNode: ({ data }: any) => (
    <div className={cn("px-6 py-4 rounded-xl flex flex-col items-center justify-center min-w-[240px] text-center backdrop-blur-xl relative overflow-hidden", nodeStyles.result)}>
      <div className="absolute inset-0 bg-gradient-to-r from-purple-600/20 to-fuchsia-600/20" />
      <div className="absolute inset-0 border-2 border-purple-400/50 rounded-xl" />
      <Handle type="target" position={Position.Top} className="w-2 h-2 opacity-0" />
      <Activity className="w-6 h-6 text-purple-300 mb-2 relative z-10" />
      <div className="text-base font-bold uppercase tracking-widest relative z-10">{data.label}</div>
      <div className="text-[10px] text-purple-300/70 mt-1 uppercase relative z-10">Simulation Endpoint</div>
    </div>
  )
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

function CanvasStrategyLab() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [simRunning, setSimRunning] = useState(false);
  const [simResults, setSimResults] = useState<{risk: number, netWorth: number[], liquidity: string, stress: string} | null>(null);
  
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
    (params: Connection) => setEdges((eds) => addEdge({ ...params, animated: true, style: { stroke: '#94a3b8', strokeWidth: 2, filter: 'none' } } as any, eds)),
    [setEdges],
  );

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
    }
    
    if (newNodes.length > 0) {
      setNodes(newNodes);
      setEdges(newEdges);
      setSimResults(null); 
    }
  };

  const runSimulation = () => {
    setSimRunning(true);
    setSimResults(null);
    
    // Save current edges
    const currentEdges = edges;

    // Simulate edges flowing super fast
    setEdges((eds) => eds.map(e => ({ ...e, style: { ...e.style, stroke: '#10b981', strokeWidth: 4, filter: 'drop-shadow(0 0 8px #10b981)' } })));

    setTimeout(() => {
      setSimRunning(false);
      setSimResults({
        risk: Math.floor(Math.random() * 40 + 30),
        netWorth: Array.from({length: 7}, () => Math.floor(Math.random() * 60 + 20)),
        liquidity: ['Low', 'Medium', 'High'][Math.floor(Math.random() * 3)],
        stress: ['Low', 'Medium', 'High'][Math.floor(Math.random() * 3)]
      });

      // Reset edges color to original
      setEdges(currentEdges);
    }, 1500);
  };

  return (
    <div className="absolute inset-0 flex bg-[#0d0f12] text-foreground font-sans overflow-hidden">
      
      {/* LEFT SIDEBAR - TEMPLATES & PALETTE */}
      <div className="w-[320px] h-full flex flex-col bg-[#111418] border-r border-white/5 z-20 shrink-0">
        
        {/* Header */}
        <div className="p-6 pb-2 shrink-0">
          <div className="flex items-center gap-2 mb-2">
            <BrainCircuit className="w-5 h-5 text-blue-400" />
            <h1 className="text-xl font-bold tracking-tight text-white">Strategy Lab</h1>
          </div>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Design & simulate MSME financial stress pathways.
          </p>
        </div>

        {/* Templates */}
        <div className="p-5 flex-1 min-h-0 overflow-y-auto space-y-8">
          
          <div className="space-y-3">
            <p className="text-[10px] font-bold text-white/40 uppercase tracking-widest pl-1">Templates</p>
            <div className="space-y-2">
              <TemplateButton icon={<UserX className="w-4 h-4 text-red-400" />} label="Job Loss Survival Plan" border="border-red-500/30" bg="hover:bg-red-950/20" onClick={() => loadStrategyTemplate('job_loss')} />
              <TemplateButton icon={<Percent className="w-4 h-4 text-rose-400" />} label="Debt Reduction Strategy" border="border-rose-500/30" bg="hover:bg-rose-950/20" onClick={() => loadStrategyTemplate('debt_reduction')} />
              <TemplateButton icon={<TrendingUp className="w-4 h-4 text-emerald-400" />} label="Investment Optimization" border="border-emerald-500/30" bg="hover:bg-emerald-950/20" onClick={() => loadStrategyTemplate('investment_optimization')} />
              <TemplateButton icon={<AlertTriangle className="w-4 h-4 text-orange-400" />} label="Cash Flow Crisis" border="border-orange-500/30" bg="hover:bg-orange-950/20" onClick={() => loadStrategyTemplate('cash_flow_crisis')} />
              <TemplateButton icon={<Plus className="w-4 h-4 text-blue-400" />} label="Expansion Growth Plan" border="border-blue-500/30" bg="hover:bg-blue-950/20" onClick={() => loadStrategyTemplate('expansion_growth')} />
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

        {/* AI Button Bottom */}
        <div className="p-5 border-t border-white/5 shrink-0">
          <Button variant="outline" className="w-full bg-emerald-950/40 border-emerald-500/30 hover:bg-emerald-900/40 text-emerald-100 rounded-xl h-12 flex items-center justify-center gap-2" onClick={() => loadStrategyTemplate('expansion_growth')}>
            <BrainCircuit className="w-4 h-4 text-emerald-400" />
            Generate Strategy (AI)
          </Button>
        </div>

      </div>

      {/* MIDDLE CANVAS */}
      <div className="flex-1 relative bg-[#090b0e] overflow-hidden">
        
        {/* Glow behind canvas */}
        <div className="absolute inset-x-0 top-0 h-[200px] bg-emerald-900/10 blur-[100px] pointer-events-none" />
        <div className="absolute inset-y-0 left-0 w-[200px] bg-blue-900/10 blur-[100px] pointer-events-none" />

        {/* The React Flow Canvas */}
        <div className="absolute inset-4 rounded-2xl border border-white/10 bg-[#0d0f12]/80 backdrop-blur-sm overflow-hidden shadow-2xl flex items-center justify-center">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              nodeTypes={nodeTypes}
              fitView
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
      <div className="w-[360px] h-full bg-[#111418] border-l border-white/5 z-20 shrink-0 flex flex-col">
          
          <div className="flex flex-col gap-8 flex-1 min-h-0 overflow-y-auto p-6 pr-4">
            
            {/* Header */}
            <div>
              <h2 className="flex items-center gap-2 text-lg font-semibold text-white mb-6">
                <Activity className="w-5 h-5 text-emerald-400" />
                Simulation Results
              </h2>

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
