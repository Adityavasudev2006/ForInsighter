export type AIMode = "local" | "api";
export type APIProvider = "gemini" | "openai";
export type ProcessingStatus = "queued" | "processing" | "done" | "failed";
export type DocumentType = "pdf" | "excel" | "csv" | "docx" | "image" | "text" | "unknown";

export interface DocumentSummary {
  title: string;
  key_points: string[];
  important_entities: string[];
  conclusion: string;
  document_type?: string;
  narrative_summary?: string | string[] | null;
  columns?: string[] | null;
  column_types?: Record<string, string> | null;
  column_descriptions?: Record<string, string> | null;
  row_count?: number | null;
  column_count?: number | null;
  file_size_bytes?: number | null;
  sheet_count?: number | null;
  missing_values_per_column?: Record<string, number> | null;
  missing_values_total?: number | null;
  unique_values_per_column?: Record<string, number> | null;
  numerical_stats?: Record<string, Record<string, number | null>> | null;
  categorical_stats?: Record<string, Record<string, string | number | null>> | null;
  duplicate_rows?: number | null;
  inconsistent_formats?: string[] | null;
  invalid_values?: string[] | null;
}

export interface ViewManifest {
  mode: "pdf" | "html" | "text" | "table" | "image";
  view_url?: string | null;
  highlight_url?: string | null;
  source_mode?: "pdf" | "native";
}

export interface ExtractedQuestion {
  text: string;
  category: string;
  source_page?: number | null;
}

export interface EntityData {
  names: string[];
  dates: string[];
  numbers: string[];
  emails: string[];
}

export interface SourceRef {
  chunk_index: number;
  page_num: number;
  snippet: string;
  line_ref?: string;
  cell_ref?: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sources?: SourceRef[];
}

export interface AppDocument {
  id: string;
  filename: string;
  file_type: DocumentType;
  doc_type?: string | null;
  status: ProcessingStatus;
  created_at: string;
  summary?: DocumentSummary | null;
  questions?: ExtractedQuestion[] | null;
  entities?: EntityData | null;
  processing_error?: string | null;
  view_manifest?: ViewManifest | null;
}

export interface CompareResult {
  local_output: DocumentSummary;
  api_output: DocumentSummary;
  local_latency_ms: number;
  api_latency_ms: number;
}

export interface SearchResult {
  doc_id: string;
  filename: string;
  snippet: string;
  score: number;
  page: number;
}

export interface AppConfig {
  mode: AIMode;
  apiProvider?: APIProvider;
  apiKey?: string;
  ollamaBaseUrl?: string;
  ollamaModel?: string;
}

export interface ChartSpec {
  id: string;
  title: string;
  type: "bar" | "line";
  data: Array<Record<string, string | number | null>>;
  xKey: string;
  yKey?: string;
  series?: string[];
}
