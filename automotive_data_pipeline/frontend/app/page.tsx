"use client";

import { useEffect, useMemo, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

type Evidence = { source_uri: string; locator: string; quote?: string };
type Requirement = {
  requirement_id: string; target_platform: string; taxonomy_category: string; title: string;
  requirement_statement: string; region_variant: string; average_sentiment: number;
  velocity_acceleration_pct: number | null; effort_class: string; effort_penalty: number;
  priority_score: number | null; review_band: string; ehi_score: number; confidence_label: string;
  regional_conflict: boolean; warnings: string[]; blindspots: string[]; evidence: Evidence[]; status: string;
};

export default function Page() {
  const [items, setItems] = useState<Requirement[]>([]);
  const [vehicle, setVehicle] = useState("Neue_Klasse");
  const [error, setError] = useState("");
  const [openBlindspots, setOpenBlindspots] = useState<string | null>(null);
  const refresh = () => { void fetch(`${API}/api/requirements`).then(r => r.ok ? r.json() : Promise.reject(r.statusText)).then(setItems).catch(e => setError(String(e))); };
  useEffect(() => { refresh(); }, []);
  const visible = useMemo(() => items.filter(item => item.target_platform === vehicle), [items, vehicle]);

  async function decide(item: Requirement, action: string) {
    const actor = window.prompt("PM name")?.trim();
    if (!actor) return;
    const justification = action === "Approve" ? "" : window.prompt(`Mandatory justification for ${action}`)?.trim();
    if (action !== "Approve" && !justification) return;
    const edited = action === "Edit" ? window.prompt("Edited customer-facing requirement", item.requirement_statement)?.trim() : undefined;
    if (action === "Edit" && !edited) return;
    const response = await fetch(`${API}/api/requirements/${item.requirement_id}/decision`, {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({actor, action, justification: justification || "", edited_requirement_statement: edited})
    });
    if (!response.ok) setError(await response.text()); else refresh();
  }

  async function trigger() {
    const actor = window.prompt("PM name")?.trim();
    const justification = window.prompt("Why run this synthetic scenario now?")?.trim();
    if (!actor || !justification) return;
    const response = await fetch(`${API}/api/trigger-synthetic`, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({actor, seed: Date.now() % 100000, justification})});
    alert(response.ok ? "Synthetic scenario queued. It is labelled hypothetical evidence." : await response.text());
  }

  return <main>
    <header>
      <div><p className="eyebrow">BMW PRODUCT MANAGEMENT</p><h1>Evidence cockpit</h1></div>
      <div className="toolbar">
        <label>Vehicle<select value={vehicle} onChange={e => setVehicle(e.target.value)}>{["Neue_Klasse", "F70", "G60", "G70"].map(value => <option key={value}>{value}</option>)}</select></label>
        <button onClick={trigger}>⚡ Do It Now</button>
        <a className="button" href={`${API}/api/export-deck`}>Export board deck</a>
      </div>
    </header>
    {error && <aside className="error">{error}</aside>}
    <section className="summary"><span>{visible.length} candidates</span><span>{visible.filter(x => x.review_band === "Unscored").length} unscored</span><span>{visible.filter(x => x.regional_conflict).length} regional conflicts</span></section>
    <section className="grid">{visible.map(item => <article key={item.requirement_id}>
      <div className="cardTop"><span className="category">{item.taxonomy_category}</span><span className={`band ${item.review_band.replace(" ", "-").toLowerCase()}`}>{item.review_band}</span></div>
      <h2>{item.title}</h2><p className="requirement">{item.requirement_statement}</p>
      {(item.ehi_score < 50 || item.regional_conflict) && <div className="warning"><strong>AI uncertainty warning — {item.ehi_score.toFixed(0)}%</strong><br/>{item.warnings.join(" ") || "Human PM intervention required."}</div>}
      <div className="metrics">
        <div><small>Sentiment</small><strong className={item.average_sentiment < 0 ? "negative" : "positive"}>{item.average_sentiment > 0 ? "+" : ""}{item.average_sentiment.toFixed(0)}</strong></div>
        <div><small>30-day velocity</small><strong>{item.velocity_acceleration_pct == null ? "Unknown" : `${item.velocity_acceleration_pct > 0 ? "+" : ""}${item.velocity_acceleration_pct}%`}</strong></div>
        <div><small>Effort</small><strong>{item.effort_class} −{item.effort_penalty}</strong></div>
        <div><small>Priority</small><strong>{item.priority_score ?? "Unscored"}</strong></div>
      </div>
      <details><summary>Evidence grid ({item.evidence.length})</summary>{item.evidence.slice(0, 8).map((evidence, index) => <p key={index}><b>{evidence.source_uri}</b> · {evidence.locator}<br/><small>{evidence.quote}</small></p>)}</details>
      <button className="blindspot" onClick={() => setOpenBlindspots(openBlindspots === item.requirement_id ? null : item.requirement_id)}>View data blindspots</button>
      {openBlindspots === item.requirement_id && <ul>{item.blindspots.map(value => <li key={value}>{value}</li>)}</ul>}
      <footer><span>{item.status}</span><div><button onClick={() => decide(item, "Approve")}>Approve</button><button onClick={() => decide(item, "Edit")}>Edit</button><button onClick={() => decide(item, "Reject")}>Reject</button><button onClick={() => decide(item, "Postpone")}>Postpone</button></div></footer>
    </article>)}</section>
    {!visible.length && <div className="empty">No requirement candidates for this vehicle. Missing evidence stays visible rather than being filled with assumptions.</div>}
  </main>;
}
