export type KPIs = {
  revenueRecovered: number; // USD cents
  callsAnswered: number;
  appointmentsBooked: number;
  conversionRate: number; // 0..1
};

export type CallsTimeseriesPoint = {
  date: string; // YYYY-MM-DD
  answered: number;
  missed: number;
  afterHoursCaptured: number;
};

export type RevenueByService = { service: string; revenueCents: number }[];

export type RecentCall = {
  id: string;
  timestamp: string; // ISO
  callerNameMasked: string; // "J*** D***"
  intent: string; // "balayage", "women's cut", etc.
  outcome: "booked" | "transferred" | "voicemail";
  durationSec: number;
  sentiment: "up" | "down";
};

export type TopService = {
  service: string;
  count: number;
  avgPriceCents: number;
};

export type DateRange = "7" | "30" | "90";