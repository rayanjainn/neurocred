import { NextRequest, NextResponse } from "next/server";

const WA_PHONE_ID = "***REMOVED***";
const WA_TOKEN =
  "***REMOVED***";
const RECIPIENT = "***REMOVED***"; // Must be a verified test recipient in Meta Developer Console

// Priority order for sorting — lower number = higher priority
const STATUS_PRIORITY: Record<string, number> = {
  overdue: 0,
  due: 1,
  upcoming: 2,
  completed: 3,
};

function fmtDate(d: string) {
  return new Date(d).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function buildAlertMessage(reminders: any[]): string {
  // --- Count by status ---
  const overdue = reminders.filter((r) => r.status === "overdue");
  const due = reminders.filter((r) => r.status === "due");
  const upcoming = reminders.filter((r) => r.status === "upcoming");

  // --- Top 5 action items sorted by priority then due date ---
  const actionItems = [...overdue, ...due]
    .sort((a, b) => {
      const priorityDiff =
        (STATUS_PRIORITY[a.status] ?? 9) - (STATUS_PRIORITY[b.status] ?? 9);
      if (priorityDiff !== 0) return priorityDiff;
      // secondary sort: earliest due date first
      return new Date(a.due_date).getTime() - new Date(b.due_date).getTime();
    })
    .slice(0, 5)
    .map((r) => {
      const icon = r.status === "overdue" ? "🔴" : "🟡";
      const amount =
        r.amount
          ? ` · ₹${Number(r.amount).toLocaleString("en-IN")}`
          : "";
      return `${icon} ${r.title}${amount} (Due: ${fmtDate(r.due_date)})`;
    });

  const headline = overdue.length > 0 ? "Action Required" : due.length > 0 ? "Due Soon" : upcoming.length > 0 ? "Upcoming" : "No Alerts";

  // --- Header emoji reflects worst status present ---
  const headerEmoji =
    overdue.length > 0 ? "🔴" : due.length > 0 ? "🟡" : "🟢";

  const topSection =
    actionItems.length > 0
      ? `⚡ *Top Priority Items*\n${actionItems.join("\n")}\n\n`
      : `✅ *No immediate action required.*\n\n`;

  return (
    `${headerEmoji} *FinTwin Alert - ${headline}*\n\n` +
    `📊 *Your Reminder Summary*\n` +
    `🔴 Overdue:  *${overdue.length}*\n` +
    `🟡 Due Soon: *${due.length}*\n` +
    `🔵 Upcoming: *${upcoming.length}*\n\n` +
    topSection +
    `_Log in to FinTwin to take action and avoid penalties._`
  );
}

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const reminders: any[] = Array.isArray(body.reminders) ? body.reminders : [];

  const message = buildAlertMessage(reminders);

  const res = await fetch(
    `https://graph.facebook.com/v25.0/${WA_PHONE_ID}/messages`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${WA_TOKEN}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        messaging_product: "whatsapp",
        to: RECIPIENT,
        type: "text",
        text: { body: message },
      }),
    }
  );

  const data = await res.json();

  if (!res.ok) {
    return NextResponse.json(
      { error: data?.error?.message ?? "WhatsApp API error", detail: data },
      { status: res.status }
    );
  }

  return NextResponse.json({ ok: true, messageId: data?.messages?.[0]?.id });
}
