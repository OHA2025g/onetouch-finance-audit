import {
  Warning,
  ShieldWarning,
  Clock,
  Plugs,
  CalendarCheck,
  Scales,
  Bank,
  BookOpen,
  GitMerge,
  UserCircleGear,
  Scroll,
  CurrencyCircleDollar,
  ListChecks,
} from "@phosphor-icons/react";

const TYPE_ICON = {
  case_overdue: Warning,
  exception_highrisk: ShieldWarning,
  approval_pending: Clock,
  connector_failed: Plugs,
  close_critical_task: CalendarCheck,
  reconciliation_overdue: Scales,
  bank_signoff_pending: Bank,
  journal_approval_backlog: BookOpen,
  three_way_match_failure: GitMerge,
  sod_violation: UserCircleGear,
  policy_exception: Scroll,
  treasury_alert: CurrencyCircleDollar,
};

export function ActionQueueTypeIcon({ type, size = 16, className = "" }) {
  const Icon = TYPE_ICON[type] || ListChecks;
  return <Icon size={size} weight="duotone" className={className} aria-hidden />;
}
