"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api, setTokens } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const fd = new FormData(e.currentTarget);
    try {
      const tokens = await api.login(String(fd.get("email")), String(fd.get("password")));
      setTokens(tokens);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed");
      setBusy(false);
    }
  }

  return (
    <main className="container" style={{ maxWidth: 480, paddingTop: "3rem" }}>
      <Link href="/" className="brand">
        Travel Booking Agent
      </Link>
      <h1 style={{ marginTop: "1.5rem" }}>Log in</h1>
      <form className="panel fade-in" onSubmit={onSubmit}>
        <div className="field">
          <label htmlFor="email">Email</label>
          <input id="email" name="email" type="email" required />
        </div>
        <div className="field">
          <label htmlFor="password">Password</label>
          <input id="password" name="password" type="password" required />
        </div>
        {error && <div className="error">{error}</div>}
        <button className="btn btn-primary" disabled={busy} type="submit">
          {busy ? "Signing in…" : "Log in"}
        </button>
      </form>
      <p style={{ marginTop: "1rem", color: "var(--muted)" }}>
        New here? <Link href="/signup">Create an account</Link>
      </p>
    </main>
  );
}
