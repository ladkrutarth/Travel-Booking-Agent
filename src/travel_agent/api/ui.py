"""Minimal browser UI for trip propose / approve / reject."""

UI_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Travel Booking Agent</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,700&family=Source+Sans+3:wght@400;600&display=swap" rel="stylesheet" />
  <style>
    :root {
      --ink: #13212b;
      --muted: #5a6b75;
      --paper: #f3efe6;
      --panel: rgba(255, 252, 246, 0.92);
      --line: #d5cbb8;
      --accent: #0f6a5c;
      --accent-2: #c45c26;
      --danger: #9b2c2c;
      --ok: #1f6b3a;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: "Source Sans 3", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(1200px 600px at 10% -10%, #d8ebe4 0%, transparent 55%),
        radial-gradient(900px 500px at 100% 0%, #f0d9c4 0%, transparent 50%),
        linear-gradient(180deg, #efe8da 0%, var(--paper) 45%, #e7efe9 100%);
    }
    main {
      width: min(880px, calc(100% - 2rem));
      margin: 0 auto;
      padding: 2.5rem 0 4rem;
    }
    h1 {
      font-family: Fraunces, Georgia, serif;
      font-size: clamp(2rem, 5vw, 3rem);
      font-weight: 700;
      letter-spacing: -0.02em;
      margin: 0 0 0.35rem;
    }
    .lede {
      color: var(--muted);
      max-width: 38rem;
      margin: 0 0 1.75rem;
      line-height: 1.5;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 1.25rem 1.35rem;
      backdrop-filter: blur(8px);
      box-shadow: 0 18px 40px rgba(19, 33, 43, 0.06);
    }
    label {
      display: block;
      font-weight: 600;
      font-size: 0.92rem;
      margin-bottom: 0.45rem;
    }
    textarea {
      width: 100%;
      min-height: 110px;
      resize: vertical;
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 0.85rem 1rem;
      font: inherit;
      background: #fffdf8;
      color: var(--ink);
    }
    textarea:focus {
      outline: 2px solid rgba(15, 106, 92, 0.35);
      border-color: var(--accent);
    }
    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 0.65rem;
      margin-top: 0.9rem;
    }
    button {
      appearance: none;
      border: 0;
      border-radius: 999px;
      padding: 0.7rem 1.15rem;
      font: inherit;
      font-weight: 600;
      cursor: pointer;
      transition: transform 0.15s ease, opacity 0.15s ease;
    }
    button:hover { transform: translateY(-1px); }
    button:disabled { opacity: 0.55; cursor: not-allowed; transform: none; }
    .primary { background: var(--accent); color: #f7fffc; }
    .secondary { background: #ebe4d6; color: var(--ink); }
    .approve { background: var(--ok); color: #f4fff7; }
    .reject { background: var(--danger); color: #fff7f7; }
    #status {
      margin: 1rem 0 0;
      min-height: 1.25rem;
      color: var(--muted);
      font-size: 0.95rem;
    }
    #result {
      margin-top: 1.25rem;
      display: none;
    }
    #result.visible { display: block; animation: rise 0.35s ease; }
    @keyframes rise {
      from { opacity: 0; transform: translateY(8px); }
      to { opacity: 1; transform: none; }
    }
    .meta {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem 1rem;
      margin-bottom: 1rem;
      color: var(--muted);
      font-size: 0.92rem;
    }
    .pill {
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
      padding: 0.25rem 0.65rem;
      border-radius: 999px;
      background: #e8f3ef;
      color: var(--accent);
      font-weight: 600;
      font-size: 0.85rem;
    }
    .summary {
      font-family: Fraunces, Georgia, serif;
      font-size: 1.35rem;
      line-height: 1.35;
      margin: 0 0 1rem;
    }
    .grid {
      display: grid;
      gap: 0.85rem;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    }
    .card {
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 0.9rem 1rem;
      background: #fffdf8;
    }
    .card h3 {
      margin: 0 0 0.35rem;
      font-size: 0.8rem;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--muted);
      font-weight: 600;
    }
    .card p { margin: 0; line-height: 1.45; }
    .price {
      margin-top: 1rem;
      font-size: 1.15rem;
      font-weight: 600;
    }
    .bookings { margin-top: 1rem; color: var(--ok); font-weight: 600; }
    .error { color: var(--danger); }
    .links { margin-top: 1.5rem; color: var(--muted); font-size: 0.9rem; }
    .links a { color: var(--accent); }
  </style>
</head>
<body>
  <main>
    <h1>Travel Booking Agent</h1>
    <p class="lede">
      Describe a trip. The agent searches flights and hotels, then waits for your approval before booking.
    </p>

    <section class="panel">
      <label for="message">Trip request</label>
      <textarea id="message" placeholder="Trip from New York to Los Angeles 2026-09-01 to 2026-09-05, budget $2000"></textarea>
      <div class="actions">
        <button class="primary" id="planBtn" type="button">Find itinerary</button>
        <button class="approve" id="approveBtn" type="button" disabled>Approve &amp; book</button>
        <button class="reject" id="rejectBtn" type="button" disabled>Reject &amp; replan</button>
        <button class="secondary" id="docsBtn" type="button">API docs</button>
      </div>
      <p id="status"></p>
    </section>

    <section class="panel" id="result">
      <div class="meta">
        <span class="pill" id="statePill">—</span>
        <span id="tripId"></span>
      </div>
      <p class="summary" id="summary"></p>
      <div class="grid">
        <div class="card">
          <h3>Flight</h3>
          <p id="flight"></p>
        </div>
        <div class="card">
          <h3>Hotel</h3>
          <p id="hotel"></p>
        </div>
        <div class="card">
          <h3>Weather / reviews</h3>
          <p id="extras"></p>
        </div>
      </div>
      <p class="price" id="price"></p>
      <p class="bookings" id="bookings"></p>
      <p class="error" id="error"></p>
    </section>

    <p class="links">Also available: <a href="/docs">/docs</a> · <a href="/health">/health</a></p>
  </main>

  <script>
    let trip = null;
    const statusEl = document.getElementById("status");
    const resultEl = document.getElementById("result");
    const approveBtn = document.getElementById("approveBtn");
    const rejectBtn = document.getElementById("rejectBtn");

    function setBusy(busy) {
      document.getElementById("planBtn").disabled = busy;
      approveBtn.disabled = busy || !trip || trip.state !== "AWAIT_APPROVAL";
      rejectBtn.disabled = busy || !trip || trip.state !== "AWAIT_APPROVAL";
    }

    function render(data) {
      trip = data;
      resultEl.classList.add("visible");
      document.getElementById("statePill").textContent = data.state;
      document.getElementById("tripId").textContent = "Trip " + data.trip_id;
      const p = data.proposal;
      document.getElementById("summary").textContent = (p && p.summary) || data.error || "No proposal yet.";
      if (p && p.flight) {
        document.getElementById("flight").textContent =
          p.flight.carrier + " " + p.flight.origin + " → " + p.flight.destination +
          " · $" + p.flight.price_usd.toFixed(2) + " · " + p.flight.stops + " stops";
      } else {
        document.getElementById("flight").textContent = "—";
      }
      if (p && p.hotel) {
        document.getElementById("hotel").textContent =
          p.hotel.name + " · $" + p.hotel.price_usd.toFixed(2) +
          " · " + p.hotel.check_in + " → " + p.hotel.check_out;
      } else {
        document.getElementById("hotel").textContent = "—";
      }
      const bits = [];
      if (p && p.weather) bits.push(p.weather.temp_c + "°C, " + p.weather.description);
      if (p && p.reviews) bits.push("Reviews " + p.reviews.rating + "/5 (" + p.reviews.review_count + ")");
      document.getElementById("extras").textContent = bits.join(" · ") || "—";
      document.getElementById("price").textContent = p
        ? ("Total $" + p.total_usd.toFixed(2) + (p.within_budget ? " · within budget" : " · over budget"))
        : "";
      if (data.bookings && data.bookings.length) {
        document.getElementById("bookings").textContent =
          "Booked: " + data.bookings.map(b => b.kind + " " + b.provider_ref).join(", ");
      } else {
        document.getElementById("bookings").textContent = "";
      }
      document.getElementById("error").textContent = data.error || "";
      setBusy(false);
    }

    async function plan() {
      const message = document.getElementById("message").value.trim();
      if (!message) {
        statusEl.textContent = "Enter a trip request first.";
        return;
      }
      setBusy(true);
      statusEl.textContent = "Searching flights and hotels…";
      try {
        const res = await fetch("/trips", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Request failed");
        statusEl.textContent = data.state === "AWAIT_APPROVAL"
          ? "Proposal ready — approve to book, or reject to replan."
          : ("Finished with state " + data.state);
        render(data);
      } catch (err) {
        statusEl.textContent = String(err.message || err);
        setBusy(false);
      }
    }

    async function approve() {
      if (!trip || !trip.proposal) return;
      setBusy(true);
      statusEl.textContent = "Booking with approval…";
      try {
        const res = await fetch("/trips/" + trip.trip_id + "/approve", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            proposal_id: trip.proposal.proposal_id,
            itinerary_hash: trip.proposal.itinerary_hash,
          }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Approve failed");
        statusEl.textContent = "Booking complete.";
        render(data);
      } catch (err) {
        statusEl.textContent = String(err.message || err);
        setBusy(false);
      }
    }

    async function reject() {
      if (!trip) return;
      const feedback = prompt("Optional feedback for replan:", "Prefer cheaper options") || "";
      setBusy(true);
      statusEl.textContent = "Replanning…";
      try {
        const res = await fetch("/trips/" + trip.trip_id + "/reject", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            proposal_id: trip.proposal && trip.proposal.proposal_id,
            feedback,
          }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Reject failed");
        statusEl.textContent = "New proposal ready.";
        render(data);
      } catch (err) {
        statusEl.textContent = String(err.message || err);
        setBusy(false);
      }
    }

    document.getElementById("planBtn").addEventListener("click", plan);
    document.getElementById("approveBtn").addEventListener("click", approve);
    document.getElementById("rejectBtn").addEventListener("click", reject);
    document.getElementById("docsBtn").addEventListener("click", () => { window.location.href = "/docs"; });
    document.getElementById("message").value =
      "Trip from New York to Los Angeles 2026-09-01 to 2026-09-05, budget $2000";
  </script>
</body>
</html>
"""
