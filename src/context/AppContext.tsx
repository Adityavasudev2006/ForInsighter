import React, { createContext, useContext, useState, useCallback, useEffect } from "react";
import type { AppConfig, AppDocument, AIMode, APIProvider } from "@/types";

interface AppContextType {
  config: AppConfig;
  setMode: (mode: AIMode) => void;
  setApiProvider: (provider: APIProvider) => void;
  setApiKey: (key: string) => void;
  setOllamaBaseUrl: (url: string) => void;
  setOllamaModel: (model: string) => void;
  documents: AppDocument[];
  setDocuments: React.Dispatch<React.SetStateAction<AppDocument[]>>;
  addDocuments: (docs: AppDocument[]) => void;
  updateDocument: (id: string, updates: Partial<AppDocument>) => void;
  isConfigured: boolean;
}

const AppContext = createContext<AppContextType | null>(null);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [config, setConfig] = useState<AppConfig>({
    mode: (localStorage.getItem("ai_mode") as AIMode) || "local",
    apiProvider: (localStorage.getItem("api_provider") as APIProvider) || undefined,
    apiKey: localStorage.getItem("api_key") || undefined,
    ollamaBaseUrl: localStorage.getItem("ollama_base_url") || "http://localhost:11434",
    ollamaModel: localStorage.getItem("ollama_model") || "llama3.2",
  });
  const [documents, setDocuments] = useState<AppDocument[]>([]);

  const setMode = (mode: AIMode) => setConfig((c) => ({ ...c, mode }));
  const setApiProvider = (provider: APIProvider) => setConfig((c) => ({ ...c, apiProvider: provider }));
  const setApiKey = (key: string) => setConfig((c) => ({ ...c, apiKey: key }));
  const setOllamaBaseUrl = (url: string) => setConfig((c) => ({ ...c, ollamaBaseUrl: url }));
  const setOllamaModel = (model: string) => setConfig((c) => ({ ...c, ollamaModel: model }));

  const addDocuments = useCallback((docs: AppDocument[]) => {
    setDocuments((prev) => [...prev, ...docs]);
  }, []);

  const updateDocument = useCallback((id: string, updates: Partial<AppDocument>) => {
    setDocuments((prev) => prev.map((d) => (d.id === id ? { ...d, ...updates } : d)));
  }, []);

  const isConfigured = config.mode === "local" || (config.mode === "api" && !!config.apiKey && !!config.apiProvider);

  useEffect(() => {
    localStorage.setItem("ai_mode", config.mode);
    if (config.apiProvider) localStorage.setItem("api_provider", config.apiProvider);
    if (config.apiKey) localStorage.setItem("api_key", config.apiKey);
    if (config.ollamaBaseUrl) localStorage.setItem("ollama_base_url", config.ollamaBaseUrl);
    if (config.ollamaModel) localStorage.setItem("ollama_model", config.ollamaModel);
  }, [config.mode, config.apiProvider, config.apiKey, config.ollamaBaseUrl, config.ollamaModel]);

  return (
    <AppContext.Provider value={{ config, setMode, setApiProvider, setApiKey, setOllamaBaseUrl, setOllamaModel, documents, setDocuments, addDocuments, updateDocument, isConfigured }}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}
