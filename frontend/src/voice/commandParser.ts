export type VoiceCommandType = "navigate" | "action";

export type ParsedCommand = {
  type: VoiceCommandType;
  target: string;
};

const normalize = (value: string) =>
  value
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();

const includesAny = (text: string, keywords: string[]) =>
  keywords.some((keyword) => text.includes(keyword));

export function parseCommand(rawText: string): ParsedCommand | null {
  const text = normalize(rawText);

  if (!text) return null;

  if (includesAny(text, ["dashboard", "home", "overview"])) {
    return { type: "navigate", target: "dashboard" };
  }

  if (includesAny(text, ["score report", "report", "reports", "decision", "decisions", "audit log", "audit"])) {
    return { type: "navigate", target: "reports" };
  }

  if (includesAny(text, ["analytics", "analytic", "analysis", "strategy", "strategy lab", "signal trend", "signal trends", "topology"])) {
    return { type: "navigate", target: "analytics" };
  }

  if (includesAny(text, ["alert", "alerts", "notification", "notifications", "dispute", "disputes", "queue", "fraud queue"])) {
    return { type: "navigate", target: "alerts" };
  }

  if (includesAny(text, ["loan", "loans", "loan queue"])) {
    return { type: "navigate", target: "loans" };
  }

  if (includesAny(text, ["reminder", "reminders"])) {
    return { type: "navigate", target: "reminders" };
  }

  if (includesAny(text, ["guide", "help", "support guide"])) {
    return { type: "navigate", target: "guide" };
  }

  if (includesAny(text, ["shap", "shap explorer"])) {
    return { type: "navigate", target: "shap_explorer" };
  }

  if (includesAny(text, ["data explorer", "data", "dataset"])) {
    return { type: "navigate", target: "data_explorer" };
  }

  if (includesAny(text, ["threshold", "thresholds"])) {
    return { type: "navigate", target: "thresholds" };
  }

  if (includesAny(text, ["fraud topology", "network map", "topology map"])) {
    return { type: "navigate", target: "fraud_topology" };
  }

  if (includesAny(text, ["users", "user management"])) {
    return { type: "navigate", target: "users" };
  }

  if (includesAny(text, ["api key", "api keys", "keys"])) {
    return { type: "navigate", target: "api_keys" };
  }

  if (includesAny(text, ["banks", "bank list"])) {
    return { type: "navigate", target: "banks" };
  }

  if (includesAny(text, ["show my risk", "my risk", "risk"])) {
    return { type: "action", target: "risk" };
  }

  if (includesAny(text, ["open digital twin", "digital twin", "open twin"])) {
    return { type: "action", target: "open_twin" };
  }

  if (includesAny(text, ["talk to my twin", "talk to twin", "twin chat", "chat with twin"])) {
    return { type: "action", target: "open_twin_chat" };
  }

  if (includesAny(text, ["toggle dark mode", "dark mode", "light mode", "toggle theme", "change theme"])) {
    return { type: "action", target: "toggle_dark_mode" };
  }

  return null;
}
