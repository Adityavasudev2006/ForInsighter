import type { ProcessingStatus } from "@/types";
import { Badge } from "@/components/ui/badge";
import { Loader2, CheckCircle2, XCircle, Clock } from "lucide-react";

const config: Record<ProcessingStatus, { label: string; className: string; icon: React.ReactNode }> = {
  queued: { label: "Queued", className: "bg-muted text-muted-foreground", icon: <Clock className="h-3 w-3" /> },
  processing: { label: "Processing", className: "bg-info/15 text-info", icon: <Loader2 className="h-3 w-3 animate-spin" /> },
  done: { label: "Done", className: "bg-success/15 text-success", icon: <CheckCircle2 className="h-3 w-3" /> },
  failed: { label: "Failed", className: "bg-destructive/15 text-destructive", icon: <XCircle className="h-3 w-3" /> },
};

export function StatusChip({ status }: { status: ProcessingStatus }) {
  const c = config[status];
  return (
    <Badge variant="outline" className={`gap-1 text-xs font-medium border-0 ${c.className}`}>
      {c.icon}
      {c.label}
    </Badge>
  );
}
