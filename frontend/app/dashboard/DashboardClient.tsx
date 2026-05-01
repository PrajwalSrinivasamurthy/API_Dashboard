"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import type {
  AdminUsage,
  CreateKeyResponse,
  ProjectKeyRow,
} from "@/lib/types";

type Tab = "overview" | "keys" | "new-key";

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

function fmtUsd(s: string | number): string {
  const n = typeof s === "string" ? parseFloat(s) : s;
  if (Number.isNaN(n)) return String(s);
  return n.toLocaleString(undefined, {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 6,
  });
}

async function parseJson<T>(r: Response): Promise<T | null> {
  const text = await r.text();
  if (!text) return null;
  try {
    return JSON.parse(text) as T;
  } catch {
    return null;
  }
}

export function DashboardClient({
  serverConfigured,
}: {
  serverConfigured: boolean;
}) {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("overview");
  const [usage, setUsage] = useState<AdminUsage | null>(null);
  const [keys, setKeys] = useState<ProjectKeyRow[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);
  const [createdKey, setCreatedKey] = useState<CreateKeyResponse | null>(null);

  const [showPassword, setShowPassword] = useState(false);
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordBusy, setPasswordBusy] = useState(false);
  const [passwordOk, setPasswordOk] = useState(false);

  const loadUsage = useCallback(async () => {
    setError(null);
    const r = await fetch("/api/admin/usage");
    if (!r.ok) {
      const j = await parseJson<{ detail?: string }>(r);
      setError(j?.detail ?? `Usage failed (${r.status})`);
      setUsage(null);
      return;
    }
    const data = await parseJson<AdminUsage>(r);
    setUsage(data);
  }, []);

  const loadKeys = useCallback(async () => {
    setError(null);
    const r = await fetch("/api/admin/project-keys");
    if (!r.ok) {
      const j = await parseJson<{ detail?: string }>(r);
      setError(j?.detail ?? `Keys failed (${r.status})`);
      setKeys(null);
      return;
    }
    const data = await parseJson<ProjectKeyRow[]>(r);
    setKeys(Array.isArray(data) ? data : []);
  }, []);

  const refreshAll = useCallback(async () => {
    setLoading(true);
    try {
      await Promise.all([loadUsage(), loadKeys()]);
    } finally {
      setLoading(false);
    }
  }, [loadUsage, loadKeys]);

  useEffect(() => {
    if (!serverConfigured) return;
    void refreshAll();
  }, [serverConfigured, refreshAll]);

  useEffect(() => {
    if (tab === "keys" && serverConfigured && keys === null && !loading) {
      void loadKeys();
    }
  }, [tab, serverConfigured, keys, loading, loadKeys]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    setCreating(true);
    setError(null);
    setCreatedKey(null);
    try {
      const r = await fetch("/api/admin/create-key", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newName.trim() }),
      });
      const data = await parseJson<CreateKeyResponse & { detail?: string }>(r);
      if (!r.ok) {
        setError(data?.detail ?? `Create failed (${r.status})`);
        return;
      }
      if (data && data.reveal_token) {
        const origin =
          typeof window !== "undefined" ? window.location.origin : "";
        setCreatedKey({
          ...data,
          revealUrl: `${origin}/vk/${data.reveal_token}`,
        });
        setNewName("");
        await refreshAll();
      }
    } finally {
      setCreating(false);
    }
  }

  async function handleDisable(id: number, name: string) {
    if (!window.confirm(`Disable project key for "${name}"?`)) return;
    setError(null);
    const r = await fetch("/api/admin/disable-key", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id }),
    });
    if (!r.ok && r.status !== 204) {
      const j = await parseJson<{ detail?: string }>(r);
      setError(j?.detail ?? `Disable failed (${r.status})`);
      return;
    }
    await refreshAll();
  }

  async function copyText(text: string) {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      setError("Could not copy to clipboard");
    }
  }

  async function handleLogout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.replace("/login");
    router.refresh();
  }

  async function handleChangePassword(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (newPassword.length < 8) {
      setError("New password must be at least 8 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("New password and confirmation do not match.");
      return;
    }
    setPasswordBusy(true);
    setPasswordOk(false);
    try {
      const r = await fetch("/api/auth/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          old_password: oldPassword,
          new_password: newPassword,
        }),
      });
      const j = await parseJson<{ detail?: string | string[] }>(r);
      if (!r.ok) {
        const d = j?.detail;
        setError(
          typeof d === "string"
            ? d
            : Array.isArray(d)
              ? d.map(String).join(", ")
              : `Change failed (${r.status})`
        );
        return;
      }
      setOldPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setShowPassword(false);
      setPasswordOk(true);
    } finally {
      setPasswordBusy(false);
    }
  }

  if (!serverConfigured) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16">
        <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-6 text-amber-100">
          <h1 className="text-lg font-semibold">Configuration required</h1>
          <p className="mt-2 text-sm text-amber-200/90">
            Set <code className="rounded bg-black/30 px-1">BACKEND_URL</code>,{" "}
            <code className="rounded bg-black/30 px-1">ADMIN_API_KEY</code>, and{" "}
            <code className="rounded bg-black/30 px-1">JWT_SECRET</code> in{" "}
            <code className="rounded bg-black/30 px-1">frontend/.env.local</code>{" "}
            (<code className="rounded bg-black/30 px-1">JWT_SECRET</code> must match
            the backend), then restart{" "}
            <code className="rounded bg-black/30 px-1">next dev</code>.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <header className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-white">
            API Dashboard 
          </h1>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => {
              setShowPassword((v) => !v);
              setError(null);
              setPasswordOk(false);
            }}
            className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-2 text-sm font-medium text-white transition hover:bg-white/5"
          >
            {showPassword ? "Close" : "Change password"}
          </button>
          <button
            type="button"
            onClick={() => void handleLogout()}
            className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-2 text-sm font-medium text-[var(--muted)] transition hover:bg-white/5 hover:text-white"
          >
            Log out
          </button>
          <button
            type="button"
            onClick={() => void refreshAll()}
            disabled={loading}
            className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-2 text-sm font-medium text-white transition hover:bg-white/5 disabled:opacity-50"
          >
            {loading ? "Refreshing…" : "Refresh data"}
          </button>
        </div>
      </header>

      {showPassword && (
        <section className="mb-6 max-w-md rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6">
          <h2 className="text-sm font-medium text-white">Update password</h2>
          <p className="mt-1 text-xs text-[var(--muted)]">
            New password must be at least 8 characters (bcrypt max 72).
          </p>
          <form onSubmit={handleChangePassword} className="mt-4 space-y-3">
            <div>
              <label
                htmlFor="old-pw"
                className="block text-xs font-medium text-[var(--muted)]"
              >
                Current password
              </label>
              <input
                id="old-pw"
                type="password"
                autoComplete="current-password"
                value={oldPassword}
                onChange={(e) => setOldPassword(e.target.value)}
                required
                className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-white focus:border-[var(--accent)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
              />
            </div>
            <div>
              <label
                htmlFor="new-pw"
                className="block text-xs font-medium text-[var(--muted)]"
              >
                New password
              </label>
              <input
                id="new-pw"
                type="password"
                autoComplete="new-password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                minLength={8}
                maxLength={72}
                className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-white focus:border-[var(--accent)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
              />
            </div>
            <div>
              <label
                htmlFor="confirm-pw"
                className="block text-xs font-medium text-[var(--muted)]"
              >
                Confirm new password
              </label>
              <input
                id="confirm-pw"
                type="password"
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                minLength={8}
                maxLength={72}
                className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-white focus:border-[var(--accent)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
              />
            </div>
            <button
              type="submit"
              disabled={passwordBusy}
              className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:bg-blue-600 disabled:opacity-50"
            >
              {passwordBusy ? "Saving…" : "Save new password"}
            </button>
          </form>
        </section>
      )}

      {passwordOk && (
        <div
          className="mb-6 rounded-lg border border-[var(--success)]/40 bg-[var(--success)]/10 px-4 py-3 text-sm text-[var(--success)]"
          role="status"
        >
          Password updated. Use your new password next time you sign in.
        </div>
      )}

      {error && (
        <div
          className="mb-6 rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-200"
          role="alert"
        >
          {error}
        </div>
      )}

      <nav className="mb-6 flex gap-2 border-b border-[var(--border)] pb-px">
        {(
          [
            ["overview", "Usage overview"],
            ["keys", "Project keys"],
            ["new-key", "Virtual key"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => {
              setTab(id);
              if (id === "new-key") setCreatedKey(null);
            }}
            className={`border-b-2 px-4 py-2 text-sm font-medium transition ${
              tab === id
                ? "border-[var(--accent)] text-white"
                : "border-transparent text-[var(--muted)] hover:text-white"
            }`}
          >
            {label}
          </button>
        ))}
      </nav>

      {tab === "overview" && (
        <section className="space-y-6">
          {usage === null && loading ? (
            <p className="text-[var(--muted)]">Loading usage…</p>
          ) : usage ? (
            <>
              <div className="grid gap-4 sm:grid-cols-3">
                <Metric
                  label="Total tokens"
                  value={usage.total_tokens.toLocaleString()}
                />
                <Metric
                  label="Total cost (est.)"
                  value={fmtUsd(usage.total_cost)}
                />
                <Metric
                  label="Projects"
                  value={String(usage.per_project.length)}
                />
              </div>
              <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface)]">
                <h2 className="border-b border-[var(--border)] px-4 py-3 text-sm font-medium text-white">
                  Per project (from <code className="text-xs">usage_logs</code>{" "}
                  + <code className="text-xs">project_keys</code>)
                </h2>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="border-b border-[var(--border)] text-[var(--muted)]">
                        <th className="px-4 py-3 font-medium">Project</th>
                        <th className="px-4 py-3 font-medium">Key id</th>
                        <th className="px-4 py-3 font-medium">Tokens</th>
                        <th className="px-4 py-3 font-medium">Cost</th>
                        <th className="px-4 py-3 font-medium">Last used</th>
                      </tr>
                    </thead>
                    <tbody>
                      {usage.per_project.length === 0 ? (
                        <tr>
                          <td
                            colSpan={5}
                            className="px-4 py-8 text-center text-[var(--muted)]"
                          >
                            No usage logged yet (non-streaming completions write
                            logs).
                          </td>
                        </tr>
                      ) : (
                        usage.per_project.map((row) => (
                          <tr
                            key={row.project_key_id}
                            className="border-b border-[var(--border)]/60 last:border-0"
                          >
                            <td className="px-4 py-3 font-medium text-white">
                              {row.project_name}
                            </td>
                            <td className="px-4 py-3 text-[var(--muted)]">
                              {row.project_key_id}
                            </td>
                            <td className="px-4 py-3">
                              {row.total_tokens.toLocaleString()}
                            </td>
                            <td className="px-4 py-3">{fmtUsd(row.total_cost)}</td>
                            <td className="px-4 py-3 text-[var(--muted)]">
                              {fmtDate(row.last_used)}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          ) : (
            <p className="text-[var(--muted)]">No usage data.</p>
          )}
        </section>
      )}

      {tab === "keys" && (
        <section>
          <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface)]">
            <h2 className="border-b border-[var(--border)] px-4 py-3 text-sm font-medium text-white">
              <code className="text-xs">project_keys</code> table
            </h2>
            {keys === null && loading ? (
              <p className="px-4 py-8 text-[var(--muted)]">Loading…</p>
            ) : keys && keys.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-[var(--border)] text-[var(--muted)]">
                      <th className="px-4 py-3 font-medium">ID</th>
                      <th className="px-4 py-3 font-medium">Name</th>
                      <th className="px-4 py-3 font-medium">Active</th>
                      <th className="px-4 py-3 font-medium">Used tokens</th>
                      <th className="px-4 py-3 font-medium">Created</th>
                      <th className="px-4 py-3 font-medium">Bound IP</th>
                      <th className="px-4 py-3 font-medium">Budget</th>
                      <th className="px-4 py-3 font-medium">Spent</th>
                      <th className="px-4 py-3 font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {keys.map((k) => (
                      <tr
                        key={k.id}
                        className="border-b border-[var(--border)]/60 last:border-0"
                      >
                        <td className="px-4 py-3 text-[var(--muted)]">{k.id}</td>
                        <td className="px-4 py-3 font-medium text-white">
                          {k.name}
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={
                              k.active
                                ? "text-[var(--success)]"
                                : "text-[var(--muted)]"
                            }
                          >
                            {k.active ? "Yes" : "No"}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          {k.used_tokens.toLocaleString()}
                        </td>
                        <td className="px-4 py-3 text-[var(--muted)]">
                          {fmtDate(k.created_at)}
                        </td>
                        <td className="px-4 py-3 font-mono text-xs text-[var(--muted)]">
                          {k.allowed_client_ip ?? "—"}
                        </td>
                        <td className="px-4 py-3 text-[var(--muted)]">
                          {fmtUsd(k.budget_usd)}
                        </td>
                        <td className="px-4 py-3 text-[var(--muted)]">
                          {fmtUsd(k.spent_usd)}
                        </td>
                        <td className="px-4 py-3">
                          {k.active ? (
                            <button
                              type="button"
                              onClick={() => void handleDisable(k.id, k.name)}
                              className="rounded-md border border-red-500/50 px-2 py-1 text-xs font-medium text-red-300 hover:bg-red-500/10"
                            >
                              Disable
                            </button>
                          ) : (
                            <span className="text-xs text-[var(--muted)]">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="px-4 py-8 text-[var(--muted)]">
                No project keys yet. Open the <strong>Virtual key</strong> tab
                to create one.
              </p>
            )}
          </div>
        </section>
      )}

      {tab === "new-key" && (
        <section className="max-w-xl space-y-6">
          <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6">
            <h2 className="text-sm font-medium text-white">Create virtual key</h2>
            <p className="mt-1 text-xs text-[var(--muted)]">
              Creates a <code className="rounded bg-black/30 px-1">sk_proj_…</code> key and a{" "}
              <strong>one-time link</strong> you can send. The recipient opens the link, copies the
              key once, and the link stops working (same lifetime as your dashboard session JWT).
            </p>
            <form onSubmit={handleCreate} className="mt-4 space-y-4">
              <div>
                <label
                  htmlFor="name"
                  className="block text-xs font-medium text-[var(--muted)]"
                >
                  Project name
                </label>
                <input
                  id="name"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="e.g. Continue — work laptop"
                  className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-white placeholder:text-[var(--muted)] focus:border-[var(--accent)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
                  required
                  minLength={1}
                  maxLength={255}
                />
              </div>
              <button
                type="submit"
                disabled={creating || !newName.trim()}
                className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:bg-blue-600 disabled:opacity-50"
              >
                {creating ? "Creating…" : "Create virtual key"}
              </button>
            </form>
          </div>

          {createdKey?.revealUrl && (
            <div className="rounded-xl border border-[var(--success)]/40 bg-[var(--success)]/10 p-6">
              <h3 className="text-sm font-semibold text-[var(--success)]">
                Share this one-time link
              </h3>
              <p className="mt-1 text-xs text-[var(--muted)]">
                {createdKey.message ??
                  "The virtual key is not shown here. Send the link; it expires after first view or when the time below passes."}
              </p>
              <p className="mt-2 text-xs text-[var(--muted)]">
                Link valid until:{" "}
                <span className="text-white">{fmtDate(createdKey.reveal_expires_at)}</span>
              </p>
              <pre className="mt-3 overflow-x-auto whitespace-pre-wrap break-all rounded-lg bg-black/40 p-3 font-mono text-xs leading-relaxed text-white">
                {createdKey.revealUrl}
              </pre>
              <button
                type="button"
                onClick={() => void copyText(createdKey.revealUrl!)}
                className="mt-3 rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-medium text-white hover:bg-white/5"
              >
                Copy link
              </button>
            </div>
          )}
        </section>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4 py-4">
      <p className="text-xs font-medium text-[var(--muted)]">{label}</p>
      <p className="mt-1 text-xl font-semibold text-white">{value}</p>
    </div>
  );
}
