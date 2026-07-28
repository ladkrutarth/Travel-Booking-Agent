"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ApiError,
  FlightOffer,
  LayoverInfo,
  ToolCallEvent,
  Traveler,
  TripResponse,
  api,
  isLoggedIn,
} from "@/lib/api";
import { FlightRouteMap } from "@/components/FlightRouteMap";

function Stepper({ state }: { state: string }) {
  const steps = ["Search", "Compare", "Travelers", "Approve", "Confirm"];
  const active =
    state === "COMPARE"
      ? 1
      : state === "TRAVELERS"
        ? 2
        : state === "AWAIT_APPROVAL" || state === "BOOK"
          ? 3
          : state === "CONFIRM"
            ? 4
            : state === "PARTIAL_FAILURE" || state === "FAILED" || state === "EXPIRED"
              ? 3
              : 0;
  return (
    <div className="stepper">
      {steps.map((label, i) => (
        <span key={label} className={`step ${i === active ? "active" : i < active ? "done" : ""}`}>
          {i + 1}. {label}
        </span>
      ))}
    </div>
  );
}

function formatDateTime(iso: string) {
  try {
    return new Date(iso).toLocaleString([], {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function formatDuration(isoDuration: string) {
  const m = isoDuration.match(/PT(?:(\d+)H)?(?:(\d+)M)?/);
  if (!m) return isoDuration;
  const h = m[1] ? `${m[1]}h` : "";
  const min = m[2] ? `${m[2]}m` : "";
  return `${h} ${min}`.trim() || isoDuration;
}

function formatMinutes(mins: number) {
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  if (h && m) return `${h}h ${m}m`;
  if (h) return `${h}h`;
  return `${m}m`;
}

function layoverSummary(layovers: LayoverInfo[] | undefined, stops: number) {
  if (!layovers?.length) {
    return stops === 0 ? "Nonstop" : `${stops} stop${stops > 1 ? "s" : ""}`;
  }
  return layovers
    .map((l) => `${l.city || l.airport} ${formatMinutes(l.duration_minutes)}`)
    .join(" · ");
}

function AgentToolsPanel({
  toolCalls,
  busy,
}: {
  toolCalls: ToolCallEvent[];
  busy: boolean;
}) {
  return (
    <aside className="panel tool-panel fade-in">
      <h2 style={{ marginTop: 0, fontFamily: "Fraunces, Georgia, serif" }}>Agent tool calls</h2>
      <p style={{ color: "var(--muted)", marginTop: 0, fontFamily: "Source Sans 3, sans-serif" }}>
        Live trace of tools the booking agent invoked.
      </p>
      {busy && (
        <div className="tool-row">
          <span className="tool-status started">running</span>
          <div>
            <div className="tool-name">agent.loop</div>
            <div className="tool-summary">Waiting for tool responses…</div>
          </div>
          <span>—</span>
        </div>
      )}
      {!toolCalls.length && !busy && (
        <p className="empty" style={{ padding: "1rem 0" }}>
          No tool calls yet. Run a search to see `search_google_flights`, `search_kayak`, hotel site tools, and more.
        </p>
      )}
      {toolCalls.map((call, idx) => (
        <div className="tool-row" key={`${call.tool}-${idx}-${call.status}`}>
          <span className={`tool-status ${call.status}`}>{call.status}</span>
          <div>
            <div className="tool-name">{call.tool}()</div>
            <div className="tool-summary">{call.summary}</div>
            {call.args && Object.keys(call.args).length > 0 && (
              <div className="tool-args">{JSON.stringify(call.args)}</div>
            )}
          </div>
          <span>{call.latency_ms != null ? `${call.latency_ms}ms` : ""}</span>
        </div>
      ))}
    </aside>
  );
}

function sourceLabel(source: string) {
  return source.replace(/_/g, " ").replace(".com", ".com");
}

function FlightCard({
  flight,
  selected,
  expanded,
  onSelect,
  onToggleExpand,
}: {
  flight: FlightOffer;
  selected: boolean;
  expanded: boolean;
  onSelect: () => void;
  onToggleExpand: () => void;
}) {
  const label = flight.raw?.label || (flight.stops === 0 ? "Nonstop" : `${flight.stops}-stop`);
  const cabin = (flight.cabin || flight.raw?.cabin || "ECONOMY").replace(/_/g, " ");
  const airline = flight.carrier_name || flight.carrier;
  const segments = flight.segments?.length ? flight.segments : [];
  const flightNumbers =
    segments.map((s) => s.flight_number).filter(Boolean).join(", ") ||
    flight.raw?.flight_numbers?.join(", ") ||
    "—";
  const currency = flight.currency || "USD";

  return (
    <div className={`offer flight-offer ${selected ? "selected" : ""}`}>
      <button type="button" className="flight-offer-main" onClick={onSelect}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", flexWrap: "wrap" }}>
          <strong>
            {airline} · {label}
          </strong>
          <span className="pill">{sourceLabel(flight.source)}</span>
          <span className="pill">{cabin}</span>
          {flight.raw?.mock ? <span className="pill warn">Mock fares</span> : null}
        </div>
        <div className="offer-meta">
          <span>
            {formatDateTime(flight.departure_at)} {flight.origin}
            {flight.origin_name ? ` (${flight.origin_name})` : ""} → {formatDateTime(flight.arrival_at)}{" "}
            {flight.destination}
            {flight.destination_name ? ` (${flight.destination_name})` : ""}
          </span>
        </div>
        <div className="offer-meta">
          <span>Flights {flightNumbers}</span>
          <span>{formatDuration(flight.duration)} total</span>
          <span>
            {flight.stops === 0
              ? "Nonstop"
              : `${flight.stops} stop${flight.stops > 1 ? "s" : ""} · ${layoverSummary(flight.layovers, flight.stops)}`}
          </span>
        </div>
        <div className="offer-price">
          {currency} ${flight.price_usd.toFixed(0)}
          <span className="offer-price-source"> via {sourceLabel(flight.source)}</span>
        </div>
      </button>
      <div className="flight-offer-actions">
        <button
          type="button"
          className="btn btn-secondary flight-expand-btn"
          onClick={(e) => {
            e.stopPropagation();
            onToggleExpand();
          }}
        >
          {expanded ? "Hide segments" : "Show segments"}
        </button>
        {flight.deep_link ? (
          <a
            className="flight-deeplink"
            href={flight.deep_link}
            target="_blank"
            rel="noreferrer"
            onClick={(e) => e.stopPropagation()}
          >
            Source link
          </a>
        ) : null}
      </div>
      {expanded && (
        <ol className="segment-timeline">
          {segments.map((seg, i) => {
            const layover = flight.layovers?.[i];
            return (
              <li key={`${seg.flight_number}-${i}`}>
                <div className="segment-head">
                  <strong>{seg.flight_number || `${seg.carrier} —`}</strong>
                  <span>
                    {seg.carrier_name || seg.carrier}
                    {seg.aircraft ? ` · ${seg.aircraft}` : ""}
                    {seg.cabin ? ` · ${seg.cabin.replace(/_/g, " ")}` : ""}
                  </span>
                </div>
                <div className="segment-body">
                  <div>
                    <div className="segment-time">{formatDateTime(seg.departure_at)}</div>
                    <div>
                      {seg.origin} — {seg.origin_name || seg.origin}
                    </div>
                  </div>
                  <div className="segment-duration">{formatDuration(seg.duration || "")}</div>
                  <div>
                    <div className="segment-time">{formatDateTime(seg.arrival_at)}</div>
                    <div>
                      {seg.destination} — {seg.destination_name || seg.destination}
                    </div>
                  </div>
                </div>
                {layover ? (
                  <div className="segment-layover">
                    Layover at {layover.city || layover.airport}
                    {layover.airport_name ? ` (${layover.airport_name})` : ""} ·{" "}
                    {formatMinutes(layover.duration_minutes)}
                  </div>
                ) : null}
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}

export default function TripDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const tripId = params.id;
  const [trip, setTrip] = useState<TripResponse | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [flightId, setFlightId] = useState<string>("");
  const [hotelId, setHotelId] = useState<string>("");
  const [ackBudget, setAckBudget] = useState(false);
  const [expiryLeft, setExpiryLeft] = useState<string>("");
  const [flightSort, setFlightSort] = useState<"price" | "duration" | "stops">("price");
  const [expandedFlightId, setExpandedFlightId] = useState<string>("");
  const [hoveredFlightId, setHoveredFlightId] = useState<string>("");

  const load = useCallback(async () => {
    const data = await api.getTrip(tripId);
    setTrip(data);
    setFlightId(data.selected_flight_id || "");
    setHotelId(data.selected_hotel_id || "");
  }, [tripId]);

  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace("/login");
      return;
    }
    load().catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load trip"));
  }, [load, router]);

  useEffect(() => {
    if (!trip?.proposal_expires_at) return;
    const tick = () => {
      const ms = new Date(trip.proposal_expires_at!).getTime() - Date.now();
      if (ms <= 0) setExpiryLeft("Expired");
      else {
        const m = Math.floor(ms / 60000);
        const s = Math.floor((ms % 60000) / 1000);
        setExpiryLeft(`${m}m ${s}s`);
      }
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [trip?.proposal_expires_at]);

  const travelersCount = trip?.constraints.adults || 1;
  const travelerDefaults = useMemo(() => {
    const existing = trip?.constraints.travelers || [];
    return Array.from({ length: travelersCount }, (_, i) => existing[i] || {
      first_name: "",
      last_name: "",
      email: "",
      date_of_birth: "",
    });
  }, [trip, travelersCount]);

  const sortedFlights = useMemo(() => {
    const list = [...(trip?.flight_offers || [])];
    const durationMinutes = (d: string) => {
      const m = d.match(/PT(?:(\d+)H)?(?:(\d+)M)?/);
      if (!m) return 9999;
      return Number(m[1] || 0) * 60 + Number(m[2] || 0);
    };
    list.sort((a, b) => {
      if (flightSort === "price") return a.price_usd - b.price_usd;
      if (flightSort === "stops") return a.stops - b.stops || a.price_usd - b.price_usd;
      return durationMinutes(a.duration) - durationMinutes(b.duration) || a.price_usd - b.price_usd;
    });
    return list;
  }, [trip?.flight_offers, flightSort]);

  const mapFlight = useMemo(() => {
    const id = hoveredFlightId || flightId;
    return sortedFlights.find((f) => f.offer_id === id) || sortedFlights[0] || null;
  }, [sortedFlights, flightId, hoveredFlightId]);

  async function run(action: () => Promise<TripResponse>) {
    setBusy(true);
    setError("");
    try {
      const next = await action();
      setTrip(next);
      setFlightId(next.selected_flight_id || flightId);
      setHotelId(next.selected_hotel_id || hotelId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Action failed");
      try {
        await load();
      } catch {
        /* ignore */
      }
    } finally {
      setBusy(false);
    }
  }

  async function onSelect() {
    if (!flightId || !hotelId) {
      setError("Select both a flight and a hotel.");
      return;
    }
    await run(() => api.select(tripId, flightId, hotelId));
  }

  async function onTravelers(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const travelers: Traveler[] = [];
    for (let i = 0; i < travelersCount; i++) {
      travelers.push({
        first_name: String(fd.get(`first_name_${i}`) || ""),
        last_name: String(fd.get(`last_name_${i}`) || ""),
        email: String(fd.get(`email_${i}`) || "") || null,
        date_of_birth: String(fd.get(`dob_${i}`) || "") || null,
      });
    }
    if (travelers.some((t) => !t.first_name || !t.last_name)) {
      setError("First and last name are required for each traveler.");
      return;
    }
    await run(() => api.travelers(tripId, travelers));
  }

  if (!trip) {
    return (
      <main className="container">
        <p className="empty">{error || "Loading trip…"}</p>
      </main>
    );
  }

  const overBudget = trip.proposal && !trip.proposal.within_budget;
  const toolCalls = trip.tool_calls || [];

  return (
    <main className="container" style={{ paddingBottom: "3rem" }}>
      <header className="site-header">
        <Link href="/dashboard" className="brand">
          Travel Booking Agent
        </Link>
        <span className={`pill ${trip.state.includes("FAIL") || trip.state === "EXPIRED" ? "danger" : ""}`}>
          {trip.state}
        </span>
      </header>

      <h1>
        {trip.constraints.origin} → {trip.constraints.destination}
      </h1>
      <p style={{ color: "var(--muted)", marginTop: 0 }}>
        {trip.constraints.departure_date} – {trip.constraints.return_date}
        {trip.constraints.budget_usd ? ` · Budget $${trip.constraints.budget_usd}` : ""}
      </p>
      <Stepper state={trip.state} />
      {error && <div className="error">{error}</div>}

      <div className="layout-split">
        <div>
          {(trip.state === "COMPARE" || trip.state === "TRAVELERS" || trip.state === "AWAIT_APPROVAL") && (
            <section className="panel fade-in" style={{ marginBottom: "1rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem", flexWrap: "wrap" }}>
                <h2 style={{ marginTop: 0 }}>
                  Flight options{" "}
                  <span className="pill">{sortedFlights.length} available</span>
                </h2>
                <label style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                  Sort
                  <select
                    value={flightSort}
                    onChange={(e) => setFlightSort(e.target.value as "price" | "duration" | "stops")}
                  >
                    <option value="price">Price</option>
                    <option value="duration">Duration</option>
                    <option value="stops">Stops</option>
                  </select>
                </label>
              </div>
              {!sortedFlights.length && (
                <div className="empty">
                  No flight offers.{" "}
                  <button
                    className="btn btn-secondary"
                    disabled={busy}
                    type="button"
                    onClick={() => run(() => api.search(tripId))}
                  >
                    Retry search
                  </button>
                </div>
              )}
              {sortedFlights.length > 0 && <FlightRouteMap flight={mapFlight} />}
              <div style={{ display: "grid", gap: "0.65rem", marginBottom: "1.25rem" }}>
                {sortedFlights.map((f) => (
                  <div
                    key={f.offer_id}
                    onMouseEnter={() => setHoveredFlightId(f.offer_id)}
                    onMouseLeave={() => setHoveredFlightId("")}
                  >
                    <FlightCard
                      flight={f}
                      selected={flightId === f.offer_id}
                      expanded={expandedFlightId === f.offer_id}
                      onSelect={() => setFlightId(f.offer_id)}
                      onToggleExpand={() =>
                        setExpandedFlightId((prev) => (prev === f.offer_id ? "" : f.offer_id))
                      }
                    />
                  </div>
                ))}
              </div>

              <h3>Hotel options <span className="pill">{trip.hotel_offers.length}</span></h3>
              <div style={{ display: "grid", gap: "0.65rem" }}>
                {trip.hotel_offers.map((h) => (
                  <button
                    key={h.offer_id}
                    type="button"
                    className={`offer ${hotelId === h.offer_id ? "selected" : ""}`}
                    onClick={() => setHotelId(h.offer_id)}
                  >
                    <strong>{h.name}</strong>
                    <span className="pill">{sourceLabel(h.source)}</span>
                    <div className="offer-meta">
                      <span>
                        {h.check_in} → {h.check_out}
                      </span>
                      {h.rating ? <span>{h.rating}★</span> : null}
                      {h.address ? <span>{h.address}</span> : null}
                    </div>
                    <div className="offer-price">${h.price_usd.toFixed(0)}</div>
                  </button>
                ))}
              </div>

              {trip.ranked_pairs.some((p) => !p.within_budget) && (
                <p className="pill warn" style={{ marginTop: "0.9rem" }}>
                  Some combinations exceed your budget
                </p>
              )}
              <div style={{ marginTop: "1rem", display: "flex", gap: "0.6rem", flexWrap: "wrap" }}>
                <button className="btn btn-primary" disabled={busy} type="button" onClick={onSelect}>
                  Continue with selection
                </button>
                <button
                  className="btn btn-secondary"
                  disabled={busy}
                  type="button"
                  onClick={() => run(() => api.search(tripId))}
                >
                  Refresh search
                </button>
              </div>
            </section>
          )}

          {(trip.state === "TRAVELERS" || trip.state === "AWAIT_APPROVAL") && (
            <section className="panel fade-in" style={{ marginBottom: "1rem" }}>
              <h2 style={{ marginTop: 0 }}>Travelers</h2>
              <form onSubmit={onTravelers}>
                {travelerDefaults.map((t, i) => (
                  <div key={i} className="grid-2" style={{ marginBottom: "0.5rem" }}>
                    <div className="field">
                      <label>First name</label>
                      <input name={`first_name_${i}`} defaultValue={t.first_name} required />
                    </div>
                    <div className="field">
                      <label>Last name</label>
                      <input name={`last_name_${i}`} defaultValue={t.last_name} required />
                    </div>
                    <div className="field">
                      <label>Email</label>
                      <input name={`email_${i}`} type="email" defaultValue={t.email || ""} />
                    </div>
                    <div className="field">
                      <label>Date of birth</label>
                      <input name={`dob_${i}`} type="date" defaultValue={t.date_of_birth || ""} />
                    </div>
                  </div>
                ))}
                <button className="btn btn-primary" disabled={busy} type="submit">
                  Save travelers
                </button>
              </form>
            </section>
          )}

          {trip.proposal && (trip.state === "AWAIT_APPROVAL" || trip.state === "TRAVELERS") && (
            <section className="panel fade-in" style={{ marginBottom: "1rem" }}>
              <h2 style={{ marginTop: 0 }}>Review & approve</h2>
              <p className="display" style={{ fontSize: "1.35rem" }}>
                {trip.proposal.summary}
              </p>
              <p>
                Total <strong>${trip.proposal.total_usd.toFixed(2)}</strong>{" "}
                {trip.proposal.within_budget ? (
                  <span className="pill">Within budget</span>
                ) : (
                  <span className="pill warn">Over budget</span>
                )}
              </p>
              {trip.weather && (
                <p style={{ color: "var(--muted)" }}>
                  Weather: {trip.weather.temp_c}°C, {trip.weather.description}
                </p>
              )}
              {trip.reviews && (
                <p style={{ color: "var(--muted)" }}>
                  Reviews: {trip.reviews.rating}/5 ({trip.reviews.review_count})
                </p>
              )}
              {expiryLeft && (
                <p style={{ color: "var(--muted)" }}>
                  Proposal expires in: <strong>{expiryLeft}</strong>
                </p>
              )}
              {overBudget && (
                <label style={{ display: "flex", gap: "0.5rem", alignItems: "center", margin: "0.8rem 0" }}>
                  <input type="checkbox" checked={ackBudget} onChange={(e) => setAckBudget(e.target.checked)} />
                  I acknowledge this itinerary exceeds my budget
                </label>
              )}
              <div style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap" }}>
                <button
                  className="btn btn-ok"
                  disabled={busy || trip.state !== "AWAIT_APPROVAL" || (Boolean(overBudget) && !ackBudget)}
                  type="button"
                  onClick={() =>
                    run(() =>
                      api.approve(
                        tripId,
                        trip.proposal!.proposal_id,
                        trip.proposal!.itinerary_hash,
                        ackBudget,
                      ),
                    )
                  }
                >
                  Approve & book
                </button>
                <button
                  className="btn btn-danger"
                  disabled={busy}
                  type="button"
                  onClick={() => run(() => api.reject(tripId, "Looking for other options", true))}
                >
                  Reject & replan
                </button>
              </div>
            </section>
          )}

          {trip.state === "CONFIRM" && (
            <section className="panel fade-in">
              <h2 style={{ marginTop: 0 }}>Booking confirmed</h2>
              <p>Your trip is booked. Keep these references:</p>
              <ul>
                {trip.bookings.map((b) => (
                  <li key={b.booking_id}>
                    <strong>{b.kind}</strong>: {b.provider_ref} (${b.amount_usd.toFixed(2)})
                  </li>
                ))}
              </ul>
              <Link className="btn btn-primary" href="/dashboard">
                Back to dashboard
              </Link>
            </section>
          )}

          {(trip.state === "PARTIAL_FAILURE" || trip.state === "FAILED" || trip.state === "EXPIRED") && (
            <section className="panel fade-in">
              <h2 style={{ marginTop: 0 }}>{trip.state.replace("_", " ")}</h2>
              <p>{trip.error || "Something went wrong."}</p>
              {trip.bookings?.length > 0 && (
                <ul>
                  {trip.bookings.map((b) => (
                    <li key={b.booking_id}>
                      {b.kind}: {b.provider_ref}
                    </li>
                  ))}
                </ul>
              )}
              <button
                className="btn btn-primary"
                disabled={busy}
                type="button"
                onClick={() => run(() => api.search(tripId))}
              >
                Search again
              </button>
            </section>
          )}
        </div>

        <AgentToolsPanel toolCalls={toolCalls} busy={busy} />
      </div>

      {(trip.daily_weather?.length || trip.weather) && (
        <section className="panel fade-in weather-strip" style={{ marginTop: "1.25rem" }}>
          <h2 style={{ marginTop: 0 }}>Destination weather</h2>
          <p style={{ color: "var(--muted)", marginTop: 0 }}>
            {trip.weather?.location || trip.constraints.destination_city || trip.constraints.destination}
            {trip.weather ? ` · now ~${trip.weather.temp_c}°C, ${trip.weather.description}` : ""}
          </p>
          <div className="weather-days">
            {(trip.daily_weather || []).map((d) => (
              <div key={d.date} className="weather-day">
                <div className="weather-day-date">{d.date}</div>
                <div>
                  {d.temp_low_c.toFixed(0)}–{d.temp_high_c.toFixed(0)}°C
                </div>
                <div style={{ color: "var(--muted)", fontSize: "0.9rem" }}>{d.description}</div>
                {d.precipitation_chance != null && (
                  <div style={{ fontSize: "0.85rem" }}>Rain {d.precipitation_chance}%</div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
