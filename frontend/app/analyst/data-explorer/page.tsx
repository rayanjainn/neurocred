"use client";

import { useState, useEffect, useRef } from "react";
import { adminApi } from "@/dib/api";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/shared";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { 
  Search, DownloadCloud, Activity, LayoutDashboard, Calendar, 
  ArrowUpRight, ArrowDownRight, PackageOpen, Shield, Globe, 
  Link as LinkIcon, ExternalLink, Zap, ChevronRight, Filter
} from "lucide-react";
import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, 
  ResponsiveContainer, Legend, AreaChart, Area 
} from "recharts";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import { cn } from "@/dib/utils";

interface Profile {
  gstin: string;
  business_name: string;
  profile_type: string;
  state_code: string;
  business_age_months: number;
  credit_score?: number;
  risk_band?: string;
}

interface TimelinePoint {
  date: string;
  daily_volume?: number;
  daily_count?: number;
  daily_ewb_volume?: number;
  daily_ewb_count?: number;
}

interface Details {
  info: Profile;
  upi_timeline: TimelinePoint[];
  ewb_timeline: TimelinePoint[];
  recent_upi: any[];
  recent_ewb: any[];
}

export default function DataExplorerPage() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [filteredProfiles, setFilteredProfiles] = useState<Profile[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [selectedGstin, setSelectedGstin] = useState<string | null>(null);
  const [details, setDetails] = useState<Details | null>(null);
  const [detailsLoading, setDetailsLoading] = useState(false);

  useEffect(() => {
    adminApi.getExplorerGstins()
      .then((res) => {
        setProfiles(res);
        setFilteredProfiles(res);
      })
      .finally(() => setLoading(false));
  }, []);

  useGSAP(() => {
    if (!containerRef.current) return;
    const targets = containerRef.current.querySelectorAll('.gsap-fade-up');
    if (targets.length === 0) return;
    
    gsap.fromTo(targets, 
      { opacity: 0, y: 20 }, 
      { opacity: 1, y: 0, duration: 0.6, stagger: 0.05, ease: "power2.out" }
    );
  }, { scope: containerRef, dependencies: [loading, selectedGstin] });

  const handleSearch = (v: string) => {
    setSearch(v);
    const q = v.toLowerCase();
    setFilteredProfiles(
      profiles.filter(p => p.gstin.toLowerCase().includes(q) || p.business_name.toLowerCase().includes(q) || p.profile_type.toLowerCase().includes(q))
    );
  };

  const loadDetails = async (gstin: string) => {
    setSelectedGstin(gstin);
    setDetailsLoading(true);
    try {
      const res = await adminApi.getExplorerDetails(gstin);
      setDetails(res);
    } catch(e) {
      console.error(e);
    } finally {
      setDetailsLoading(false);
    }
  };

  const getProfileColor = (type: string) => {
    if(type.includes("HEALTHY")) return "bg-emerald-500/10 text-emerald-500 border-emerald-500/20";
    if(type.includes("STRUGGLING")) return "bg-amber-500/10 text-amber-500 border-amber-500/20";
    if(type.includes("SHELL") || type.includes("FRAUD")) return "bg-rose-500/10 text-rose-500 border-rose-500/20";
    return "bg-slate-500/10 text-slate-500 border-slate-500/20";
  };

  return (
    <div ref={containerRef} className="p-6 md:p-8 max-w-[1400px] mx-auto min-h-screen space-y-8 relative overflow-hidden">
      {/* Background Glows */}
      <div className="absolute top-[-10%] right-[-10%] w-[500px] h-[500px] bg-primary/10 rounded-full blur-[120px] -z-10 animate-pulse" />
      <div className="absolute bottom-[-10%] left-[-10%] w-[400px] h-[400px] bg-indigo-500/10 rounded-full blur-[100px] -z-10" />

      <PageHeader 
        title="Entity Data Explorer 360" 
        description="Global system state inspection. Deep visualization of transactional graph nodes and behavioral partitions."
      />

      {!selectedGstin ? (
        <Card className="gsap-fade-up shadow-2xl border-border bg-card/40 backdrop-blur-xl overflow-hidden rounded-3xl">
            <CardHeader className="border-b bg-muted/30 py-6">
                <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
                    <div className="space-y-1">
                        <div className="flex items-center gap-2">
                            <div className="p-2 rounded-xl bg-primary/20">
                                <Globe className="h-5 w-5 text-primary" />
                            </div>
                            <CardTitle className="text-2xl font-bold tracking-tight">Active Entity Directory</CardTitle>
                        </div>
                        <CardDescription>Filtering {filteredProfiles.length} of {profiles.length} total generated nodes</CardDescription>
                    </div>
                    <div className="relative w-full md:w-96">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                        <Input 
                            placeholder="Input GSTIN, Name or Persona..." 
                            value={search} 
                            onChange={e => handleSearch(e.target.value)}
                            className="pl-10 h-12 bg-background/50 border-border focus-visible:ring-primary rounded-2xl shadow-inner"
                        />
                    </div>
                </div>
            </CardHeader>
            <CardContent className="p-0">
            {loading ? (
                <div className="p-24 text-center text-muted-foreground flex flex-col items-center gap-4">
                   <div className="relative">
                       <Activity className="h-12 w-12 text-primary animate-pulse" />
                       <Zap className="h-6 w-6 text-primary absolute -top-1 -right-1 animate-bounce" />
                   </div>
                   <p className="font-medium tracking-wide">QUERYING REDIS TRANSACTION STREAMS...</p>
                </div>
            ) : (
                <div className="overflow-auto max-h-[750px] scrollbar-thin scrollbar-thumb-primary/20">
                    <Table>
                        <TableHeader className="sticky top-0 bg-background/95 backdrop-blur-md z-20">
                            <TableRow className="hover:bg-transparent">
                                <TableHead className="py-4 pl-8 uppercase text-[10px] font-bold tracking-widest text-muted-foreground">GSTIN Identification</TableHead>
                                <TableHead className="uppercase text-[10px] font-bold tracking-widest text-muted-foreground">Business Entity</TableHead>
                                <TableHead className="uppercase text-[10px] font-bold tracking-widest text-muted-foreground">Behavioral Persona</TableHead>
                                <TableHead className="uppercase text-[10px] font-bold tracking-widest text-muted-foreground">Risk Maturity</TableHead>
                                <TableHead className="text-right pr-8 uppercase text-[10px] font-bold tracking-widest text-muted-foreground">Action</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {filteredProfiles.map((p, i) => (
                                <TableRow key={p.gstin} className="group hover:bg-muted/50 transition-all duration-300 border-border/50">
                                    <TableCell className="py-4 pl-8">
                                        <div className="flex flex-col">
                                            <span className="font-mono text-sm font-semibold tracking-tighter text-foreground group-hover:text-primary transition-colors">{p.gstin}</span>
                                            <span className="text-[10px] text-muted-foreground">LOC: {p.gstin.substring(0, 2)}</span>
                                        </div>
                                    </TableCell>
                                    <TableCell className="font-medium text-foreground">{p.business_name}</TableCell>
                                    <TableCell>
                                        <Badge variant="outline" className={cn("px-2.5 py-0.5 rounded-full text-[10px] font-bold tracking-wide uppercase border", getProfileColor(p.profile_type))}>
                                            {p.profile_type.replace(/_/g, " ")}
                                        </Badge>
                                    </TableCell>
                                    <TableCell>
                                        <div className="flex flex-col gap-1.5">
                                            <div className="flex justify-between items-end">
                                                <span className="text-[10px] font-bold text-muted-foreground uppercase">{p.business_age_months}m tenure</span>
                                                <span className="text-[10px] font-black text-primary">{p.credit_score || 700}</span>
                                            </div>
                                            <div className="w-24 h-1.5 bg-muted rounded-full overflow-hidden border border-border/50">
                                                <div className="h-full bg-primary" style={{ width: `${Math.min(100, ((p.credit_score || 700)-300)/550*100)}%` }} />
                                            </div>
                                        </div>
                                    </TableCell>
                                    <TableCell className="text-right pr-8">
                                        <Button 
                                            size="sm" 
                                            variant="ghost" 
                                            onClick={() => loadDetails(p.gstin)} 
                                            className="group-hover:bg-primary group-hover:text-primary-foreground rounded-xl transition-all h-9 w-9 p-0"
                                        >
                                            <ChevronRight className="h-5 w-5" />
                                        </Button>
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                    {filteredProfiles.length === 0 && (
                        <div className="p-16 text-center">
                            <div className="bg-muted w-16 h-16 rounded-3xl flex items-center justify-center mx-auto mb-4">
                                <Search className="h-8 w-8 text-muted-foreground" />
                            </div>
                            <p className="text-muted-foreground font-medium">No results for "{search}"</p>
                        </div>
                    )}
                </div>
            )}
            </CardContent>
        </Card>
      ) : (
        <div className="space-y-8 animate-in fade-in zoom-in-95 duration-400">
           <Button 
             variant="outline" 
             onClick={() => setSelectedGstin(null)} 
             className="bg-card/40 backdrop-blur-md border-border hover:bg-muted text-foreground px-6 h-12 rounded-2xl gap-2 font-semibold shadow-xl"
           >
             <LayoutDashboard className="h-4 w-4" />
             Return to Fleet Overview
           </Button>

           {detailsLoading || !details ? (
              <div className="h-[500px] flex flex-col items-center justify-center bg-card/40 backdrop-blur-xl rounded-[40px] border border-border shadow-2xl relative overflow-hidden">
                  <div className="absolute inset-0 bg-gradient-to-tr from-primary/5 to-transparent -z-10" />
                  <div className="flex items-center gap-3 mb-6">
                      <div className="w-4 h-4 rounded-full bg-primary animate-ping" />
                      <div className="w-4 h-4 rounded-full bg-primary/60 animate-ping [animation-delay:0.2s]" />
                      <div className="w-4 h-4 rounded-full bg-primary/30 animate-ping [animation-delay:0.4s]" />
                  </div>
                  <p className="text-2xl font-bold tracking-tight text-foreground">Assembling 360 Degree View</p>
                  <p className="text-muted-foreground mt-2 max-w-xs text-center">Parsing longitudinal signals for {selectedGstin}...</p>
              </div>
           ) : (
             <>
               <Card className="gsap-fade-up shadow-2xl overflow-hidden border-border bg-card/40 backdrop-blur-xl rounded-[32px] border-l-8 border-l-primary group">
                 <div className="absolute top-0 right-0 p-8 opacity-10 group-hover:opacity-20 transition-opacity">
                    <Shield className="w-32 h-32 text-primary" />
                 </div>
                 <CardHeader className="p-8">
                    <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
                        <div className="space-y-3">
                            <div className="flex items-center gap-3">
                                <Badge className={cn("px-4 py-1 text-[10px] font-black tracking-widest uppercase border shadow-lg", getProfileColor(details.info.profile_type))}>
                                    {details.info.profile_type}
                                </Badge>
                                <span className="text-xs font-mono text-muted-foreground">{details.info.gstin}</span>
                            </div>
                            <CardTitle className="text-4xl font-black tracking-tighter bg-gradient-to-r from-foreground to-foreground/60 bg-clip-text text-transparent">
                                {details.info.business_name}
                            </CardTitle>
                            <div className="flex items-center gap-4 text-sm text-muted-foreground font-medium">
                                <span className="flex items-center gap-1.5"><Globe className="w-4 h-4" /> REGION: {details.info.state_code}</span>
                                <span className="text-muted-foreground/30">•</span>
                                <span className="flex items-center gap-1.5"><Calendar className="w-4 h-4" /> TENURE: {details.info.business_age_months} Months</span>
                                <span className="text-muted-foreground/30">•</span>
                                <span className="flex items-center gap-1.5 text-primary"><Zap className="w-4 h-4" /> SCORE: {details.info.credit_score || "N/A"}</span>
                            </div>
                        </div>
                        <div className="flex gap-3">
                           <Button className="rounded-2xl gap-2 font-bold bg-primary text-primary-foreground h-12 px-6 shadow-lg shadow-primary/20">
                             <DownloadCloud className="w-5 h-5" /> Export Data PII
                           </Button>
                           <Button variant="outline" className="rounded-2xl h-12 px-5 bg-background/50 border-border">
                             <ExternalLink className="w-5 h-5" />
                           </Button>
                        </div>
                    </div>
                 </CardHeader>
               </Card>

               <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mt-8">
                 {/* UPI Chart */}
                 <Card className="gsap-fade-up shadow-2xl border-border bg-card/40 backdrop-blur-xl rounded-[32px] overflow-hidden">
                     <CardHeader className="bg-muted/30 border-b">
                         <CardTitle className="flex items-center gap-2 text-lg"><Activity className="h-5 w-5 text-indigo-400"/> UPI Flux Capacity</CardTitle>
                     </CardHeader>
                     <CardContent className="p-4 pb-2">
                        {details.upi_timeline.length === 0 ? (
                           <div className="h-full flex items-center justify-center text-muted-foreground bg-muted/20 rounded-2xl border border-dashed border-border italic">No UPI Activity Node Detected</div>
                        ) : (
                          <div style={{ width: "100%", height: 300 }}>
                          <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={details.upi_timeline} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                              <defs>
                                <linearGradient id="colorUpi" x1="0" y1="0" x2="0" y2="1">
                                  <stop offset="5%" stopColor="#6366f1" stopOpacity={0.4}/>
                                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0}/>
                                </linearGradient>
                              </defs>
                              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--muted-foreground))" strokeOpacity={0.1} />
                              <XAxis dataKey="date" tick={{fontSize: 10}} tickMargin={10} minTickGap={30} stroke="hsl(var(--muted-foreground))" strokeOpacity={0.5} axisLine={false} />
                              <YAxis tickFormatter={(val) => `₹${(val/1000).toFixed(0)}k`} width={60} tick={{fontSize: 10}} stroke="hsl(var(--muted-foreground))" strokeOpacity={0.5} axisLine={false} />
                              <Tooltip 
                                cursor={{ stroke: '#6366f1', strokeWidth: 2 }}
                                formatter={(val: number) => [`₹${val.toLocaleString()}`, "Volume"]}
                                contentStyle={{ 
                                  backgroundColor: 'rgba(var(--background), 0.8)', 
                                  backdropFilter: 'blur(12px)',
                                  borderRadius: '20px', 
                                  border: '1px solid hsl(var(--border))', 
                                  boxShadow: '0 20px 25px -5px rgb(0 0 0 / 0.1)',
                                  padding: '12px'
                                }}
                              />
                              <Area type="monotone" dataKey="daily_volume" stroke="#6366f1" strokeWidth={4} fillOpacity={1} fill="url(#colorUpi)" animationDuration={1500} />
                            </AreaChart>
                          </ResponsiveContainer>
                          </div>
                        )}
                     </CardContent>
                 </Card>

                 {/* Eway Chart */}
                 <Card className="gsap-fade-up shadow-2xl border-border bg-card/40 backdrop-blur-xl rounded-[32px] overflow-hidden">
                     <CardHeader className="bg-muted/30 border-b">
                         <CardTitle className="flex items-center gap-2 text-lg"><PackageOpen className="h-5 w-5 text-amber-500"/> Logistics Velocity Index</CardTitle>
                     </CardHeader>
                     <CardContent className="p-4 pb-2">
                        {details.ewb_timeline.length === 0 ? (
                           <div className="h-full flex items-center justify-center text-muted-foreground bg-muted/20 rounded-2xl border border-dashed border-border italic">No E-Way Bill Logs Found</div>
                        ) : (
                          <div style={{ width: "100%", height: 300 }}>
                          <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={details.ewb_timeline} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--muted-foreground))" strokeOpacity={0.1} />
                              <XAxis dataKey="date" tick={{fontSize: 10}} tickMargin={10} minTickGap={30} stroke="hsl(var(--muted-foreground))" strokeOpacity={0.5} axisLine={false} />
                              <YAxis tickFormatter={(val) => `₹${(val/1000).toFixed(0)}k`} width={60} tick={{fontSize: 10}} stroke="hsl(var(--muted-foreground))" strokeOpacity={0.5} axisLine={false} />
                              <Tooltip 
                                cursor={{ stroke: '#f59e0b', strokeWidth: 2 }}
                                formatter={(val: number) => [`₹${val.toLocaleString()}`, "Logistics Value"]}
                                contentStyle={{ 
                                  backgroundColor: 'rgba(var(--background), 0.8)', 
                                  backdropFilter: 'blur(12px)',
                                  borderRadius: '20px', 
                                  border: '1px solid hsl(var(--border))', 
                                  padding: '12px'
                                }}
                              />
                              <Line type="stepAfter" dataKey="daily_ewb_volume" stroke="#f59e0b" strokeWidth={4} dot={false} animationDuration={1500} />
                            </LineChart>
                          </ResponsiveContainer>
                          </div>
                        )}
                     </CardContent>
                 </Card>
               </div>

               <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mt-8 pb-12">
                 {/* Raw UPI Feed */}
                 <Card className="gsap-fade-up shadow-2xl border-border bg-card/40 backdrop-blur-xl rounded-[32px] h-[550px] flex flex-col overflow-hidden">
                     <CardHeader className="p-6 border-b bg-muted/30">
                         <div className="flex justify-between items-center">
                             <CardTitle className="text-xl font-bold flex items-center gap-2">
                                <Zap className="w-5 h-5 text-primary" /> UPI Raw Signal Ledger
                             </CardTitle>
                             <Button variant="ghost" size="sm" className="rounded-xl"><Filter className="w-4 h-4" /></Button>
                         </div>
                     </CardHeader>
                     <CardContent className="p-0 overflow-auto flex-1 scrollbar-thin scrollbar-thumb-primary/10">
                        <Table>
                          <TableHeader className="bg-background/90 sticky top-0 shadow-sm z-10">
                            <TableRow className="hover:bg-transparent border-border">
                              <TableHead className="text-[10px] font-bold tracking-widest pl-8 uppercase">Timestamp</TableHead>
                              <TableHead className="text-[10px] font-bold tracking-widest uppercase">Magnitude</TableHead>
                              <TableHead className="text-[10px] font-bold tracking-widest text-center uppercase">Signal</TableHead>
                              <TableHead className="text-[10px] font-bold tracking-widest uppercase pr-8">Counterparty Node</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {details.recent_upi.slice(0, 50).map((r, i) => (
                               <TableRow key={i} className="hover:bg-primary/5 border-border/50 group/row">
                                  <TableCell className="py-4 pl-8">
                                      <span className="text-[11px] font-mono text-muted-foreground bg-muted/50 px-2 py-0.5 rounded leading-none shrink-0 border border-border/50 whitespace-nowrap">
                                          {(r.timestamp || r.date || "").split(" ")[0]}
                                      </span>
                                  </TableCell>
                                  <TableCell className="font-bold text-sm tracking-tight text-foreground">₹{r.amount.toLocaleString()}</TableCell>
                                  <TableCell className="text-center">
                                    <div className="flex justify-center">
                                        {r.direction?.toLowerCase() === "inbound" ? 
                                           <div className="flex items-center text-emerald-500 font-black text-[10px] bg-emerald-500/10 border border-emerald-500/20 px-2 py-1 rounded-lg">
                                               <ArrowDownRight className="h-3 w-3 mr-0.5" /> IN
                                           </div> : 
                                           <div className="flex items-center text-rose-500 font-black text-[10px] bg-rose-500/10 border border-rose-500/20 px-2 py-1 rounded-lg">
                                               <ArrowUpRight className="h-3 w-3 mr-0.5" /> OUT
                                           </div>
                                        }
                                    </div>
                                  </TableCell>
                                  <TableCell className="pr-8">
                                      <div className="flex items-center gap-2 max-w-[160px]">
                                          <div className="w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center shrink-0">
                                              <LinkIcon className="w-3 h-3 text-primary" />
                                          </div>
                                          <span className="text-[11px] font-mono text-muted-foreground truncate group-hover/row:text-foreground transition-colors" title={r.counterparty_vpa || "Unknown"}>
                                              {(r.counterparty_vpa || "anonymous@idfc").split("@")[0]}
                                          </span>
                                      </div>
                                  </TableCell>
                               </TableRow>
                            ))}
                            {details.recent_upi.length === 0 && <TableRow><TableCell colSpan={4} className="text-center py-16 text-muted-foreground italic">NODE_HISTORY_EMPTY</TableCell></TableRow>}
                          </TableBody>
                        </Table>
                     </CardContent>
                 </Card>

                 {/* Raw EWB Feed */}
                 <Card className="gsap-fade-up shadow-2xl border-border bg-card/40 backdrop-blur-xl rounded-[32px] h-[550px] flex flex-col overflow-hidden">
                     <CardHeader className="p-6 border-b bg-muted/30">
                         <div className="flex justify-between items-center">
                             <CardTitle className="text-xl font-bold flex items-center gap-2">
                                <PackageOpen className="w-5 h-5 text-amber-500" /> Logistics Supply Chain
                             </CardTitle>
                             <Button variant="ghost" size="sm" className="rounded-xl"><Filter className="w-4 h-4" /></Button>
                         </div>
                     </CardHeader>
                     <CardContent className="p-0 overflow-auto flex-1 scrollbar-thin scrollbar-thumb-amber-500/10">
                        <Table>
                          <TableHeader className="bg-background/90 sticky top-0 shadow-sm z-10">
                            <TableRow className="hover:bg-transparent border-border">
                              <TableHead className="text-[10px] font-bold tracking-widest pl-8 uppercase">Dispatch</TableHead>
                              <TableHead className="text-[10px] font-bold tracking-widest uppercase">Value</TableHead>
                              <TableHead className="text-[10px] font-bold tracking-widest text-center uppercase">HSN</TableHead>
                              <TableHead className="text-[10px] font-bold tracking-widest uppercase pr-8">Counterparty Node</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {details.recent_ewb.slice(0, 50).map((r, i) => (
                               <TableRow key={i} className="hover:bg-amber-500/5 border-border/50 group/row">
                                  <TableCell className="py-4 pl-8">
                                      <span className="text-[11px] font-mono text-muted-foreground bg-muted/50 px-2 py-0.5 rounded leading-none shrink-0 border border-border/50">
                                          {(r.timestamp || "").split(" ")[0]}
                                      </span>
                                  </TableCell>
                                  <TableCell className="font-bold text-sm tracking-tight text-foreground">₹{r.totalValue.toLocaleString()}</TableCell>
                                  <TableCell className="text-center">
                                      <Badge variant="outline" className="text-[9px] font-black border-amber-500/20 bg-amber-500/5 text-amber-500 h-5">
                                          {r.mainHsnCode}
                                      </Badge>
                                  </TableCell>
                                  <TableCell className="pr-8">
                                      <div className="flex items-center gap-2 max-w-[160px]">
                                          {r.toGstin === details.info.gstin ? 
                                             <div className="flex items-center gap-1.5 overflow-hidden">
                                                <div className="w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
                                                <span className="text-[10px] text-muted-foreground truncate font-mono" title={r.fromGstin}>FROM: {r.fromGstin}</span>
                                             </div> : 
                                             <div className="flex items-center gap-1.5 overflow-hidden">
                                                <div className="w-2 h-2 rounded-full bg-amber-500 shrink-0" />
                                                <span className="text-[10px] text-muted-foreground truncate font-mono" title={r.toGstin}>TO: {r.toGstin}</span>
                                             </div>
                                          }
                                      </div>
                                  </TableCell>
                               </TableRow>
                            ))}
                            {details.recent_ewb.length === 0 && <TableRow><TableCell colSpan={4} className="text-center py-16 text-muted-foreground italic">LOGISTICS_GRAPH_EMPTY</TableCell></TableRow>}
                          </TableBody>
                        </Table>
                     </CardContent>
                 </Card>
               </div>
             </>
           )}
        </div>
      )}
    </div>
  );
}
