"use client";
import { cn } from "@/dib/utils";

export type RiskBand =
  | "very_low_risk"
  | "low_risk"
  | "medium_risk"
  | "high_risk";

const BAND_CONFIG: Record<
  RiskBand,
  { label: string; color: string; bg: string }
> = {
  very_low_risk: {
    label: "Very Low Risk",
    color: "text-[#a8d900]",
    bg: "bg-[rgba(200,255,0,0.1)] border border-[rgba(200,255,0,0.24)]",
  },
  low_risk: {
    label: "Low Risk",
    color: "text-[#00c8d4]",
    bg: "bg-[rgba(0,240,255,0.1)] border border-[rgba(0,240,255,0.24)]",
  },
  medium_risk: {
    label: "Medium Risk",
    color: "text-[#e09500]",
    bg: "bg-[rgba(255,170,0,0.1)] border border-[rgba(255,170,0,0.24)]",
  },
  high_risk: {
    label: "High Risk",
    color: "text-[#e0003a]",
    bg: "bg-[rgba(255,0,64,0.1)] border border-[rgba(255,0,64,0.24)]",
  },
};

export function RiskBadge({
  band,
  className,
}: {
  band: string;
  className?: string;
}) {
  const cfg = BAND_CONFIG[band as RiskBand] ?? {
    label: band,
    color: "text-muted-foreground",
    bg: "bg-muted",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-semibold uppercase tracking-[0.1em]",
        cfg.bg,
        cfg.color,
        className,
      )}
    >
      {cfg.label}
    </span>
  );
}

// Format INR currency
export function formatINR(amount: number) {
  if (amount >= 10000000) return `₹${(amount / 10000000).toFixed(1)}Cr`;
  if (amount >= 100000) return `₹${(amount / 100000).toFixed(1)}L`;
  if (amount >= 1000) return `₹${(amount / 1000).toFixed(0)}K`;
  return `₹${amount}`;
}

// Score gauge
export function ScoreGauge({
  score,
  size = 180,
}: {
  score: number;
  size?: number;
}) {
  const min = 300,
    max = 900;
  const pct = (score - min) / (max - min);
  const angle = -135 + pct * 270; // -135 to 135 degrees

  const color =
    score >= 700
      ? "#c8ff00"
      : score >= 600
        ? "#00f0ff"
        : score >= 500
          ? "#ffaa00"
          : "#ff0040";

  const cx = size / 2,
    cy = size / 2;
  const r = size * 0.38;
  const strokeWidth = size * 0.07;

  // Arc path helper
  function polarToCart(angleDeg: number) {
    const rad = ((angleDeg - 90) * Math.PI) / 180;
    return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
  }

  function arcPath(startDeg: number, endDeg: number) {
    const s = polarToCart(startDeg);
    const e = polarToCart(endDeg);
    const large = endDeg - startDeg > 180 ? 1 : 0;
    return `M ${s.x} ${s.y} A ${r} ${r} 0 ${large} 1 ${e.x} ${e.y}`;
  }

  const startAngle = -135 + 90; // offset by 90 since our polar uses -90
  const trackStart = -135 + 90;
  const trackEnd = 135 + 90;
  const fillEnd = -135 + 90 + pct * 270;

  return (
    <svg
      width={size}
      height={size * 0.9}
      viewBox={`0 0 ${size} ${size * 0.9}`}
      className="overflow-visible"
    >
      <defs>
        <filter id="gaugeShadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="4" stdDeviation="6" floodColor={color} floodOpacity="0.4" />
        </filter>
      </defs>
      {/* Track */}
      <path
        d={arcPath(trackStart, trackEnd)}
        fill="none"
        stroke="currentColor"
        className="text-muted/50"
        strokeWidth={strokeWidth}
        strokeLinecap="round"
      />
      {/* Fill */}
      <path
        d={arcPath(trackStart, fillEnd)}
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        filter="url(#gaugeShadow)"
        className="transition-all duration-1000 ease-out"
      />
      {/* Score text */}
      <text
        x={cx}
        y={cy * 0.95}
        textAnchor="middle"
        fontSize={size * 0.22}
        fontWeight="800"
        fill={color}
        style={{ textShadow: `0px 4px 12px ${color}40` }}
      >
        {score}
      </text>
      <text
        x={cx}
        y={cy * 0.95 + size * 0.12}
        textAnchor="middle"
        fontSize={size * 0.07}
        className="fill-muted-foreground font-medium uppercase tracking-widest"
      >
        out of 900
      </text>
    </svg>
  );
}

// Stat card
export function StatCard({
  label,
  value,
  sub,
  icon: Icon,
  accent = false,
  className,
}: {
  label: string;
  value: string | number;
  sub?: string;
  icon?: React.ElementType;
  accent?: boolean;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-xl p-4 border",
        accent
          ? "bg-primary text-primary-foreground border-primary"
          : "bg-card text-card-foreground border-border",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <p
            className={cn(
              "text-xs font-medium uppercase tracking-wide mb-1",
              accent ? "text-white/70" : "text-muted-foreground",
            )}
          >
            {label}
          </p>
          <p
            className={cn(
              "text-2xl font-bold leading-none",
              accent ? "text-white" : "text-foreground",
            )}
          >
            {value}
          </p>
          {sub && (
            <p
              className={cn(
                "text-xs mt-1",
                accent ? "text-white/60" : "text-muted-foreground",
              )}
            >
              {sub}
            </p>
          )}
        </div>
        {Icon && (
          <div
            className={cn(
              "w-8 h-8 rounded-lg flex items-center justify-center shrink-0",
              accent ? "bg-white/20" : "bg-accent",
            )}
          >
            <Icon
              className={cn("w-4 h-4", accent ? "text-white" : "text-primary")}
            />
          </div>
        )}
      </div>
    </div>
  );
}

// Page header
export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-4 mb-6">
      <div>
        <h1 className="text-xl font-bold text-foreground text-balance">
          {title}
        </h1>
        {description && (
          <p className="text-sm text-muted-foreground mt-0.5 leading-relaxed">
            {description}
          </p>
        )}
      </div>
      {actions && (
        <div className="shrink-0 flex items-center gap-2">{actions}</div>
      )}
    </div>
  );
}

// Status badge
const STATUS_CONFIG: Record<string, { label: string; className: string }> = {
  submitted: {
    label: "Submitted",
    className: "bg-[rgba(0,240,255,0.1)] text-[#00c8d4] border border-[rgba(0,240,255,0.24)]",
  },
  bank_reviewing: {
    label: "Bank Reviewing",
    className: "bg-[rgba(0,240,255,0.1)] text-[#00c8d4] border border-[rgba(0,240,255,0.24)]",
  },
  permission_requested: {
    label: "Permission Requested",
    className: "bg-[rgba(255,170,0,0.1)] text-[#e09500] border border-[rgba(255,170,0,0.24)]",
  },
  data_shared: {
    label: "Data Shared",
    className: "bg-[rgba(0,240,255,0.1)] text-[#00c8d4] border border-[rgba(0,240,255,0.24)]",
  },
  approved: {
    label: "Approved",
    className: "bg-[rgba(200,255,0,0.1)] text-[#a8d900] border border-[rgba(200,255,0,0.24)]",
  },
  denied: {
    label: "Denied",
    className: "bg-[rgba(255,0,64,0.1)] text-[#e0003a] border border-[rgba(255,0,64,0.24)]",
  },
  active: {
    label: "Active",
    className: "bg-[rgba(200,255,0,0.1)] text-[#a8d900] border border-[rgba(200,255,0,0.24)]",
  },
  open: {
    label: "Open",
    className: "bg-[rgba(255,170,0,0.1)] text-[#e09500] border border-[rgba(255,170,0,0.24)]",
  },
  under_review: {
    label: "Under Review",
    className: "bg-[rgba(0,240,255,0.1)] text-[#00c8d4] border border-[rgba(0,240,255,0.24)]",
  },
  resolved: {
    label: "Resolved",
    className: "bg-[rgba(200,255,0,0.1)] text-[#a8d900] border border-[rgba(200,255,0,0.24)]",
  },
  pending: {
    label: "Pending",
    className: "bg-[rgba(255,170,0,0.1)] text-[#e09500] border border-[rgba(255,170,0,0.24)]",
  },
  granted: {
    label: "Granted",
    className: "bg-[rgba(200,255,0,0.1)] text-[#a8d900] border border-[rgba(200,255,0,0.24)]",
  },
  revoked: {
    label: "Revoked",
    className: "bg-[rgba(255,0,64,0.1)] text-[#e0003a] border border-[rgba(255,0,64,0.24)]",
  },
  suspended: {
    label: "Suspended",
    className: "bg-[rgba(255,0,64,0.1)] text-[#e0003a] border border-[rgba(255,0,64,0.24)]",
  },
  upcoming: {
    label: "Upcoming",
    className: "bg-[rgba(0,240,255,0.1)] text-[#00c8d4] border border-[rgba(0,240,255,0.24)]",
  },
  due: {
    label: "Due",
    className: "bg-[rgba(255,170,0,0.1)] text-[#e09500] border border-[rgba(255,170,0,0.24)]",
  },
  overdue: {
    label: "Overdue",
    className: "bg-[rgba(255,0,64,0.1)] text-[#e0003a] border border-[rgba(255,0,64,0.24)]",
  },
  completed: {
    label: "Completed",
    className: "bg-[rgba(200,255,0,0.1)] text-[#a8d900] border border-[rgba(200,255,0,0.24)]",
  },
};

export function StatusBadge({
  status,
  className,
}: {
  status: string;
  className?: string;
}) {
  const cfg = STATUS_CONFIG[status] ?? {
    label: status,
    className: "bg-muted text-muted-foreground",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-semibold uppercase tracking-[0.1em]",
        cfg.className,
        className,
      )}
    >
      {cfg.label}
    </span>
  );
}
