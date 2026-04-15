import type { AppDocument, DocumentSummary, QuestionGroup, ChatMessage, DocumentMetadata } from "@/types";

const metadata: DocumentMetadata = {
  names: ["John Smith", "Sarah Johnson", "ACME Corp"],
  dates: ["2024-01-15", "2024-03-22", "2024-06-01"],
  emails: ["john@acme.com", "sarah.j@example.org"],
  pageCount: 12,
  author: "John Smith",
  language: "English",
};

const summary: DocumentSummary = {
  title: "Q4 2024 Financial Report - ACME Corp",
  key_points: [
    "Revenue increased 23% year-over-year to $4.2B",
    "Operating margins improved from 18% to 22%",
    "New product line contributed $800M in revenue",
    "International expansion into 3 new markets",
    "R&D spending increased by 15% to support innovation pipeline",
  ],
  important_entities: ["ACME Corp", "Board of Directors", "SEC", "NYSE", "Goldman Sachs"],
  conclusion: "ACME Corp demonstrated strong financial performance in Q4 2024, driven by robust revenue growth and improved operational efficiency. The company is well-positioned for continued growth in the coming fiscal year.",
};

const altSummary: DocumentSummary = {
  title: "Q4 2024 Financial Analysis - ACME Corporation",
  key_points: [
    "Total revenue reached $4.2 billion, up 23% YoY",
    "Profit margins expanded significantly to 22%",
    "Strategic market expansion into APAC region",
    "Technology investments driving future growth",
  ],
  important_entities: ["ACME Corporation", "Board Members", "Securities Commission", "Stock Exchange"],
  conclusion: "Strong quarterly results indicate sustainable growth trajectory with diversified revenue streams and operational improvements across all business units.",
};

const questions: QuestionGroup[] = [
  {
    category: "Financial Performance",
    questions: [
      "What was the total revenue for Q4 2024?",
      "How did operating margins change compared to last year?",
      "What is the projected revenue for Q1 2025?",
    ],
  },
  {
    category: "Strategy & Operations",
    questions: [
      "Which new markets were entered during this period?",
      "What percentage of revenue came from the new product line?",
      "How does the R&D spending compare to industry average?",
    ],
  },
  {
    category: "Compliance & Governance",
    questions: [
      "Are there any pending regulatory issues mentioned?",
      "What governance changes were implemented?",
    ],
  },
];

const chatMessages: ChatMessage[] = [
  { id: "m1", role: "user", content: "What was the total revenue mentioned in this document?", sources: [], timestamp: new Date().toISOString() },
  { id: "m2", role: "assistant", content: "According to the document, ACME Corp reported total revenue of $4.2 billion for Q4 2024, representing a 23% year-over-year increase.", sources: ["Page 3, Section 2.1", "Page 7, Table 4"], timestamp: new Date().toISOString() },
  { id: "m3", role: "user", content: "What about the new product line performance?", sources: [], timestamp: new Date().toISOString() },
  { id: "m4", role: "assistant", content: "The new product line contributed $800 million in revenue, accounting for approximately 19% of total revenue. This exceeded initial projections by 12%.", sources: ["Page 5, Section 3.2", "Page 8, Chart 6"], timestamp: new Date().toISOString() },
];

export const mockDocuments: AppDocument[] = [
  {
    id: "doc-1",
    fileName: "Q4_2024_Financial_Report.pdf",
    fileSize: 2_400_000,
    docType: "pdf",
    status: "done",
    uploadedAt: "2024-12-15T10:30:00Z",
    metadata,
    summary,
    localOutput: summary,
    apiOutput: altSummary,
    questions,
    chatMessages,
  },
  {
    id: "doc-2",
    fileName: "Employee_Data_2024.xlsx",
    fileSize: 1_100_000,
    docType: "excel",
    status: "done",
    uploadedAt: "2024-12-14T08:15:00Z",
    metadata: { ...metadata, names: ["HR Department", "Jane Doe"], emails: ["hr@acme.com"], pageCount: 5 },
    summary: { ...summary, title: "Employee Data Summary 2024" },
    questions: questions.slice(0, 2),
  },
  {
    id: "doc-3",
    fileName: "Contract_Draft_v3.pdf",
    fileSize: 890_000,
    docType: "pdf",
    status: "processing",
    uploadedAt: "2024-12-16T14:00:00Z",
  },
  {
    id: "doc-4",
    fileName: "Market_Analysis_APAC.pdf",
    fileSize: 3_200_000,
    docType: "pdf",
    status: "queued",
    uploadedAt: "2024-12-16T14:05:00Z",
  },
  {
    id: "doc-5",
    fileName: "Budget_Forecast_Error.xlsx",
    fileSize: 500_000,
    docType: "excel",
    status: "failed",
    uploadedAt: "2024-12-13T11:00:00Z",
  },
];

export function delay(ms?: number): Promise<void> {
  const time = ms ?? 500 + Math.random() * 1500;
  return new Promise((r) => setTimeout(r, time));
}
