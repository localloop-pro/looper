/// <reference types="vite/client" />

export type LooperArtifact = {
  title: string;
  kind:
    | "text"
    | "markdown"
    | "code"
    | "table"
    | "notes"
    | "mermaid"
    | "image"
    | "imageLoading"
    | "thumbnailBoard"
    | "progress";
  content: string;
  language?: string;
  fullscreen?: boolean;
};

export type LooperToolSpec = {
  type: "function";
  name: string;
  description: string;
  parameters: Record<string, unknown>;
};

export type LooperToolCall = {
  name: string;
  arguments: Record<string, unknown>;
};

export type LooperToolResult = {
  ok: boolean;
  artifact?: LooperArtifact;
  mode?: "display" | "computer";
  message?: string;
  error?: string;
  [key: string]: unknown;
};

declare global {
  interface Window {
    looper: {
      createRealtimeToken: () => Promise<{ value: string; expiresAt: number | null }>;
      executeTool: (toolCall: LooperToolCall) => Promise<LooperToolResult>;
      getToolSpecs: () => Promise<LooperToolSpec[]>;
    };
  }
}
