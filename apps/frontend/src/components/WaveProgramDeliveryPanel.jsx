import React, { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { SectionCard } from "@/components/PageShell";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "@/components/DataTable";
import { PARAM_LABELS, PARAM_TARGET, WAVE_META } from "@/data/waveProgramDeliveryModel";
import {
  aggregateParamCompletion,
  applyRecheckCloseGaps,
  applyWaveDeliveryAction,
  buildInitialModuleStates,
  isProgramTargetAchieved,
  isWaveUnlockedForDelivery,
  maxUnlockedWaveIndex,
  modulesInWave,
  waveAggregateCompletion,
  WAVE_UNLOCK_MIN_PARAM,
} from "@/lib/waveProgramSimulation";
import { CheckCircle2, Lock } from "lucide-react";

const LS_KEY = "onetouch-wave-program-delivery-v1";

function loadPersistedModules() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed?.modules || !Array.isArray(parsed.modules) || parsed.modules.length !== 40) return null;
    const ok = parsed.modules.every(
      (m) =>
        typeof m.id === "number" &&
        typeof m.wave === "number" &&
        typeof m.name === "string" &&
        Array.isArray(m.parameters) &&
        m.parameters.length === 8 &&
        ["L2", "L3", "L4"].includes(m.depth) &&
        ["Partial", "Mostly complete", "Complete*", "Fully Complete"].includes(m.status)
    );
    return ok ? parsed.modules : null;
  } catch {
    return null;
  }
}

function persistModules(modules) {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify({ modules, savedAt: new Date().toISOString() }));
  } catch {
    /* ignore quota */
  }
}

function statusBadgeVariant(status) {
  if (status === "Fully Complete") return "default";
  if (status === "Complete*") return "secondary";
  if (status === "Mostly complete") return "outline";
  return "outline";
}

export default function WaveProgramDeliveryPanel() {
  const [modules, setModules] = useState(() => loadPersistedModules() || buildInitialModuleStates());

  useEffect(() => {
    persistModules(modules);
  }, [modules]);

  const programDone = useMemo(() => isProgramTargetAchieved(modules), [modules]);
  const overallPct = useMemo(() => Math.round(aggregateParamCompletion(modules) * 1000) / 10, [modules]);
  const maxUnlocked = useMemo(() => maxUnlockedWaveIndex(modules), [modules]);
  const fullyCompleteCount = useMemo(() => modules.filter((m) => m.status === "Fully Complete").length, [modules]);

  const onSimulateWave = useCallback((waveId) => {
    setModules((prev) => {
      if (!isWaveUnlockedForDelivery(waveId, prev)) {
        toast.message(`Wave ${waveId} is locked`, {
          description: `Complete prior wave (every module min ≥ ${WAVE_UNLOCK_MIN_PARAM}) to unlock.`,
        });
        return prev;
      }
      const next = applyWaveDeliveryAction(prev, waveId, "simulate");
      toast.success(`Simulated delivery · Wave ${waveId}`);
      return next;
    });
  }, []);

  const onAdvanceWave = useCallback((waveId) => {
    setModules((prev) => {
      if (!isWaveUnlockedForDelivery(waveId, prev)) {
        toast.message(`Wave ${waveId} is locked`);
        return prev;
      }
      const next = applyWaveDeliveryAction(prev, waveId, "advance");
      toast.success(`Advanced wave ${waveId}`);
      return next;
    });
  }, []);

  const onRecheck = useCallback(() => {
    setModules((prev) => {
      const next = applyRecheckCloseGaps(prev);
      toast.success("Recheck / close gaps applied", {
        description: `Unlocked waves 0–${maxUnlockedWaveIndex(prev)} nudged toward 100.`,
      });
      return next;
    });
  }, []);

  const onResetDemo = useCallback(() => {
    setModules(buildInitialModuleStates());
    try {
      localStorage.removeItem(LS_KEY);
    } catch {
      /* ignore */
    }
    toast.message("Program reset to demo seed");
  }, []);

  return (
    <div className="space-y-6" data-testid="wave-program-delivery-panel">
      {programDone ? (
        <Alert
          className="border-emerald-500/50 bg-emerald-500/10 text-foreground dark:border-emerald-400/40"
          data-testid="wave-program-target-achieved-banner"
        >
          <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
          <AlertTitle>Program target achieved</AlertTitle>
          <AlertDescription>
            All 40 modules are at 100 across eight parameters, depth L4, and status Fully Complete. Parallel wave delivery
            is closed out for this program slice.
          </AlertDescription>
        </Alert>
      ) : null}

      <SectionCard
        kicker="DELIVERY MODEL · WAVES 0–8"
        title="Parallel wave program (40 modules × 8 parameters)"
        right={
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="crt-num">
              Overall {overallPct}%
            </Badge>
            <Badge variant="secondary" className="crt-num">
              Fully complete {fullyCompleteCount}/40
            </Badge>
            <Button type="button" variant="default" size="sm" onClick={onRecheck} data-testid="wave-program-recheck">
              Run recheck / close gaps
            </Button>
            <Button type="button" variant="outline" size="sm" onClick={onResetDemo} data-testid="wave-program-reset">
              Reset demo
            </Button>
          </div>
        }
      >
        <p className="text-sm text-muted-foreground mb-4">
          Waves run in parallel in-product: each card shows live progress. Wave <span className="crt-num">N</span>{" "}
          unlocks when every module in wave <span className="crt-num">N−1</span> reaches min parameter ≥{" "}
          <span className="crt-num">{WAVE_UNLOCK_MIN_PARAM}</span>. Use per-wave actions plus global recheck until all
          parameters hit <span className="crt-num">100</span>, depth <span className="font-medium">L4</span>, and{" "}
          <span className="font-medium">Fully Complete</span>.
        </p>

        <div className="overflow-x-auto pb-2 mb-6">
          <div className="flex gap-3 min-w-min">
            {WAVE_META.map(({ wave, title, blurb }) => {
              const unlocked = isWaveUnlockedForDelivery(wave, modules);
              const pct = Math.round(waveAggregateCompletion(modules, wave) * 1000) / 10;
              const locked = !unlocked;
              return (
                <div
                  key={wave}
                  className="crt-card flex w-[200px] shrink-0 flex-col gap-2 border border-border p-3 text-left"
                  data-testid={`wave-card-${wave}`}
                >
                  <div className="flex items-start justify-between gap-1">
                    <div className="min-w-0">
                      <div className="crt-overline text-[10px] text-muted-foreground">Wave {wave}</div>
                      <div className="mt-1 text-xs font-semibold leading-tight text-foreground line-clamp-2">{title}</div>
                    </div>
                    {locked ? <Lock className="h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-label="Locked" /> : null}
                  </div>
                  <p className="text-[10px] leading-snug text-muted-foreground line-clamp-3">{blurb}</p>
                  <div className="space-y-1">
                    <div className="flex justify-between text-[10px] text-muted-foreground">
                      <span>Params vs target</span>
                      <span className="crt-num font-medium text-foreground">{pct}%</span>
                    </div>
                    <Progress value={pct} className="h-1.5" />
                  </div>
                  <div className="mt-auto flex flex-col gap-1.5">
                    <Button
                      type="button"
                      size="sm"
                      variant="secondary"
                      className="h-8 text-[11px]"
                      disabled={locked}
                      onClick={() => onSimulateWave(wave)}
                      data-testid={`wave-${wave}-simulate`}
                    >
                      Simulate wave delivery
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      className="h-8 text-[11px]"
                      disabled={locked}
                      onClick={() => onAdvanceWave(wave)}
                      data-testid={`wave-${wave}-advance`}
                    >
                      Advance wave
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="text-xs text-muted-foreground mb-2">
          Next unlock: waves through <span className="crt-num font-medium text-foreground">{maxUnlocked}</span> are open
          for delivery actions and recheck.
        </div>

        <Accordion type="multiple" defaultValue={WAVE_META.map((w) => `wave-${w.wave}`)} className="w-full border-t border-border pt-2">
          {WAVE_META.map(({ wave, title }) => {
            const rows = modulesInWave(modules, wave);
            return (
              <AccordionItem value={`wave-${wave}`} key={wave} className="border-border">
                <AccordionTrigger className="text-sm hover:no-underline">
                  <span className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{title}</span>
                    <Badge variant="outline" className="crt-num font-normal">
                      {rows.length} modules
                    </Badge>
                    <Badge variant="secondary" className="crt-num font-normal">
                      {Math.round(waveAggregateCompletion(modules, wave) * 1000) / 10}%
                    </Badge>
                  </span>
                </AccordionTrigger>
                <AccordionContent>
                  <div className="overflow-x-auto rounded-md border border-border">
                    <DataTable
                      className="rounded-none border-0 bg-transparent min-w-[1100px]"
                      maxHeightClassName="max-h-80"
                      testId={`wave-${wave}-modules`}
                    >
                      <DataTableHead>
                        <tr>
                          <DataTableTh className="w-10">#</DataTableTh>
                          <DataTableTh className="min-w-[160px]">Module</DataTableTh>
                          {PARAM_LABELS.map((label, i) => (
                            <DataTableTh key={label} className="text-[10px] whitespace-nowrap px-1" title={label}>
                              P{i + 1}
                            </DataTableTh>
                          ))}
                          <DataTableTh>Depth</DataTableTh>
                          <DataTableTh>Status</DataTableTh>
                        </tr>
                      </DataTableHead>
                      <DataTableBody>
                        {rows.map((m) => (
                          <DataTableRow key={m.id}>
                            <DataTableTd className="crt-num text-xs text-muted-foreground">{m.id}</DataTableTd>
                            <DataTableTd className="text-xs font-medium text-foreground">{m.name}</DataTableTd>
                            {m.parameters.map((p, i) => (
                              <DataTableTd key={PARAM_LABELS[i]} className="crt-num whitespace-nowrap px-1 text-[10px]">
                                {p}/{PARAM_TARGET}
                              </DataTableTd>
                            ))}
                            <DataTableTd className="text-xs">{m.depth}</DataTableTd>
                            <DataTableTd className="text-xs">
                              <Badge variant={statusBadgeVariant(m.status)} className="font-normal">
                                {m.status}
                              </Badge>
                            </DataTableTd>
                          </DataTableRow>
                        ))}
                      </DataTableBody>
                    </DataTable>
                  </div>
                  <p className="mt-2 text-[10px] text-muted-foreground">
                    P1–P8: {PARAM_LABELS.join(" · ")}. Target {PARAM_TARGET} on each.
                  </p>
                </AccordionContent>
              </AccordionItem>
            );
          })}
        </Accordion>
      </SectionCard>
    </div>
  );
}
