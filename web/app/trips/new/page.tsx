"use client";

import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AirportSearchResult, ApiError, api, isLoggedIn } from "@/lib/api";

function AirportField({
  id,
  name,
  label,
  required,
  placeholder,
  onPick,
}: {
  id: string;
  name: string;
  label: string;
  required?: boolean;
  placeholder?: string;
  onPick?: (ap: AirportSearchResult) => void;
}) {
  const [query, setQuery] = useState("");
  const [iata, setIata] = useState("");
  const [suggestions, setSuggestions] = useState<AirportSearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const debounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (debounce.current) clearTimeout(debounce.current);
    if (query.trim().length < 2) {
      setSuggestions([]);
      return;
    }
    debounce.current = setTimeout(() => {
      api
        .searchAirports(query.trim())
        .then(setSuggestions)
        .catch(() => setSuggestions([]));
    }, 220);
    return () => {
      if (debounce.current) clearTimeout(debounce.current);
    };
  }, [query]);

  function pick(ap: AirportSearchResult) {
    setQuery(ap.label);
    setIata(ap.iata);
    setOpen(false);
    onPick?.(ap);
  }

  return (
    <div className="field airport-field">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        name={name}
        required={required}
        placeholder={placeholder}
        autoComplete="off"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setIata("");
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
      />
      <input type="hidden" name={`${name}_iata`} value={iata} readOnly />
      {open && suggestions.length > 0 && (
        <ul className="airport-suggestions" role="listbox">
          {suggestions.map((ap) => (
            <li key={ap.iata}>
              <button type="button" onMouseDown={() => pick(ap)}>
                <strong>{ap.iata}</strong> — {ap.city}, {ap.country}
                <span style={{ display: "block", color: "var(--muted)", fontSize: "0.88rem" }}>{ap.name}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {iata && (
        <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--muted)" }}>
          Selected IATA: <strong>{iata}</strong>
        </p>
      )}
    </div>
  );
}

export default function NewTripPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [destCity, setDestCity] = useState("");

  useEffect(() => {
    if (!isLoggedIn()) router.replace("/login");
  }, [router]);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const fd = new FormData(e.currentTarget);
    const origin = String(fd.get("origin_iata") || fd.get("origin") || "")
      .toUpperCase()
      .trim();
    const destination = String(fd.get("destination_iata") || fd.get("destination") || "")
      .toUpperCase()
      .trim();
    const departure = String(fd.get("departure_date"));
    const ret = String(fd.get("return_date"));
    if (origin.length !== 3 || destination.length !== 3) {
      setError("Pick origin and destination from the airport suggestions (3-letter IATA).");
      setBusy(false);
      return;
    }
    if (ret < departure) {
      setError("Return date must be on or after departure.");
      setBusy(false);
      return;
    }
    try {
      const trip = await api.createTrip(
        {
          origin,
          destination,
          destination_city: String(fd.get("destination_city") || destCity || destination),
          departure_date: departure,
          return_date: ret,
          adults: Number(fd.get("adults") || 1),
          budget_usd: fd.get("budget_usd") ? Number(fd.get("budget_usd")) : null,
          travelers: [],
        },
        String(fd.get("preferences_text") || "") || undefined,
      );
      const searched = await api.search(trip.trip_id);
      router.push(`/trips/${searched.trip_id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not start trip");
      setBusy(false);
    }
  }

  return (
    <main className="container" style={{ maxWidth: 720, paddingBottom: "3rem" }}>
      <header className="site-header">
        <Link href="/dashboard" className="brand">
          Travel Booking Agent
        </Link>
      </header>
      <h1>Plan a trip</h1>
      <p style={{ color: "var(--muted)" }}>Search across flight and hotel websites — not a chatbot.</p>
      <div className="stepper">
        <span className="step active">1. Search</span>
        <span className="step">2. Compare</span>
        <span className="step">3. Travelers</span>
        <span className="step">4. Approve</span>
      </div>
      <form className="panel fade-in" onSubmit={onSubmit}>
        <div className="grid-2">
          <AirportField id="origin" name="origin" label="Origin airport" required placeholder="Tokyo, JFK, Heathrow…" />
          <AirportField
            id="destination"
            name="destination"
            label="Destination airport"
            required
            placeholder="Los Angeles, CDG…"
            onPick={(ap) => setDestCity(ap.city)}
          />
        </div>
        <div className="field">
          <label htmlFor="destination_city">Destination city label</label>
          <input
            id="destination_city"
            name="destination_city"
            placeholder="Los Angeles"
            value={destCity}
            onChange={(e) => setDestCity(e.target.value)}
          />
        </div>
        <div className="grid-2">
          <div className="field">
            <label htmlFor="departure_date">Departure</label>
            <input id="departure_date" name="departure_date" type="date" required defaultValue="2026-09-01" />
          </div>
          <div className="field">
            <label htmlFor="return_date">Return</label>
            <input id="return_date" name="return_date" type="date" required defaultValue="2026-09-05" />
          </div>
        </div>
        <div className="grid-2">
          <div className="field">
            <label htmlFor="adults">Adults</label>
            <input id="adults" name="adults" type="number" min={1} max={9} defaultValue={1} required />
          </div>
          <div className="field">
            <label htmlFor="budget_usd">Budget (USD)</label>
            <input id="budget_usd" name="budget_usd" type="number" min={1} step="1" placeholder="2000" />
          </div>
        </div>
        <div className="field">
          <label htmlFor="preferences_text">Preferences (optional)</label>
          <textarea id="preferences_text" name="preferences_text" rows={2} placeholder="Prefer direct flights" />
        </div>
        {error && <div className="error">{error}</div>}
        <button className="btn btn-primary" disabled={busy} type="submit">
          {busy ? "Searching…" : "Search flights & hotels"}
        </button>
      </form>
    </main>
  );
}
