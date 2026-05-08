import React, { useCallback, useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { http } from "../lib/api";
import { toast } from "sonner";
import { useAuth } from "../lib/auth";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";

const ROLE_OPTIONS = [
  "CFO",
  "Controller",
  "Internal Auditor",
  "Compliance Head",
  "Process Owner",
  "External Auditor",
  "Super Admin",
];

export default function SuperAdminPage() {
  const { user } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [creating, setCreating] = useState(false);
  const [focus, setFocus] = useState(null);
  const [form, setForm] = useState({
    email: "",
    full_name: "",
    role: "Process Owner",
    entity: "US-HQ",
    password: "",
  });

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const { data } = await http.get("/admin/users");
      setUsers(Array.isArray(data) ? data : []);
    } catch (e) {
      setErr(e?.response?.data?.detail || "Could not load users");
      toast.error("Failed to load users");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user?.role === "Super Admin") load();
  }, [user, load]);

  if (!user) return null;
  if (user.role !== "Super Admin") {
    return <Navigate to="/app/cfo" replace />;
  }

  const submit = async (ev) => {
    ev.preventDefault();
    setCreating(true);
    try {
      await http.post("/admin/users", {
        email: form.email.trim().toLowerCase(),
        full_name: form.full_name.trim(),
        role: form.role,
        entity: form.entity.trim() || "US-HQ",
        password: form.password,
      });
      toast.success("User created");
      setForm({ ...form, email: "", full_name: "", password: "" });
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Create failed");
    } finally {
      setCreating(false);
    }
  };

  const remove = async (row) => {
    if (!window.confirm(`Remove user ${row.email}?`)) return;
    try {
      await http.delete(`/admin/users/${encodeURIComponent(row.id)}`);
      toast.success("User removed");
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Remove failed");
    }
  };

  return (
    <PageShell maxWidth="max-w-[1100px]">
      <PageHeader
        kicker="SUPER ADMIN"
        title="User management"
        subtitle="Create or remove platform users (JWT login identities)."
        right={
          <Link to="/app/admin" className="text-xs font-mono uppercase text-[#0A84FF]">
            Platform admin console →
          </Link>
        }
      />

      <SectionCard kicker="CREATE" title="Add user" bodyClassName="p-6">
        <form onSubmit={submit} className="grid gap-4 md:grid-cols-2">
          <label className="text-xs font-mono text-[#737373] uppercase">
            Email
            <input
              required
              type="email"
              value={form.email}
              onChange={(ev) => setForm({ ...form, email: ev.target.value })}
              className="mt-1 w-full bg-black border border-[#262626] px-3 py-2 text-sm text-white"
            />
          </label>
          <label className="text-xs font-mono text-[#737373] uppercase">
            Full name
            <input
              required
              value={form.full_name}
              onChange={(ev) => setForm({ ...form, full_name: ev.target.value })}
              className="mt-1 w-full bg-black border border-[#262626] px-3 py-2 text-sm text-white"
            />
          </label>
          <label className="text-xs font-mono text-[#737373] uppercase">
            Role
            <select
              value={form.role}
              onChange={(ev) => setForm({ ...form, role: ev.target.value })}
              className="mt-1 w-full bg-black border border-[#262626] px-3 py-2 text-sm text-white"
            >
              {ROLE_OPTIONS.map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
          </label>
          <label className="text-xs font-mono text-[#737373] uppercase">
            Entity
            <input
              value={form.entity}
              onChange={(ev) => setForm({ ...form, entity: ev.target.value })}
              className="mt-1 w-full bg-black border border-[#262626] px-3 py-2 text-sm text-white"
              placeholder="US-HQ"
            />
          </label>
          <label className="text-xs font-mono text-[#737373] uppercase md:col-span-2">
            Password (min 6 chars)
            <input
              required
              type="password"
              minLength={6}
              value={form.password}
              onChange={(ev) => setForm({ ...form, password: ev.target.value })}
              className="mt-1 w-full bg-black border border-[#262626] px-3 py-2 text-sm text-white max-w-md"
            />
          </label>
          <div className="md:col-span-2">
            <button
              type="submit"
              disabled={creating}
              className="px-4 py-2 bg-white text-black font-mono text-xs uppercase disabled:opacity-50"
            >
              {creating ? "Creating…" : "Create user"}
            </button>
          </div>
        </form>
      </SectionCard>

      {focus ? (
        <SectionCard kicker="USER" title="Selected user" bodyClassName="p-6 mt-6" data-testid="super-admin-user-detail">
          <div className="grid gap-2 text-sm text-[#E5E5E5] font-mono text-xs">
            <div><span className="text-[#737373] uppercase">Email</span> — {focus.email}</div>
            <div><span className="text-[#737373] uppercase">Name</span> — {focus.full_name}</div>
            <div><span className="text-[#737373] uppercase">Role</span> — {focus.role}</div>
            <div><span className="text-[#737373] uppercase">Entity</span> — {focus.entity || "—"}</div>
            <div><span className="text-[#737373] uppercase">Status</span> — {focus.status || "—"}</div>
            <div><span className="text-[#737373] uppercase">Id</span> — {focus.id}</div>
          </div>
          <div className="mt-4 flex flex-wrap gap-3 font-mono text-[10px] uppercase">
            <Link to={`/app/drill/user/${encodeURIComponent(focus.email)}`} className="text-[#0A84FF] hover:underline">
              User drill-down →
            </Link>
            <button type="button" onClick={() => setFocus(null)} className="text-[#737373] hover:text-white">
              Clear selection
            </button>
          </div>
        </SectionCard>
      ) : null}

      <SectionCard kicker="DIRECTORY" title="Users" bodyClassName="p-0 overflow-x-auto mt-6">
        {loading ? (
          <div className="p-6 font-mono text-xs text-[#737373]">Loading…</div>
        ) : null}
        {err && !loading ? (
          <div className="p-6 text-sm text-red-300">{err}</div>
        ) : null}
        {!loading && !err ? (
          <DataTable>
            <DataTableHead>
              <tr>
                <DataTableTh>Email</DataTableTh>
                <DataTableTh>Name</DataTableTh>
                <DataTableTh>Role</DataTableTh>
                <DataTableTh>Entity</DataTableTh>
                <DataTableTh />
              </tr>
            </DataTableHead>
            <DataTableBody>
              {users.map((u) => (
                <DataTableRow key={u.id} onClick={() => setFocus(u)} className="cursor-pointer">
                  <DataTableTd className="font-mono text-xs">{u.email}</DataTableTd>
                  <DataTableTd>{u.full_name}</DataTableTd>
                  <DataTableTd>{u.role}</DataTableTd>
                  <DataTableTd>{u.entity || "—"}</DataTableTd>
                  <DataTableTd onClick={(ev) => ev.stopPropagation()}>
                    <button
                      type="button"
                      onClick={() => remove(u)}
                      className="text-xs font-mono uppercase text-[#FF3B30] hover:underline"
                    >
                      Remove
                    </button>
                  </DataTableTd>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        ) : null}
      </SectionCard>
    </PageShell>
  );
}
