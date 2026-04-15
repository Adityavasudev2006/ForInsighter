import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useApp } from "@/context/AppContext";
import { StatusChip } from "@/components/StatusChip";
import { DocTypeBadge } from "@/components/DocTypeBadge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { ArrowLeft, Eye, FileJson, FileSpreadsheet, FileText, Download, ChevronDown, Moon, Sun, Trash2 } from "lucide-react";
import { toggleTheme } from "@/lib/theme";
import { toast } from "sonner";
import { deleteDocument, exportDoc, getBatchStatus, getDocuments, startBatch } from "@/api/client";
import { Progress } from "@/components/ui/progress";

export default function BatchProcessing() {
  const { documents, setDocuments } = useApp();
  const navigate = useNavigate();
  const [taskId, setTaskId] = useState<string | null>(null);
  const [status, setStatus] = useState<{
    task_id: string;
    status: string;
    total: number;
    completed: number;
    failed: number;
  } | null>(null);

  useEffect(() => {
    if (!taskId) return;
    const timer = setInterval(async () => {
      const data = await getBatchStatus(taskId);
      setStatus(data);
    }, 2000);
    return () => clearInterval(timer);
  }, [taskId]);

  useEffect(() => {
    getDocuments()
      .then(setDocuments)
      .catch(() => toast.error("Failed to load documents"));
  }, [setDocuments]);

  const handleExport = (format: string) => {
    toast.success(`Exporting all documents as ${format}...`);
  };

  const handleAction = (action: string, fileName: string) => {
    toast.success(`${action}: ${fileName}`);
  };

  const handleStartBatch = async () => {
    const res = await startBatch(documents.map((d) => d.id));
    setTaskId(res.task_id);
    toast.success("Batch started");
  };

  const handleDelete = async (docId: string) => {
    try {
      await deleteDocument(docId);
      setDocuments((prev) => prev.filter((doc) => doc.id !== docId));
      toast.success("Document deleted");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to delete document");
    }
  };

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <header className="h-14 border-b border-border flex items-center px-6 gap-3 bg-card">
        <Button variant="ghost" size="icon" onClick={() => navigate("/dashboard")}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <h1 className="font-semibold text-foreground">Batch Processing</h1>
        <span className="text-sm text-muted-foreground">{documents.length} documents</span>
        <Button variant="outline" onClick={handleStartBatch}>Start Batch</Button>
        <div className="flex-1" />
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" className="gap-2">
              <Download className="h-4 w-4" />
              Export All
              <ChevronDown className="h-3 w-3" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem onClick={() => handleExport("JSON")}>
              <FileJson className="h-4 w-4 mr-2" /> Export as JSON
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => handleExport("CSV")}>
              <FileSpreadsheet className="h-4 w-4 mr-2" /> Export as CSV
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => handleExport("PDF")}>
              <FileText className="h-4 w-4 mr-2" /> Export as PDF
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
        <Button variant="ghost" size="icon" onClick={toggleTheme}>
          <Sun className="h-4 w-4 rotate-0 scale-100 transition-transform dark:-rotate-90 dark:scale-0" />
          <Moon className="absolute h-4 w-4 rotate-90 scale-0 transition-transform dark:rotate-0 dark:scale-100" />
        </Button>
      </header>

      <main className="flex-1 p-6 overflow-auto">
        {status && (
          <div className="mb-4 rounded-md border border-border p-4">
            <p className="text-sm mb-2">Task {status.task_id}: {status.status}</p>
            <Progress value={status.total ? ((status.completed + status.failed) / status.total) * 100 : 0} />
          </div>
        )}
        <div className="rounded-lg border border-border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>File Name</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Size</TableHead>
                <TableHead>Uploaded</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {documents.map((doc) => (
                <TableRow key={doc.id}>
                  <TableCell className="font-medium text-foreground">{doc.filename}</TableCell>
                  <TableCell><DocTypeBadge type={doc.file_type} /></TableCell>
                  <TableCell><StatusChip status={doc.status} /></TableCell>
                  <TableCell className="text-muted-foreground text-sm">--</TableCell>
                  <TableCell className="text-muted-foreground text-sm">{new Date(doc.created_at).toLocaleDateString()}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        disabled={doc.status !== "done"}
                        onClick={() => navigate(`/document/${doc.id}`)}
                      >
                        <Eye className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => exportDoc(doc.id, "json")}>
                        <FileJson className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => exportDoc(doc.id, "csv")}>
                        <FileSpreadsheet className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => exportDoc(doc.id, "pdf")}>
                        <FileText className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => handleDelete(doc.id)}>
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </main>
    </div>
  );
}
