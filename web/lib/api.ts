export type TripState =
  | "INTAKE"
  | "CONSTRAINTS"
  | "SEARCH"
  | "COMPARE"
  | "TRAVELERS"
  | "RANK"
  | "PROPOSE"
  | "AWAIT_APPROVAL"
  | "BOOK"
  | "CONFIRM"
  | "FAILED"
  | "CANCELLED"
  | "EXPIRED"
  | "PARTIAL_FAILURE";

export type Traveler = {
  first_name: string;
  last_name: string;
  email?: string | null;
  date_of_birth?: string | null;
};

export type TripConstraints = {
  origin?: string | null;
  destination?: string | null;
  destination_city?: string | null;
  departure_date?: string | null;
  return_date?: string | null;
  adults: number;
  budget_usd?: number | null;
  preferences?: string[];
  preferences_text?: string | null;
  travelers: Traveler[];
};

export type FlightSegment = {
  origin: string;
  origin_name?: string | null;
  destination: string;
  destination_name?: string | null;
  departure_at: string;
  arrival_at: string;
  duration?: string | null;
  carrier: string;
  carrier_name?: string | null;
  flight_number?: string | null;
  aircraft?: string | null;
  cabin?: string | null;
  layover_city?: string | null;
};

export type LayoverInfo = {
  airport: string;
  airport_name?: string | null;
  city?: string | null;
  duration_minutes: number;
};

export type FlightOffer = {
  offer_id: string;
  source: string;
  carrier: string;
  carrier_name?: string | null;
  origin: string;
  origin_name?: string | null;
  destination: string;
  destination_name?: string | null;
  departure_at: string;
  arrival_at: string;
  duration: string;
  stops: number;
  segments?: FlightSegment[];
  layovers?: LayoverInfo[];
  cabin?: string | null;
  price_usd: number;
  currency?: string;
  deep_link?: string | null;
  raw?: { label?: string; cabin?: string; mock?: boolean; source?: string; flight_numbers?: string[] };
};

export type HotelOffer = {
  offer_id: string;
  source: string;
  hotel_id: string;
  name: string;
  city: string;
  check_in: string;
  check_out: string;
  price_usd: number;
  rating?: number | null;
  address?: string | null;
};

export type ToolCallEvent = {
  tool: string;
  status: string;
  summary: string;
  args?: Record<string, unknown>;
  latency_ms?: number | null;
  created_at?: string | null;
};

export type RankedPair = {
  flight_offer_id: string;
  hotel_offer_id: string;
  total_usd: number;
  within_budget: boolean;
  score: number;
};

export type ProposedItinerary = {
  proposal_id: string;
  flight?: FlightOffer | null;
  hotel?: HotelOffer | null;
  total_usd: number;
  within_budget: boolean;
  summary: string;
  itinerary_hash: string;
  expires_at?: string | null;
};

export type BookingRecord = {
  booking_id: string;
  kind: string;
  provider_ref: string;
  status: string;
  amount_usd: number;
};

export type DailyWeatherForecast = {
  date: string;
  temp_high_c: number;
  temp_low_c: number;
  description: string;
  precipitation_chance?: number | null;
};

export type TripResponse = {
  trip_id: string;
  state: TripState;
  constraints: TripConstraints;
  flight_offers: FlightOffer[];
  hotel_offers: HotelOffer[];
  ranked_pairs: RankedPair[];
  selected_flight_id?: string | null;
  selected_hotel_id?: string | null;
  proposal?: ProposedItinerary | null;
  weather?: { location: string; temp_c: number; description: string } | null;
  daily_weather?: DailyWeatherForecast[];
  reviews?: { place_name: string; rating: number; review_count: number } | null;
  bookings: BookingRecord[];
  tool_calls?: ToolCallEvent[];
  error?: string | null;
  error_code?: string | null;
  retryable?: boolean;
  proposal_expires_at?: string | null;
};

export type TripSummary = {
  trip_id: string;
  state: TripState;
  origin?: string | null;
  destination?: string | null;
  departure_date?: string | null;
  return_date?: string | null;
  total_usd?: number | null;
};

export type TokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
};

export type Problem = {
  title: string;
  detail: string;
  code?: string;
  status: number;
  retryable?: boolean;
};

export type AirportSearchResult = {
  iata: string;
  name: string;
  city: string;
  country: string;
  label: string;
  lat?: number | null;
  lon?: number | null;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;
  code?: string;
  retryable?: boolean;
  constructor(problem: Problem) {
    super(problem.detail || problem.title);
    this.status = problem.status;
    this.code = problem.code;
    this.retryable = problem.retryable;
  }
}

function getTokens() {
  if (typeof window === "undefined") return { access: null, refresh: null };
  return {
    access: localStorage.getItem("access_token"),
    refresh: localStorage.getItem("refresh_token"),
  };
}

export function setTokens(tokens: TokenResponse) {
  localStorage.setItem("access_token", tokens.access_token);
  localStorage.setItem("refresh_token", tokens.refresh_token);
}

export function clearTokens() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

export function isLoggedIn() {
  return Boolean(getTokens().access);
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  auth = true,
): Promise<T> {
  const headers = new Headers(options.headers || {});
  headers.set("Content-Type", "application/json");
  if (auth) {
    const { access } = getTokens();
    if (access) headers.set("Authorization", `Bearer ${access}`);
  }
  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (res.status === 401 && auth) {
    const refreshed = await tryRefresh();
    if (refreshed) return request<T>(path, options, auth);
  }
  if (!res.ok) {
    let problem: Problem = {
      title: "Request failed",
      detail: res.statusText,
      status: res.status,
    };
    try {
      problem = await res.json();
    } catch {
      /* ignore */
    }
    throw new ApiError(problem);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

async function tryRefresh(): Promise<boolean> {
  const { refresh } = getTokens();
  if (!refresh) return false;
  try {
    const tokens = await request<TokenResponse>(
      "/auth/refresh",
      { method: "POST", body: JSON.stringify({ refresh_token: refresh }) },
      false,
    );
    setTokens(tokens);
    return true;
  } catch {
    clearTokens();
    return false;
  }
}

export const api = {
  signup: (email: string, password: string, full_name?: string) =>
    request<TokenResponse>(
      "/auth/signup",
      { method: "POST", body: JSON.stringify({ email, password, full_name }) },
      false,
    ),
  login: (email: string, password: string) =>
    request<TokenResponse>(
      "/auth/login",
      { method: "POST", body: JSON.stringify({ email, password }) },
      false,
    ),
  me: () => request<{ id: string; email: string; full_name?: string }>("/auth/me"),
  searchAirports: (q: string) =>
    request<AirportSearchResult[]>(`/airports/search?q=${encodeURIComponent(q)}`, {}, false),
  listTrips: () => request<TripSummary[]>("/trips"),
  createTrip: (constraints: TripConstraints, preferences_text?: string) =>
    request<TripResponse>("/trips", {
      method: "POST",
      body: JSON.stringify({ constraints, preferences_text }),
    }),
  getTrip: (id: string) => request<TripResponse>(`/trips/${id}`),
  search: (id: string) =>
    request<TripResponse>(`/trips/${id}/search`, { method: "POST", body: "{}" }),
  select: (id: string, flight_offer_id: string, hotel_offer_id: string) =>
    request<TripResponse>(`/trips/${id}/select`, {
      method: "POST",
      body: JSON.stringify({ flight_offer_id, hotel_offer_id }),
    }),
  travelers: (id: string, travelers: Traveler[]) =>
    request<TripResponse>(`/trips/${id}/travelers`, {
      method: "PUT",
      body: JSON.stringify({ travelers }),
    }),
  approve: (
    id: string,
    proposal_id: string,
    itinerary_hash: string,
    acknowledge_over_budget = false,
  ) =>
    request<TripResponse>(`/trips/${id}/approve`, {
      method: "POST",
      body: JSON.stringify({
        proposal_id,
        itinerary_hash,
        acknowledge_over_budget,
      }),
    }),
  reject: (id: string, feedback?: string, research = true) =>
    request<TripResponse>(`/trips/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ feedback, research }),
    }),
};
