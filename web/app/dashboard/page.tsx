"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, TripSummary, api, clearTokens, isLoggedIn } from "@/lib/api";

export default function DashboardPage() {
  const router = useRouter();
  const [trips, setTrips] = useState<TripSummary[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace("/login");
      return;
    }
    api
      .listTrips()
      .then(setTrips)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load trips"))
      .finally(() => setLoading(false));
  }, [router]);

  return (
    <main className="container" style={{ paddingBottom: "3rem" }}>
      <header className="site-header">
        <Link href="/" className="brand">
          Travel Booking Agent
        </Link>
        <div className="nav-actions">
          <Link className="btn btn-primary" href="/trips/new">
            New trip
          </Link>
          <button
            className="btn btn-secondary"
            type="button"
            onClick={() => {
              clearTokens();
              router.push("/");
            }}
          >
            Log out
          </button>
        </div>
      </header>

      <h1>Your trips</h1>
      <p style={{ color: "var(--muted)", marginTop: 0 }}>Track searches, approvals, and confirmations.</p>

      {error && <div className="error">{error}</div>}
      {loading && <p className="empty">Loading trips…</p>}
      {!loading && !trips.length && (
        <div className="panel empty fade-in">
          <p>No trips yet.</p>
          <Link className="btn btn-primary" href="/trips/new">
            Plan your first trip
          </Link>
        </div>
      )}

      <div style={{ display: "grid", gap: "0.85rem", marginTop: "1rem" }}>
        {trips.map((t) => (
          <Link key={t.trip_id} href={`/trips/${t.trip_id}`} className="panel fade-in" style={{ display: "block" }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem", flexWrap: "wrap" }}>
              <div>
                <strong>
                  {t.origin || "—"} → {t.destination || "—"}
                </strong>
                <div style={{ color: "var(--muted)", marginTop: 4 }}>
                  {t.departure_date || "?"} – {t.return_date || "?"}
                  {t.total_usd != null ? ` · $${t.total_usd.toFixed(0)}` : ""}
                </div>
              </div>
              <span
                className={`pill ${
                  t.state === "FAILED" || t.state === "PARTIAL_FAILURE" || t.state === "EXPIRED"
                    ? "danger"
                    : t.state === "CONFIRM"
                      ? ""
                      : "warn"
                }`}
              >
                {t.state}
              </span>
            </div>
          </Link>
        ))}
      </div>
    </main>
  );
}
