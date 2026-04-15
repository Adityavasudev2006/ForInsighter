import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useApp } from "@/context/AppContext";
import { StatusChip } from "@/components/StatusChip";
import { DocTypeBadge } from "@/components/DocTypeBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ArrowLeft, Send, Moon, Sun, User, Bot, FileText, Calendar, Mail, Globe, BookOpen, Mic, MicOff } from "lucide-react";
import { toggleTheme } from "@/lib/theme";
import { chat, clearChat, compareModels, exportDoc, getChatHistory, getCharts, getDocument, getEntities, getQuestions } from "@/api/client";
import { toast } from "sonner";
import type { AppDocument, ChatMessage, ChartSpec, CompareResult, EntityData, ExtractedQuestion, SourceRef } from "@/types";
import { BrandMark } from "@/components/BrandMark";
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export default function DocumentViewer() {
  const { id } = useParams<{ id: string }>();
  const { config } = useApp();
  const navigate = useNavigate();
  const [chatInput, setChatInput] = useState("");
  const [doc, setDoc] = useState<AppDocument | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [questions, setQuestions] = useState<ExtractedQuestion[]>([]);
  const [entities, setEntities] = useState<EntityData | null>(null);
  const [comparison, setComparison] = useState<CompareResult | null>(null);
  const [charts, setCharts] = useState<ChartSpec[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [activeTab, setActiveTab] = useState("summary");
  const [viewSrc, setViewSrc] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    getDocument(id).then(setDoc).catch(() => toast.error("Failed to load document"));
    getQuestions(id).then(setQuestions).catch(() => null);
    getEntities(id).then(setEntities).catch(() => null);
    getCharts(id).then((data) => setCharts((data as { charts?: ChartSpec[] })?.charts || [])).catch(() => setCharts([]));
    getChatHistory(id)
      .then((rows) =>
        setMessages(
          (rows as Array<{ role: "user" | "assistant"; content: string; sources?: SourceRef[] | null }>).map((row) => ({
            role: row.role,
            content: row.content,
            sources: row.sources || [],
          })),
        ),
      )
      .catch(() => null);
  }, [id]);

  useEffect(() => {
    if (!doc?.id) return;
    if (!viewSrc) {
      const prefersNative = doc?.view_manifest?.source_mode === "native";
      const path = prefersNative ? "native-view" : "view";
      setViewSrc(`http://localhost:8000/api/documents/${doc.id}/${path}`);
    }
  }, [doc?.id, viewSrc]);

  useEffect(() => {
    if ((doc?.file_type === "excel" || doc?.file_type === "csv") && (activeTab === "questions" || activeTab === "view")) {
      setActiveTab("summary");
    }
  }, [doc?.file_type, activeTab]);

  const handleSend = async () => {
    if (!chatInput.trim() || !id) return;
    const userMsg: ChatMessage = { role: "user", content: chatInput };
    setMessages((m) => [...m, userMsg]);
    setChatInput("");
    setIsGenerating(true);
    try {
      const result = await chat(id, userMsg.content, messages, config.mode, config);
      const assistantMsg: ChatMessage = { role: "assistant", content: result.answer, sources: result.sources };
      setMessages((m) => [...m, assistantMsg]);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to generate response";
      toast.error(message);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleCompare = async () => {
    if (!id) return;
    const data = await compareModels(id, config);
    setComparison(data);
  };

  const openHighlightsForMessage = (sources: SourceRef[] | undefined) => {
    if (!doc?.id) return;
    const safeSources = Array.isArray(sources) ? sources : [];
    const json = JSON.stringify(safeSources);
    const b64 = btoa(unescape(encodeURIComponent(json)))
      .replaceAll("+", "-")
      .replaceAll("/", "_")
      .replaceAll("=", "");
    const useNative = doc?.view_manifest?.source_mode === "native";
    const highlightPath = useNative ? "native-highlight" : "highlight";
    setViewSrc(`http://localhost:8000/api/documents/${doc.id}/${highlightPath}?sources=${b64}`);
    setActiveTab("view");
  };

  const toggleListening = () => {
    const speechAny = window as Window & {
      SpeechRecognition?: new () => SpeechRecognition;
      webkitSpeechRecognition?: new () => SpeechRecognition;
    };
    const SpeechRecognition = speechAny.SpeechRecognition || speechAny.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      toast.error("Speech recognition is not supported in this browser.");
      return;
    }
    if (isListening) {
      setIsListening(false);
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    setIsListening(true);
    recognition.onresult = (event) => {
      const transcript = event.results?.[0]?.[0]?.transcript || "";
      if (transcript.trim()) setChatInput((prev) => `${prev}${prev ? " " : ""}${transcript.trim()}`);
    };
    recognition.onerror = () => {
      toast.error("Unable to capture voice input.");
      setIsListening(false);
    };
    recognition.onend = () => setIsListening(false);
    recognition.start();
  };

  if (!doc) return <div className="min-h-screen bg-background flex items-center justify-center text-foreground">Document not found</div>;

  const narrativeSummary =
    doc?.summary?.narrative_summary ||
    (doc?.summary as unknown as { narrativeSummary?: string | string[] | null })?.narrativeSummary ||
    null;
  const isTabularDoc = doc.file_type === "excel" || doc.file_type === "csv";
  const detailsSummary = (() => {
    if (!doc.summary) return null;
    const copy = { ...doc.summary } as Record<string, unknown>;
    delete copy.title;
    return copy;
  })();

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <header className="h-14 border-b border-border flex items-center px-4 gap-3 bg-card">
        <Button variant="ghost" size="icon" onClick={() => navigate("/dashboard")}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex items-center gap-2">
          <BrandMark className="h-5 w-5 text-foreground" />
          <span className="text-xs font-semibold text-muted-foreground">ForInsighter</span>
        </div>
        <h1 className="text-sm font-semibold text-foreground truncate">{doc.filename}</h1>
        <div className="flex items-center gap-2 ml-2">
          <DocTypeBadge type={doc.file_type} />
          <StatusChip status={doc.status} />
        </div>
        {doc.status === "failed" && doc.processing_error && (
          <Badge variant="destructive" className="ml-2 max-w-[500px] truncate">{doc.processing_error}</Badge>
        )}
        <div className="flex-1" />
        <Button variant="ghost" size="icon" onClick={toggleTheme}>
          <Sun className="h-4 w-4 rotate-0 scale-100 transition-transform dark:-rotate-90 dark:scale-0" />
          <Moon className="absolute h-4 w-4 rotate-90 scale-0 transition-transform dark:rotate-0 dark:scale-100" />
        </Button>
      </header>

      <div className="h-[calc(100vh-3.5rem)] flex overflow-hidden">
        {/* Left: Metadata */}
        <aside className="w-64 border-r border-border bg-card flex flex-col min-h-0">
          <div className="p-4 border-b border-border">
            <h3 className="text-xs font-semibold uppercase text-muted-foreground tracking-wider">File Info</h3>
          </div>
          <ScrollArea className="flex-1 min-h-0 p-4">
            <div className="space-y-5">
              <div>
                <div className="space-y-2 text-sm">
                  <p className="text-foreground">
                    <span className="text-muted-foreground">Uploaded:</span> {new Date(doc.created_at).toLocaleDateString()}
                  </p>
                </div>
              </div>

              {entities && (
                <>
                  <div>
                    <h3 className="text-xs font-semibold uppercase text-muted-foreground tracking-wider mb-2 flex items-center gap-1">
                      <User className="h-3 w-3" /> Names
                    </h3>
                    <div className="flex flex-wrap gap-1">
                      {entities.names.map((n) => (
                        <Badge key={n} variant="secondary" className="text-xs">
                          {n}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  <div>
                    <h3 className="text-xs font-semibold uppercase text-muted-foreground tracking-wider mb-2 flex items-center gap-1">
                      <Calendar className="h-3 w-3" /> Dates
                    </h3>
                    <div className="flex flex-wrap gap-1">
                      {entities.dates.map((d) => (
                        <Badge key={d} variant="secondary" className="text-xs">
                          {d}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  <div>
                    <h3 className="text-xs font-semibold uppercase text-muted-foreground tracking-wider mb-2 flex items-center gap-1">
                      <Mail className="h-3 w-3" /> Emails
                    </h3>
                    <div className="flex flex-wrap gap-1">
                      {entities.emails.map((e) => (
                        <Badge key={e} variant="secondary" className="text-xs font-mono">
                          {e}
                        </Badge>
                      ))}
                    </div>
                  </div>
                </>
              )}
            </div>
          </ScrollArea>
        </aside>

        {/* Center: Tabs */}
        <div className="flex-1 min-w-0 border-r border-border bg-background flex flex-col min-h-0">
          <div className="p-6 pb-0">
            <Tabs value={activeTab} onValueChange={setActiveTab}>
              <TabsList className="mb-4">
                <TabsTrigger value="summary">Summary</TabsTrigger>
                <TabsTrigger value="details">Details</TabsTrigger>
                {!isTabularDoc && <TabsTrigger value="questions">Extracted Questions</TabsTrigger>}
                {!isTabularDoc && <TabsTrigger value="view">View – Visualise</TabsTrigger>}
                <TabsTrigger value="charts">Charts</TabsTrigger>
                <TabsTrigger value="comparison">Mode Comparison</TabsTrigger>
              </TabsList>

              <TabsContent value="summary" className="animate-slide-up">
                <ScrollArea className="h-[calc(100vh-3.5rem-6.5rem)] pr-4">
                  {doc.summary ? (
                    <Card>
                      <CardContent className="p-6">
                        {narrativeSummary ? (
                          Array.isArray(narrativeSummary) ? (
                            <div className="space-y-4 text-sm leading-6 text-foreground">
                              {narrativeSummary.slice(0, 3).map((p: string, idx: number) => (
                                <p key={idx} className="whitespace-pre-wrap">{p}</p>
                              ))}
                            </div>
                          ) : (
                            <div className="space-y-4 text-sm leading-6 text-foreground">
                              {String(narrativeSummary)
                                .split(/\n\s*\n/g)
                                .filter(Boolean)
                                .slice(0, 3)
                                .map((p: string, idx: number) => (
                                  <p key={idx} className="whitespace-pre-wrap">{p}</p>
                                ))}
                            </div>
                          )
                        ) : (
                          <div className="space-y-4 text-sm leading-6 text-foreground">
                            <p className="whitespace-pre-wrap">
                              {doc.summary?.title ? `${doc.summary.title}\n` : ""}
                              {doc.summary?.conclusion || "Summary is not available yet."}
                            </p>
                            {Array.isArray(doc.summary?.key_points) && doc.summary.key_points.length > 0 && (
                              <div>
                                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                                  Key points
                                </p>
                                <ul className="list-disc pl-5 space-y-1">
                                  {doc.summary.key_points.slice(0, 8).map((kp: string, idx: number) => (
                                    <li key={idx}>{kp}</li>
                                  ))}
                                </ul>
                              </div>
                            )}
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  ) : (
                    <p className="text-muted-foreground">No summary available yet.</p>
                  )}
                </ScrollArea>
              </TabsContent>

              <TabsContent value="details" className="animate-slide-up">
                <ScrollArea className="h-[calc(100vh-3.5rem-6.5rem)] pr-4">
                  {doc.summary ? (
                    <Card>
                      <CardContent className="p-6">
                        <pre className="text-sm font-mono text-foreground whitespace-pre-wrap bg-muted p-4 rounded-lg overflow-auto">
{JSON.stringify(detailsSummary, null, 2)}
                        </pre>
                        <div className="mt-3 flex gap-2">
                          <Button size="sm" onClick={() => exportDoc(doc.id, "json")}>Export JSON</Button>
                          <Button size="sm" variant="outline" onClick={() => exportDoc(doc.id, "csv")}>Export CSV</Button>
                          <Button size="sm" variant="outline" onClick={() => exportDoc(doc.id, "pdf")}>Export PDF</Button>
                        </div>
                      </CardContent>
                    </Card>
                  ) : (
                    <p className="text-muted-foreground">No details available yet.</p>
                  )}
                </ScrollArea>
              </TabsContent>

              {!isTabularDoc && <TabsContent value="questions" className="animate-slide-up">
                <ScrollArea className="h-[calc(100vh-3.5rem-6.5rem)] pr-4">
                  <div className="space-y-4">
                    {questions?.length ? (
                      questions.map((q, idx) => (
                        <Card key={`${q.category}-${idx}`}>
                          <CardHeader className="pb-2">
                            <CardTitle className="text-sm flex items-center gap-2">
                              <BookOpen className="h-4 w-4 text-primary" />
                              {q.category}
                            </CardTitle>
                          </CardHeader>
                          <CardContent>
                            <p className="text-sm text-foreground pl-4 border-l-2 border-primary/30 py-1">{q.text}</p>
                          </CardContent>
                        </Card>
                      ))
                    ) : (
                      <p className="text-muted-foreground">No questions extracted.</p>
                    )}
                  </div>
                </ScrollArea>
              </TabsContent>}

              {!isTabularDoc && <TabsContent value="view" className="animate-slide-up">
                <ScrollArea className="h-[calc(100vh-3.5rem-6.5rem)] pr-4">
                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm">View – Visualise</CardTitle>
                    </CardHeader>
                    <CardContent>
                      {viewSrc ? (
                        <div className="h-[calc(100vh-3.5rem-9.5rem)] w-full rounded-md overflow-hidden border border-border bg-background">
                          <iframe
                            title="Document viewer"
                            src={viewSrc}
                            className="w-full h-full"
                          />
                        </div>
                      ) : (
                        <p className="text-sm text-muted-foreground">Preparing viewer…</p>
                      )}
                    </CardContent>
                  </Card>
                </ScrollArea>
              </TabsContent>}

              <TabsContent value="charts" className="animate-slide-up">
                <ScrollArea className="h-[calc(100vh-3.5rem-6.5rem)] pr-4">
                  {charts.length === 0 ? (
                    <p className="text-muted-foreground">No charts available for this document.</p>
                  ) : (
                    <div className="grid gap-4">
                      {charts.map((chart) => (
                        <Card key={chart.id}>
                          <CardHeader className="pb-2">
                            <CardTitle className="text-sm">{chart.title}</CardTitle>
                          </CardHeader>
                          <CardContent>
                            <div className="h-64 w-full">
                              <ResponsiveContainer width="100%" height="100%">
                                {chart.type === "line" ? (
                                  <LineChart data={chart.data}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis dataKey={chart.xKey} />
                                    <YAxis />
                                    <Tooltip />
                                    <Legend />
                                    {(chart.series || []).map((s) => (
                                      <Line key={s} type="monotone" dataKey={s} stroke="#4f46e5" />
                                    ))}
                                  </LineChart>
                                ) : (
                                  <BarChart data={chart.data}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis dataKey={chart.xKey} />
                                    <YAxis />
                                    <Tooltip />
                                    <Legend />
                                    <Bar dataKey={chart.yKey || "value"} fill="#6366f1" />
                                  </BarChart>
                                )}
                              </ResponsiveContainer>
                            </div>
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  )}
                </ScrollArea>
              </TabsContent>

              <TabsContent value="comparison" className="animate-slide-up">
                <ScrollArea className="h-[calc(100vh-3.5rem-6.5rem)] pr-4">
                  <div className="grid md:grid-cols-2 gap-4">
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm flex items-center gap-2"><Globe className="h-4 w-4" />Local Output</CardTitle>
                      </CardHeader>
                      <CardContent>
                        {comparison?.local_output ? (
                          <pre className="text-xs font-mono text-foreground whitespace-pre-wrap bg-muted p-3 rounded-lg">{JSON.stringify(comparison.local_output, null, 2)}</pre>
                        ) : <p className="text-sm text-muted-foreground">Not available</p>}
                        {comparison && <Badge variant="secondary" className="mt-2">{comparison.local_latency_ms.toFixed(0)} ms</Badge>}
                      </CardContent>
                    </Card>
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm flex items-center gap-2"><FileText className="h-4 w-4" />API Output</CardTitle>
                      </CardHeader>
                      <CardContent>
                        {comparison?.api_output ? (
                          <pre className="text-xs font-mono text-foreground whitespace-pre-wrap bg-muted p-3 rounded-lg">{JSON.stringify(comparison.api_output, null, 2)}</pre>
                        ) : <p className="text-sm text-muted-foreground">Not available</p>}
                        {comparison && <Badge variant="secondary" className="mt-2">{comparison.api_latency_ms.toFixed(0)} ms</Badge>}
                      </CardContent>
                    </Card>
                  </div>
                  <Button className="mt-4" onClick={handleCompare}>Run Comparison</Button>
                </ScrollArea>
              </TabsContent>
            </Tabs>
          </div>
        </div>

        {/* Right: Chat */}
        <aside className="w-80 bg-card flex flex-col min-h-0">
          <div className="p-4 border-b border-border">
            <h3 className="text-sm font-semibold text-foreground">Document Chat</h3>
          </div>
          <ScrollArea className="flex-1 p-4">
            <div className="space-y-4">
              {messages.map((msg, idx) => (
                <div key={`${msg.role}-${idx}`} className={`flex gap-2 ${msg.role === "user" ? "justify-end" : ""}`}>
                  {msg.role === "assistant" && (
                    <div className="w-7 h-7 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <Bot className="h-3.5 w-3.5 text-primary" />
                    </div>
                  )}
                  <div className={`max-w-[85%] space-y-1.5 ${msg.role === "user" ? "text-right" : ""}`}>
                    <div className={`inline-block px-3 py-2 rounded-lg text-sm ${msg.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted text-foreground"}`}>
                      {msg.content}
                    </div>
                    {msg.role === "assistant" && !isTabularDoc && (
                      <div className="flex justify-end">
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground"
                          onClick={() => openHighlightsForMessage(msg.sources)}
                        >
                          Show &gt;&gt;
                        </Button>
                      </div>
                    )}
                    {msg.sources && msg.sources.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {msg.sources.map((s, sourceIdx) => (
                          <Badge key={sourceIdx} variant="outline" className="text-[10px] font-mono">
                            c{s.chunk_index} p{s.page_num}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                  {msg.role === "user" && (
                    <div className="w-7 h-7 rounded-full bg-secondary flex items-center justify-center flex-shrink-0 mt-0.5">
                      <User className="h-3.5 w-3.5 text-secondary-foreground" />
                    </div>
                  )}
                </div>
              ))}
              {isGenerating && (
                <div className="flex gap-2">
                  <div className="w-7 h-7 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <Bot className="h-3.5 w-3.5 text-primary" />
                  </div>
                  <div className="max-w-[85%]">
                    <div className="inline-flex items-center gap-1 px-3 py-2 rounded-lg text-sm bg-muted text-foreground">
                      <span className="h-1.5 w-1.5 rounded-full bg-foreground/60 animate-bounce [animation-delay:-0.2s]" />
                      <span className="h-1.5 w-1.5 rounded-full bg-foreground/60 animate-bounce [animation-delay:-0.1s]" />
                      <span className="h-1.5 w-1.5 rounded-full bg-foreground/60 animate-bounce" />
                    </div>
                  </div>
                </div>
              )}
            </div>
          </ScrollArea>
          <div className="p-4 border-t border-border">
            <form onSubmit={(e) => { e.preventDefault(); handleSend(); }} className="flex gap-2">
              <Input
                placeholder="Ask about this document..."
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                className="flex-1"
              />
              <Button size="icon" type="submit">
                <Send className="h-4 w-4" />
              </Button>
              <Button
                size="icon"
                variant={isListening ? "secondary" : "outline"}
                type="button"
                onClick={toggleListening}
                title={isListening ? "Stop voice input" : "Start voice input"}
              >
                {isListening ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
              </Button>
              <Button size="icon" variant="outline" type="button" onClick={() => id && clearChat(id).then(() => setMessages([]))}>
                <FileText className="h-4 w-4" />
              </Button>
            </form>
          </div>
        </aside>
      </div>
    </div>
  );
}
