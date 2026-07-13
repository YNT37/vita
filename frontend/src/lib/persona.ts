export type PersonaId = "butler" | "servant" | "sassy" | "lover";

export const PERSONA_LABELS: Record<PersonaId, string> = {
  butler: "管家",
  servant: "奴才",
  sassy: "毒舌闺蜜",
  lover: "暖心恋人",
};

export const PERSONA_OPTIONS: PersonaId[] = ["butler", "servant", "sassy", "lover"];

export type ParseAction = {
  intent: "transaction" | "reminder" | "balance";
  data: Record<string, unknown>;
};

export type ParseResult = {
  intent: "transaction" | "reminder" | "balance" | "batch" | "unknown";
  data: Record<string, unknown>;
  actions?: ParseAction[];
};

export type ChatMsg = { role: "user" | "assistant"; content: string };
