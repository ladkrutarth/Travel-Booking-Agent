"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { clearTokens, isLoggedIn } from "@/lib/api";

export default function HomePage() {
  const [loggedIn, setLoggedIn] = useState(false);
  useEffect(() => setLoggedIn(isLoggedIn()), []);

  return (
    <main className="container">
      <header className="site-header">
        <div className="brand">Travel Booking Agent</div>
        <div className="nav-actions">
          {loggedIn ? (
            <>
              <Link className="btn btn-secondary" href="/dashboard">
                Dashboard
              </Link>
              <button
                className="btn btn-secondary"
                type="button"
                onClick={() => {
                  clearTokens();
                  setLoggedIn(false);
                }}
              >
                Log out
              </button>
            </>
          ) : (
            <>
              <Link className="btn btn-secondary" href="/login">
                Log in
              </Link>
              <Link className="btn btn-primary" href="/signup">
                Create account
              </Link>
            </>
          )}
        </div>
      </header>

      <section className="hero">
        <div className="hero-bg" aria-hidden />
        <div className="hero-content fade-in">
          <h1>Travel Booking Agent</h1>
          <p>
            Search flights and hotels, compare options, confirm travelers, and approve
            before anything is booked.
          </p>
          <Link className="btn btn-primary" href={loggedIn ? "/trips/new" : "/signup"}>
            Start a trip
          </Link>
        </div>
      </section>
    </main>
  );
}
