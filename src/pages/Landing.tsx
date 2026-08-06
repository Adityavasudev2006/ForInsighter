import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useApp } from "@/context/AppContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { BrandMark } from "@/components/BrandMark";
import { Brain, Cloud, Server, ArrowRight, Moon, Sun, Loader2 } from "lucide-react";
import { toggleTheme } from "@/lib/theme";
import type { AIMode, APIProvider } from "@/types";
import { toast } from "sonner";
import { validateLLM } from "@/api/client";

export default function Landing() {
  const { setMode, setApiProvider, setApiKey, setOllamaBaseUrl, setOllamaModel, config } = useApp();
  const [selectedMode, setSelectedMode] = useState<AIMode>(config.mode);
  const [apiKeyInput, setApiKeyInput] = useState(config.apiKey ?? "");
  const [provider, setProvider] = useState<APIProvider>(config.apiProvider ?? "gemini");
  const [ollamaBaseUrl, setOllamaBaseUrlInput] = useState(config.ollamaBaseUrl ?? "http://localhost:11434");
  const [ollamaModel, setOllamaModelInput] = useState(config.ollamaModel ?? "llama3.2");
  const [isValidating, setIsValidating] = useState(false);
  const navigate = useNavigate();

  const canContinue =
    (selectedMode === "local" && ollamaBaseUrl.trim().length > 0) ||
    (selectedMode === "api" && apiKeyInput.trim().length > 0);

  const handleContinue = async () => {
    const candidateConfig =
      selectedMode === "api"
        ? { mode: "api", apiProvider: provider, apiKey: apiKeyInput, ollamaBaseUrl, ollamaModel }
        : { mode: "local", ollamaBaseUrl, ollamaModel, apiProvider: provider, apiKey: apiKeyInput };

    setIsValidating(true);
    try {
      const result = await validateLLM(candidateConfig);
      if (!result?.ok) {
        toast.error(result?.message || "LLM validation failed");
        return;
      }

      setMode(selectedMode);
      if (selectedMode === "api") {
        setApiProvider(provider);
        setApiKey(apiKeyInput);
      } else {
        setOllamaBaseUrl(ollamaBaseUrl);
        setOllamaModel(ollamaModel);
      }
      navigate("/dashboard");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Validation failed");
    } finally {
      setIsValidating(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <header className="flex justify-end p-4">
        <Button variant="ghost" size="icon" onClick={toggleTheme}>
          <Sun className="h-5 w-5 rotate-0 scale-100 transition-transform dark:-rotate-90 dark:scale-0" />
          <Moon className="absolute h-5 w-5 rotate-90 scale-0 transition-transform dark:rotate-0 dark:scale-100" />
        </Button>
      </header>

      <main className="flex-1 flex items-center justify-center px-4">
        <div className="max-w-2xl w-full space-y-10 animate-slide-up">
          <div className="text-center space-y-4">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-sm font-medium">
              <Brain className="h-4 w-4" />
              AI-Powered
            </div>
            <div className="flex items-center justify-center gap-2">
              <BrandMark className="h-8 w-8 text-foreground" />
              <span className="text-base font-semibold text-foreground">ForInsighter</span>
            </div>
            <h1 className="text-4xl sm:text-5xl font-bold tracking-tight text-foreground">
              Document Intelligence
            </h1>
            <p className="text-lg text-muted-foreground max-w-md mx-auto">
              Extract insights, generate summaries, and ask questions across your documents using AI.
            </p>
          </div>

          <div className="grid sm:grid-cols-2 gap-4">
            <Card
              className={`cursor-pointer transition-all hover:border-primary/50 ${selectedMode === "local" ? "border-primary glow-primary" : "border-border"}`}
              onClick={() => setSelectedMode("local")}
            >
              <CardContent className="p-6 space-y-3">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-primary/10">
                    <Server className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-foreground">Local (Ollama)</h3>
                    <Badge variant="secondary" className="text-xs mt-1">Private</Badge>
                  </div>
                </div>
                <p className="text-sm text-muted-foreground">
                  Run models locally via Ollama. Your data never leaves your machine.
                </p>
              </CardContent>
            </Card>

            <Card
              className={`cursor-pointer transition-all hover:border-accent/50 ${selectedMode === "api" ? "border-accent glow-accent" : "border-border"}`}
              onClick={() => setSelectedMode("api")}
            >
              <CardContent className="p-6 space-y-3">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-accent/10">
                    <Cloud className="h-5 w-5 text-accent" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-foreground">API Mode</h3>
                    <Badge variant="secondary" className="text-xs mt-1">Cloud</Badge>
                  </div>
                </div>
                <p className="text-sm text-muted-foreground">
                  Connect to Gemini or OpenAI for powerful cloud-based processing.
                </p>
              </CardContent>
            </Card>
          </div>

          {selectedMode === "api" && (
            <div className="space-y-4 animate-slide-up">
              <Select value={provider} onValueChange={(v) => setProvider(v as APIProvider)}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select provider" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="gemini">Google Gemini</SelectItem>
                  <SelectItem value="openai">OpenAI</SelectItem>
                </SelectContent>
              </Select>
              <Input
                type="password"
                placeholder="Enter your API key"
                value={apiKeyInput}
                onChange={(e) => setApiKeyInput(e.target.value)}
              />
            </div>
          )}
          {selectedMode === "local" && (
            <div className="space-y-4 animate-slide-up">
              <Input
                placeholder="Ollama base URL (e.g. http://localhost:11434)"
                value={ollamaBaseUrl}
                onChange={(e) => setOllamaBaseUrlInput(e.target.value)}
              />
              <Input
                placeholder="Ollama model (e.g. llama3.2)"
                value={ollamaModel}
                onChange={(e) => setOllamaModelInput(e.target.value)}
              />
            </div>
          )}

          <Button
            size="lg"
            className="w-full text-base gap-2"
            disabled={!canContinue || isValidating}
            onClick={handleContinue}
          >
            {isValidating ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Validating connection...
              </>
            ) : (
              <>
                Continue to Dashboard
                <ArrowRight className="h-4 w-4" />
              </>
            )}
          </Button>
        </div>
      </main>

      {isValidating && (
        <div className="fixed inset-0 bg-background/90 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="text-center space-y-3">
            <Loader2 className="h-8 w-8 animate-spin mx-auto text-primary" />
            <p className="text-sm text-muted-foreground">
              Checking your {selectedMode === "api" ? "API key" : "local Ollama server"}...
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
