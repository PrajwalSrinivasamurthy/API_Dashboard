"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

export default function VirtualKeyRevealPage() {
  const params = useParams();
  const token = typeof params?.token === "string" ? params.token : "";
  const [key, setKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!token) {
      setError("Invalid link.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    setKey(null);
    try {
      const r = await fetch(`/api/public/vk/${encodeURIComponent(token)}`, {
        cache: "no-store",
      });
      const text = await r.text();
      let body: { key?: string; detail?: string | string[] } = {};
      try {
        body = JSON.parse(text) as typeof body;
      } catch {
        setError("Unexpected response.");
        return;
      }
      if (!r.ok) {
        const d = body.detail;
        setError(
          typeof d === "string"
            ? d
            : Array.isArray(d)
              ? d.map(String).join(", ")
              : r.status === 404
                ? "This link is invalid, expired, or was already used."
                : `Request failed (${r.status})`
        );
        return;
      }
      if (body.key) setKey(body.key);
      else setError("No key in response.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load]);

  async function copyKey() {
    if (!key) return;
    try {
      await navigator.clipboard.writeText(key);
    } catch {
      setError("Could not copy to clipboard.");
    }
  }

  return (
    <div className="mx-auto flex min-h-[60vh] max-w-2xl flex-col justify-center px-4 py-16">
      <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-8">
        <h1 className="text-lg font-semibold text-white">Virtual key</h1>
        <p className="mt-1 text-xs text-[var(--muted)]">
          One-time view. Your IP is saved for this key — only this network can use it with the proxy.
          Refreshing or reopening this link will not show the key again.
        </p>

        {loading && (
          <p className="mt-6 text-sm text-[var(--muted)]">Loading…</p>
        )}

        {!loading && error && (
          <p className="mt-6 text-sm text-red-300" role="alert">
            {error}
          </p>
        )}

        {!loading && key && (
          <div className="mt-6 space-y-4">
            <p className="text-xs font-medium text-[var(--muted)]">Copy this key (single line)</p>
            <pre className="break-all rounded-lg bg-black/50 p-4 font-mono text-sm leading-relaxed text-white">
              {key}
            </pre>
            <button
              type="button"
              onClick={() => void copyKey()}
              className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:bg-blue-600"
            >
              Copy key
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
