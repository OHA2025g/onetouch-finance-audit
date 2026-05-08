import React, { useEffect, useState } from "react";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";

export default function AdminSecurityPage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [cfg, setCfg] = useState(null);

  useEffect(() => {
    setLoading(true);
    http
      .get("/system/security-config")
      .then((r) => setCfg(r.data))
      .catch(() => toast.error("Failed to load security config"))
      .finally(() => setLoading(false));
  }, []);

  const config = cfg?.config || {};
  const fieldMasking = config.field_masking || {};
  const rbac = config.rbac || {};

  const setConfig = (patch) => {
    setCfg((prev) => ({ ...(prev || {}), config: { ...(prev?.config || {}), ...patch } }));
  };

  const save = async () => {
    setSaving(true);
    try {
      const { data } = await http.post("/system/security-config", { config: cfg?.config || {} });
      setCfg(data);
      toast.success("Security config saved");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Save failed");
    }
    setSaving(false);
  };

  if (loading) {
    return <div className="crt-overline p-8 text-muted-foreground">Loading security config…</div>;
  }

  return (
    <PageShell maxWidth="max-w-[1200px]">
      <div data-testid="admin-security-page">
        <PageHeader
          kicker="ADMIN"
          title="Security configuration"
          subtitle="Enterprise hardening toggles for masking and scope enforcement (Phase 40)."
          right={
            <button
              type="button"
              onClick={save}
              disabled={saving}
              className="inline-flex items-center gap-2 rounded-sm border border-primary bg-primary px-4 py-2 text-xs font-medium uppercase tracking-wider text-white disabled:opacity-50"
              data-testid="admin-security-save"
            >
              {saving ? "Saving…" : "Save"}
            </button>
          }
        />

        <SectionCard kicker="MASKING" title="Field masking">
          <div className="space-y-3 text-sm">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={!!fieldMasking.enabled}
                onChange={(e) =>
                  setConfig({
                    field_masking: { ...fieldMasking, enabled: e.target.checked },
                  })
                }
              />
              Enable masking (UI + API responses where supported)
            </label>

            <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={fieldMasking.mask_email !== false}
                  onChange={(e) =>
                    setConfig({
                      field_masking: { ...fieldMasking, mask_email: e.target.checked },
                    })
                  }
                />
                Mask emails
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={fieldMasking.mask_bank_account !== false}
                  onChange={(e) =>
                    setConfig({
                      field_masking: { ...fieldMasking, mask_bank_account: e.target.checked },
                    })
                  }
                />
                Mask bank account numbers
              </label>
            </div>
          </div>
        </SectionCard>

        <SectionCard kicker="RBAC" title="Scope enforcement" className="mt-4">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={!!rbac.entity_scope_enforced}
              onChange={(e) =>
                setConfig({
                  rbac: { ...rbac, entity_scope_enforced: e.target.checked },
                })
              }
            />
            Enforce entity scoping consistently (requires module support)
          </label>
          <p className="mt-2 text-sm text-muted-foreground">
            This toggle records policy intent. Enforcing field masking and entity scoping requires per-endpoint support.
          </p>
        </SectionCard>
      </div>
    </PageShell>
  );
}

