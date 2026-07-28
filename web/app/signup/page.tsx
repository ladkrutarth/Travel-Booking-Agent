"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api, setTokens } from "@/lib/api";

export default function SignupPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const fd = new FormData(e.currentTarget);
    try {
      const tokens = await api.signup(
        String(fd.get("email")),
        String(fd.get("password")),
        String(fd.get("full_name") || ""),
      );
      setTokens(tokens);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Signup failed");
      setBusy(false);
    }
  }

  return (
    <main className="container" style={{ maxWidth: 480, paddingTop: "3rem" }}>
      <Link href="/" className="brand">
        Travel Booking Agent
      </Link>
      <h1 style={{ marginTop: "1.5rem" }}>Create account</h1>
      <p style={{ color: "var(--muted)" }}>Save trips, approve bookings, and keep history.</p>
      <form className="panel fade-in" onSubmit={onSubmit}>
        <div className="field">
          <label htmlFor="full_name">Full name</label>
          <input id="full_name" name="full_name" placeholder="Alex Traveler" />
        </div>
        <div className="field">
          <label htmlFor="email">Email</label>
          <input id="email" name="email" type="email" required placeholder="you@example.com" />
        </div>
        <div className="field">
          <label htmlFor="password">Password</label>
          <input id="password" name="password" type="password" required minLength={8} />
        </div>
        {error && <div className="error">{error}</div>}
        <button className="btn btn-primary" disabled={busy} type="submit">
          {busy ? "Creating…" : "Create account"}
        </button>
      </form>
      <p style={{ marginTop: "1rem", color: "var(--muted)" }}>
        Already have an account? <Link href="/login">Log in</Link>
      </p>
    </main>
  );
}
