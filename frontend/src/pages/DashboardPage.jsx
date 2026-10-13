import React, { useEffect, useMemo, useState } from "react";

import { FeedList } from "../components/FeedList";
import { KpiCard } from "../components/KpiCard";

const gatewayUrl = import.meta.env.VITE_API_GATEWAY_URL || "http://localhost:32037";

const fallback = {
  operational: { occupancy_rate: 0, adr: 0, revpar: 0 },
  financial: { gross_revenue: 0, profit: 0, margin_pct: 0 },
  forecast: { forecast: [], mape_pct: 0, target_mape_pct: 10 },
  booking_time: { booking_time_seconds: 0, target_seconds: 3, target_met: false },
  housekeeping: { items: [] },
  bookings: { items: [] },
};

async function loadDashboard(propertyId) {
  const response = await fetch(`${gatewayUrl}/dashboard/${propertyId}`);
  if (!response.ok) {
    throw new Error(`Gateway error ${response.status}`);
  }
  return response.json();
}

export function DashboardPage() {
  const [propertyId, setPropertyId] = useState("PROP-001");
  const [data, setData] = useState(fallback);
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    let active = true;
    setStatus("loading");
    loadDashboard(propertyId)
      .then((payload) => {
        if (!active) {
          return;
        }
        setData({ ...fallback, ...payload });
        setStatus("ready");
      })
      .catch(() => {
        if (!active) {
          return;
        }
        setStatus("fallback");
        setData(fallback);
      });

    return () => {
      active = false;
    };
  }, [propertyId]);

  const bookingRows = useMemo(
    () =>
      (data.bookings?.items || []).slice(-6).map((item) => ({
        label: `${item.guest_name} · ${item.source}`,
        value: `${item.check_in_date} -> ${item.check_out_date}`,
      })),
    [data]
  );

  const taskRows = useMemo(
    () =>
      (data.housekeeping?.items || []).slice(-6).map((item) => ({
        label: `${item.task_type} · room ${item.room_id}`,
        value: item.status,
      })),
    [data]
  );

  return (
    <div className="app">
      <div className="ambient ambient-a" />
      <div className="ambient ambient-b" />

      <header className="hero">
        <div>
          <p className="eyebrow">HotelMaster PMS</p>
          <h1>Hospitality overview</h1>
          <p className="subtitle">
            Live operations board for hotels, hostels, apart-hotels, and sanatoriums with pricing automation and occupancy forecast.
          </p>
        </div>

        <div className="hero-controls">
          <label>
            Property ID
            <input value={propertyId} onChange={(event) => setPropertyId(event.target.value)} />
          </label>
          <span className="status">status: {status}</span>
        </div>
      </header>

      <section className="kpi-grid">
        <KpiCard
          title="Booking Time"
          value={`${Number(data.booking_time?.booking_time_seconds || 0).toFixed(2)} sec`}
          target={`Target < ${data.booking_time?.target_seconds || 3} sec`}
          ok={Boolean(data.booking_time?.target_met)}
        />
        <KpiCard
          title="Occupancy"
          value={`${Math.round(Number(data.operational?.occupancy_rate || 0) * 100)}%`}
          target="Daily control"
          ok={Number(data.operational?.occupancy_rate || 0) >= 0.6}
        />
        <KpiCard
          title="ADR"
          value={`${Math.round(Number(data.operational?.adr || 0)).toLocaleString()} RUB`}
          target="Average daily rate"
          ok={Number(data.operational?.adr || 0) > 0}
        />
        <KpiCard
          title="RevPAR"
          value={`${Math.round(Number(data.operational?.revpar || 0)).toLocaleString()} RUB`}
          target="Revenue per available room"
          ok={Number(data.operational?.revpar || 0) > 0}
        />
      </section>

      <section className="content-grid">
        <article className="panel panel-wide">
          <div className="panel-head">
            <h3>Financial Summary</h3>
          </div>
          <div className="finance-grid">
            <div>
              <span>Gross revenue</span>
              <strong>{Math.round(Number(data.financial?.gross_revenue || 0)).toLocaleString()} RUB</strong>
            </div>
            <div>
              <span>Profit</span>
              <strong>{Math.round(Number(data.financial?.profit || 0)).toLocaleString()} RUB</strong>
            </div>
            <div>
              <span>Margin</span>
              <strong>{Number(data.financial?.margin_pct || 0).toFixed(1)}%</strong>
            </div>
            <div>
              <span>Forecast MAPE</span>
              <strong>{Number(data.forecast?.mape_pct || 0).toFixed(2)}%</strong>
            </div>
          </div>
          <div className="forecast-line">
            {(data.forecast?.forecast || []).map((value, idx) => (
              <span key={idx} style={{ height: `${Math.max(18, value * 140)}px` }} />
            ))}
          </div>
        </article>

        <FeedList title="Recent Bookings" items={bookingRows} emptyText="No bookings" />
        <FeedList title="Housekeeping Queue" items={taskRows} emptyText="No tasks" />
      </section>
    </div>
  );
}
