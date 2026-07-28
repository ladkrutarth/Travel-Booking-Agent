"use client";

import { useMemo } from "react";
import { FlightOffer } from "@/lib/api";
import { getAirportCoord, projectEquirectangular } from "@/lib/airports";

type RoutePoint = {
  iata: string;
  role: "origin" | "stop" | "destination";
  x: number;
  y: number;
  lat: number;
  lon: number;
};

function arcPath(a: { x: number; y: number }, b: { x: number; y: number }): string {
  const mx = (a.x + b.x) / 2;
  const my = (a.y + b.y) / 2;
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len = Math.hypot(dx, dy) || 1;
  // Bulge perpendicular to segment
  const bulge = Math.min(48, 12 + len * 0.12);
  const cx = mx - (dy / len) * bulge;
  const cy = my + (dx / len) * bulge;
  return `M ${a.x} ${a.y} Q ${cx} ${cy} ${b.x} ${b.y}`;
}

export function FlightRouteMap({ flight }: { flight: FlightOffer | null }) {
  const width = 640;
  const height = 280;

  const { points, paths, title } = useMemo(() => {
    if (!flight) {
      return { points: [] as RoutePoint[], paths: [] as string[], title: "Select a flight to preview its route" };
    }
    const codes: string[] = [];
    if (flight.segments?.length) {
      flight.segments.forEach((seg, i) => {
        if (i === 0) codes.push(seg.origin);
        codes.push(seg.destination);
      });
    } else {
      codes.push(flight.origin, flight.destination);
    }
    const uniqueCodes = codes.filter(Boolean);
    const coords = uniqueCodes
      .map((iata, idx) => {
        const ap = getAirportCoord(iata);
        if (!ap) return null;
        const role: RoutePoint["role"] =
          idx === 0 ? "origin" : idx === uniqueCodes.length - 1 ? "destination" : "stop";
        const { x, y } = projectEquirectangular(ap.lat, ap.lon, width, height);
        return { iata, role, x, y, lat: ap.lat, lon: ap.lon } satisfies RoutePoint;
      })
      .filter((p): p is RoutePoint => Boolean(p));

    const paths = coords.slice(0, -1).map((p, i) => arcPath(p, coords[i + 1]));
    const via =
      coords.length > 2
        ? ` via ${coords
            .slice(1, -1)
            .map((c) => c.iata)
            .join(", ")}`
        : "";
    const title = `${flight.origin} → ${flight.destination}${via}`;
    return { points: coords, paths, title };
  }, [flight]);

  // Fit viewBox around route with padding when we have points
  const viewBox = useMemo(() => {
    if (points.length < 1) return `0 0 ${width} ${height}`;
    const xs = points.map((p) => p.x);
    const ys = points.map((p) => p.y);
    const minX = Math.max(0, Math.min(...xs) - 40);
    const maxX = Math.min(width, Math.max(...xs) + 40);
    const minY = Math.max(0, Math.min(...ys) - 36);
    const maxY = Math.min(height, Math.max(...ys) + 36);
    const vw = Math.max(120, maxX - minX);
    const vh = Math.max(100, maxY - minY);
    return `${minX} ${minY} ${vw} ${vh}`;
  }, [points]);

  return (
    <div className="route-map" aria-label="Flight route map">
      <div className="route-map-header">
        <strong>Route map</strong>
        <span className="route-map-subtitle">{title}</span>
      </div>
      <svg
        className="route-map-svg"
        viewBox={viewBox}
        role="img"
        preserveAspectRatio="xMidYMid meet"
      >
        <defs>
          <linearGradient id="ocean" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#d7e8e4" />
            <stop offset="55%" stopColor="#c5d9e8" />
            <stop offset="100%" stopColor="#e8dfd2" />
          </linearGradient>
          <filter id="soft">
            <feDropShadow dx="0" dy="1" stdDeviation="1.2" floodOpacity="0.18" />
          </filter>
        </defs>
        <rect x={0} y={0} width={width} height={height} fill="url(#ocean)" />
        {/* subtle latitude lines */}
        {[0.25, 0.5, 0.75].map((t) => (
          <line
            key={t}
            x1={0}
            x2={width}
            y1={height * t}
            y2={height * t}
            stroke="rgba(14,28,36,0.06)"
            strokeWidth={1}
          />
        ))}
        {paths.map((d, i) => (
          <path
            key={i}
            d={d}
            className="route-arc"
            fill="none"
            stroke="var(--accent)"
            strokeWidth={2.4}
            strokeLinecap="round"
          />
        ))}
        {points.map((p) => (
          <g key={`${p.role}-${p.iata}`} filter="url(#soft)">
            <circle
              cx={p.x}
              cy={p.y}
              r={p.role === "stop" ? 5.5 : 7}
              className={`route-marker route-marker-${p.role}`}
            />
            <text x={p.x} y={p.y - 12} textAnchor="middle" className="route-label">
              {p.iata}
            </text>
          </g>
        ))}
        {!points.length && (
          <text x={width / 2} y={height / 2} textAnchor="middle" className="route-empty">
            No coordinates for this route
          </text>
        )}
      </svg>
      <div className="route-legend">
        <span>
          <i className="route-dot origin" /> Origin / destination
        </span>
        <span>
          <i className="route-dot stop" /> Layover
        </span>
      </div>
    </div>
  );
}
