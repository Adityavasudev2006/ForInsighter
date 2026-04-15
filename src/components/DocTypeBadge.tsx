import type { DocumentType } from "@/types";
import { Badge } from "@/components/ui/badge";
import { FileImage, FileText, Link, Sheet } from "lucide-react";

export function DocTypeBadge({ type }: { type: DocumentType }) {
  if (type === "pdf") return <Badge variant="outline" className="gap-1 text-xs border-destructive/30 text-destructive"><FileText className="h-3 w-3" />PDF</Badge>;
  if (type === "excel") return <Badge variant="outline" className="gap-1 text-xs border-success/30 text-success"><Sheet className="h-3 w-3" />Excel</Badge>;
  if (type === "csv") return <Badge variant="outline" className="gap-1 text-xs border-success/30 text-success"><Sheet className="h-3 w-3" />CSV</Badge>;
  if (type === "docx") return <Badge variant="outline" className="gap-1 text-xs"><FileText className="h-3 w-3" />DOCX</Badge>;
  if (type === "image") return <Badge variant="outline" className="gap-1 text-xs"><FileImage className="h-3 w-3" />Image</Badge>;
  if (type === "text") return <Badge variant="outline" className="gap-1 text-xs"><Link className="h-3 w-3" />Link</Badge>;
  return <Badge variant="outline" className="text-xs">Unknown</Badge>;
}
