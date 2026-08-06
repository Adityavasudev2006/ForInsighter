import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useDropzone } from "react-dropzone";
import { useApp } from "@/context/AppContext";
import { StatusChip } from "@/components/StatusChip";
import { DocTypeBadge } from "@/components/DocTypeBadge";
import { BrandMark } from "@/components/BrandMark";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Card, CardContent } from "@/components/ui/card";
import { Upload, Search, FileUp, PlayCircle, Moon, Sun, ArrowLeft, Trash2 } from "lucide-react";
import { toggleTheme } from "@/lib/theme";
import { toast } from "sonner";
import { deleteDocument, getDocuments, search as searchApi, startBatch, uploadFiles, uploadLink } from "@/api/client";
import type { SearchResult } from "@/types";

export default function Dashboard() {
  const { documents, setDocuments, config } = useApp();
  const [search, setSearch] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [linkUrl, setLinkUrl] = useState("");
  const [linkUploading, setLinkUploading] = useState(false);
  const navigate = useNavigate();

  const loadDocuments = useCallback(async () => {
    const docs = await getDocuments();
    setDocuments(docs);
  }, [setDocuments]);

  useEffect(() => {
    loadDocuments().catch(() => toast.error("Failed to load documents"));
  }, [loadDocuments]);

  useEffect(() => {
    const shouldPoll = documents.some((d) => d.status === "processing" || d.status === "queued");
    if (!shouldPoll) return;
    const timer = setInterval(() => {
      loadDocuments().catch(() => null);
    }, 3000);
    return () => clearInterval(timer);
  }, [documents, loadDocuments]);

  const onDrop = useCallback(
    async (files: File[]) => {
      try {
        setUploading(true);
        setUploadProgress(20);
        await uploadFiles(files, config);
        setUploadProgress(100);
        await loadDocuments();
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Upload failed");
      } finally {
        setTimeout(() => {
          setUploading(false);
          setUploadProgress(0);
        }, 500);
      }
    },
    [loadDocuments, config],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
      "application/vnd.ms-excel": [".xls"],
      "text/csv": [".csv"],
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
      "image/*": [".png", ".jpg", ".jpeg", ".webp"],
    },
    multiple: true,
  });

  const handleBatchProcess = async () => {
    const ids = documents.map((d) => d.id);
    const res = await startBatch(ids);
    toast.success(`Batch started: ${res.task_id}`);
    navigate("/batch");
  };

  const handleUploadLink = async () => {
    const url = linkUrl.trim();
    if (!url) return;
    try {
      setLinkUploading(true);
      await uploadLink(url, config);
      setLinkUrl("");
      await loadDocuments();
      toast.success("Link added for processing");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to process link");
    } finally {
      setLinkUploading(false);
    }
  };

  const handleDeleteDocument = async (docId: string) => {
    try {
      await deleteDocument(docId);
      setDocuments((prev) => prev.filter((doc) => doc.id !== docId));
      toast.success("Document deleted");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to delete document");
    }
  };

  useEffect(() => {
    if (!search.trim()) {
      setSearchResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const results = await searchApi(search);
        setSearchResults(results);
      } catch {
        setSearchResults([]);
      }
    }, 350);
    return () => clearTimeout(timer);
  }, [search]);

  const filtered = useMemo(
    () => documents.filter((d) => d.filename.toLowerCase().includes(search.toLowerCase())),
    [documents, search],
  );

  return (
    <div className="min-h-screen bg-background flex">
      {/* Sidebar */}
      <aside className="w-72 border-r border-border bg-card flex flex-col">
        <div className="p-4 border-b border-border flex items-center gap-2">
          <Button variant="ghost" size="icon" onClick={() => navigate("/")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <h2 className="font-semibold text-foreground text-sm">Documents</h2>
          <span className="ml-auto text-xs text-muted-foreground">{documents.length}</span>
        </div>
        <ScrollArea className="flex-1">
          <div className="p-2 space-y-1">
            {documents.map((doc) => (
              <div key={doc.id} className="w-full p-3 rounded-lg hover:bg-muted/50 transition-colors space-y-1.5">
                <div className="flex items-start gap-2">
                  <button
                    onClick={() => doc.status === "done" && navigate(`/document/${doc.id}`)}
                    className="flex-1 text-left"
                  >
                    <p className="text-sm font-medium text-foreground truncate">{doc.filename}</p>
                  </button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteDocument(doc.id);
                    }}
                  >
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </div>
                <div className="flex items-center gap-2">
                  <DocTypeBadge type={doc.file_type} />
                  <StatusChip status={doc.status} />
                </div>
                {doc.status === "failed" && doc.processing_error && (
                  <p className="text-[11px] text-destructive line-clamp-2">{doc.processing_error}</p>
                )}
              </div>
            ))}
          </div>
        </ScrollArea>
      </aside>

      {/* Main */}
      <main className="flex-1 flex flex-col">
        <header className="h-14 border-b border-border flex items-center px-6 gap-4">
          <div className="flex items-center gap-2">
            <BrandMark className="h-6 w-6 text-foreground" />
            <h1 className="font-semibold text-foreground">ForInsighter</h1>
          </div>
          <div className="flex-1" />
          <div className="relative w-72">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Semantic search..."
              className="pl-9"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            {searchResults.length > 0 && (
              <div className="absolute mt-2 w-full rounded-md border border-border bg-card p-2 z-10 shadow-md max-h-64 overflow-auto">
                {searchResults.map((item, idx) => (
                  <button
                    key={`${item.doc_id}-${idx}`}
                    className="w-full text-left px-2 py-1 hover:bg-muted rounded"
                    onClick={() => navigate(`/document/${item.doc_id}`)}
                  >
                    <p className="text-xs font-medium">{item.filename}</p>
                    <p className="text-xs text-muted-foreground line-clamp-2">{item.snippet}</p>
                  </button>
                ))}
              </div>
            )}
          </div>
          <Button variant="ghost" size="icon" onClick={toggleTheme}>
            <Sun className="h-4 w-4 rotate-0 scale-100 transition-transform dark:-rotate-90 dark:scale-0" />
            <Moon className="absolute h-4 w-4 rotate-90 scale-0 transition-transform dark:rotate-0 dark:scale-100" />
          </Button>
        </header>

        <div className="flex-1 p-6 space-y-6 overflow-auto">
          {/* Upload zone */}
          <Card
            {...getRootProps()}
            className={`border-2 border-dashed cursor-pointer transition-all ${isDragActive ? "border-primary bg-primary/5" : "border-border hover:border-primary/40"}`}
          >
            <CardContent className="flex flex-col items-center justify-center py-16 gap-4">
              <input {...getInputProps()} />
              <div className="p-4 rounded-full bg-primary/10">
                {isDragActive ? <FileUp className="h-8 w-8 text-primary animate-pulse" /> : <Upload className="h-8 w-8 text-primary" />}
              </div>
              <div className="text-center">
                <p className="font-medium text-foreground">
                  {isDragActive ? "Drop files here" : "Drag & drop PDF, Excel, CSV, DOCX, or image files"}
                </p>
                <p className="text-sm text-muted-foreground mt-1">or click to browse</p>
                {uploading && <p className="text-xs text-primary mt-2">Uploading... {uploadProgress}%</p>}
              </div>
            </CardContent>
          </Card>

          <Card className="border border-border">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="flex-1">
                  <p className="text-sm font-medium text-foreground">Upload by link</p>
                  <p className="text-xs text-muted-foreground">Paste a Google Drive PDF share link or a public Google Form link.</p>
                </div>
              </div>
              <div className="mt-3 flex gap-2">
                <Input
                  placeholder="https://drive.google.com/file/d/... or https://docs.google.com/forms/..."
                  value={linkUrl}
                  onChange={(e) => setLinkUrl(e.target.value)}
                />
                <Button onClick={handleUploadLink} disabled={linkUploading || !linkUrl.trim()}>
                  {linkUploading ? "Adding..." : "Add link"}
                </Button>
              </div>
            </CardContent>
          </Card>

          <div className="flex gap-3">
            <Button onClick={handleBatchProcess} className="gap-2">
              <PlayCircle className="h-4 w-4" />
              Batch Process All
            </Button>
            <Button variant="outline" onClick={() => navigate("/batch")}>
              View Batch Status
            </Button>
          </div>

          {/* Quick list */}
          {filtered.length > 0 && (
            <div className="grid gap-2">
              {filtered.map((doc) => (
                <div
                  key={doc.id}
                  className="flex items-center gap-3 p-3 rounded-lg bg-card border border-border hover:border-primary/30 transition-colors cursor-pointer"
                  onClick={() => doc.status === "done" && navigate(`/document/${doc.id}`)}
                >
                  <p className="flex-1 text-sm font-medium text-foreground truncate">{doc.filename}</p>
                  <DocTypeBadge type={doc.file_type} />
                  <StatusChip status={doc.status} />
                  <span className="text-xs text-muted-foreground">{new Date(doc.created_at).toLocaleDateString()}</span>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteDocument(doc.id);
                    }}
                  >
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
