import type { LooperArtifact, LooperToolCall, LooperToolResult, LooperToolSpec } from "../vite-env";

export type LooperConnectionState = "idle" | "connecting" | "connected" | "error";
export type LooperMood = "idle" | "listening" | "thinking" | "speaking" | "working" | "error";

export type MouthShape = {
  open: number;
  width: number;
  round: number;
  teeth: number;
};

export type TranscriptEntry = {
  id: string;
  role: "user" | "looper" | "system" | "tool";
  text: string;
  at: string;
};

export type RealtimeCallbacks = {
  onConnectionState: (state: LooperConnectionState) => void;
  onMood: (mood: LooperMood) => void;
  onMouthShape: (shape: MouthShape) => void;
  onTranscript: (entry: TranscriptEntry) => void;
  onArtifact: (artifact: LooperArtifact) => void;
  onMode: (mode: "display" | "computer") => void;
  onStatus: (message: string) => void;
  onThumbnailReady: () => void;
};

type ServerEvent = {
  type?: string;
  delta?: string;
  transcript?: string;
  response?: {
    status?: string;
    output?: ResponseOutputItem[];
  };
  item?: {
    type?: string;
    role?: string;
    status?: string;
    call_id?: string;
    name?: string;
    arguments?: string;
    content?: Array<{ transcript?: string; text?: string }>;
  };
  error?: {
    code?: string;
    message?: string;
  };
};

type ResponseOutputItem = {
  type?: string;
  status?: string;
  name?: string;
  call_id?: string;
  arguments?: string;
  content?: Array<{ transcript?: string; text?: string }>;
};

const realtimeUrl = "https://api.openai.com/v1/realtime/calls";
const maxReconnectAttempts = 4;

export class LooperRealtimeClient {
  private pc: RTCPeerConnection | null = null;
  private dc: RTCDataChannel | null = null;
  private micStream: MediaStream | null = null;
  private audioEl: HTMLAudioElement | null = null;
  private callbacks: RealtimeCallbacks;
  private currentAssistantText = "";
  private toolSpecs: LooperToolSpec[] = [];
  private toolRunning = false;
  private audioContext: AudioContext | null = null;
  private outputAnalyser: AnalyserNode | null = null;
  private outputMeterFrame = 0;
  private smoothedMouthShape: MouthShape = silentMouthShape();
  // Lifecycle: the user closing voice is the only "final" disconnect — every
  // other death (Wi-Fi drop, ICE failure, OpenAI's 60-minute session cap,
  // data-channel close) reconnects automatically with a fresh client secret.
  private closedByUser = false;
  private reconnectAttempts = 0;
  private reconnectTimer = 0;
  private disconnectGraceTimer = 0;
  private responseActive = false;
  private pendingResponseCreate = false;
  private activeToolCalls = 0;
  // Bumped on every teardown: a tool still awaiting IPC when the session
  // died must not send its stale call_id into the NEXT session or decrement
  // that session's counters underneath it.
  private sessionGen = 0;
  // Bumped when the user starts a NEW turn (typed prompt or speech) — a tool
  // launched for a superseded turn still posts its output for context, but
  // must not queue a spoken follow-up after the new turn's answer.
  private turnGen = 0;
  private handledCallIds = new Set<string>();
  private mood: LooperMood = "idle";
  private lastAudibleAt = 0;

  constructor(callbacks: RealtimeCallbacks) {
    this.callbacks = callbacks;
  }

  async connect(): Promise<void> {
    if (this.pc) return;
    this.closedByUser = false;
    this.callbacks.onConnectionState("connecting");
    this.setMood("thinking");
    this.callbacks.onStatus("Minting a Realtime client secret.");

    // Attempt-local peer lives outside the try so a failed dial can close it
    // — teardown() only knows about this.pc, which isn't assigned yet.
    let pc: RTCPeerConnection | null = null;
    try {
      this.toolSpecs = await window.looper.getToolSpecs();
      const token = await window.looper.createRealtimeToken();
      if (this.closedByUser) return; // cancelled while the token minted
      pc = new RTCPeerConnection();
      const peer = pc; // non-null alias for the closures below
      const audio = document.createElement("audio");
      audio.autoplay = true;
      this.audioEl = audio;

      peer.ontrack = (event) => {
        audio.srcObject = event.streams[0];
        this.startOutputMeter(event.streams[0]);
      };

      try {
        this.micStream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        });
      } catch (error) {
        const name = error instanceof DOMException ? error.name : "";
        if (name === "NotAllowedError" || name === "SecurityError") {
          throw new Error("Microphone permission denied — allow it in System Settings > Privacy & Security > Microphone, then reconnect.");
        }
        if (name === "NotFoundError" || name === "OverconstrainedError") {
          throw new Error("No microphone found — plug one in and reconnect.");
        }
        throw error;
      }
      if (this.closedByUser) {
        // cancelled while the mic opened — release it and abandon the dial
        this.micStream.getTracks().forEach((track) => track.stop());
        this.micStream = null;
        peer.close();
        return;
      }
      const micTrack = this.micStream.getAudioTracks()[0];
      peer.addTrack(micTrack, this.micStream);
      // Hot-unplugged headset: the track just ends. Reconnect picks up the
      // new default input device instead of leaving Looper silently deaf.
      micTrack.addEventListener("ended", () => {
        this.callbacks.onStatus("Microphone disconnected.");
        void this.handleDrop("Microphone lost");
      });

      peer.addEventListener("connectionstatechange", () => {
        if (peer !== this.pc) return; // stale connection from before a reconnect
        if (peer.connectionState === "failed") {
          void this.handleDrop("Connection lost");
        } else if (peer.connectionState === "disconnected") {
          // "disconnected" can self-heal on brief network blips — give it a
          // grace period before tearing down and reconnecting.
          this.clearGraceTimer();
          this.disconnectGraceTimer = window.setTimeout(() => {
            if (peer === this.pc && (peer.connectionState === "disconnected" || peer.connectionState === "failed")) {
              void this.handleDrop("Connection lost");
            }
          }, 3000);
        } else if (peer.connectionState === "connected") {
          this.clearGraceTimer();
        }
      });

      const dc = peer.createDataChannel("oai-events");
      dc.addEventListener("open", () => {
        this.reconnectAttempts = 0;
        this.callbacks.onConnectionState("connected");
        this.setMood("idle");
        this.callbacks.onStatus("Looper is live. Start talking naturally.");
      });
      dc.addEventListener("message", (event) => {
        this.handleServerEvent(event.data).catch((error) => {
          this.callbacks.onStatus(error instanceof Error ? error.message : String(error));
        });
      });
      dc.addEventListener("close", () => {
        if (dc !== this.dc) return; // closed by our own teardown
        void this.handleDrop("Voice link closed");
      });

      const offer = await peer.createOffer();
      await peer.setLocalDescription(offer);

      const sdpResponse = await fetch(realtimeUrl, {
        method: "POST",
        body: offer.sdp,
        headers: {
          Authorization: `Bearer ${token.value}`,
          "Content-Type": "application/sdp",
        },
      });

      if (!sdpResponse.ok) {
        throw new Error(`Realtime WebRTC call failed: ${sdpResponse.status} ${await sdpResponse.text()}`);
      }

      await peer.setRemoteDescription({
        type: "answer",
        sdp: await sdpResponse.text(),
      });

      // The user can cancel while we were dialing (the mic button stays
      // clickable during "connecting") — abandon the finished dial quietly.
      if (this.closedByUser) {
        dc.close();
        peer.close();
        this.micStream?.getTracks().forEach((track) => track.stop());
        this.micStream = null;
        return;
      }

      this.pc = peer;
      this.dc = dc;
    } catch (error) {
      // teardown() only closes this.pc — the attempt-local peer from a
      // failed dial must be closed here or each retry leaks a connection.
      pc?.close();
      this.teardown();
      if (this.closedByUser) return; // cancelled mid-dial — stay quietly idle
      // A failed REDIAL (Wi-Fi still down during the immediate retry) must
      // keep walking the backoff schedule, not stop at attempt one.
      if (!this.closedByUser && this.reconnectAttempts > 0) {
        this.scheduleReconnect(friendlyErrorMessage(error));
        return;
      }
      this.callbacks.onConnectionState("error");
      this.setMood("error");
      this.callbacks.onStatus(friendlyErrorMessage(error));
    }
  }

  disconnect(): void {
    this.closedByUser = true;
    this.clearReconnectTimer();
    this.clearGraceTimer();
    this.teardown();
    this.callbacks.onConnectionState("idle");
    this.setMood("idle");
    this.callbacks.onMouthShape(silentMouthShape());
  }

  sendText(text: string): void {
    if (!this.dc || this.dc.readyState !== "open") {
      this.callbacks.onStatus("Connect Looper before sending a text prompt.");
      return;
    }
    this.callbacks.onTranscript(newEntry("user", text));
    this.turnGen += 1;
    // A follow-up deferred by the superseded turn's tool must not fire from
    // the cancelled response's response.done on top of this turn's answer.
    this.pendingResponseCreate = false;
    // Typing while Looper is mid-reply is a barge-in: cancel first, or the
    // server rejects response.create with conversation_already_has_active_response.
    if (this.responseActive) {
      this.sendEvent({ type: "response.cancel" });
    }
    // Generation can finish while the WebRTC audio is still buffered and
    // audibly playing (the "speaking" mood tracks actual playback) — flush
    // the server-side buffer so the old answer stops talking over this turn.
    if (this.mood === "speaking" || this.responseActive) {
      this.sendEvent({ type: "output_audio_buffer.clear" });
    }
    this.sendEvent({
      type: "conversation.item.create",
      item: {
        type: "message",
        role: "user",
        content: [{ type: "input_text", text }],
      },
    });
    this.sendEvent({ type: "response.create" });
  }

  // Non-user connection death: tear down and dial back in with a fresh
  // client secret (main.cjs re-sends full instructions + tools on every mint).
  private async handleDrop(reason: string): Promise<void> {
    if (this.closedByUser || !this.pc) return;
    this.clearGraceTimer();
    this.teardown();
    this.scheduleReconnect(reason);
  }

  private scheduleReconnect(reason: string): void {
    if (this.closedByUser) return;
    if (this.reconnectAttempts >= maxReconnectAttempts) {
      this.callbacks.onConnectionState("error");
      this.setMood("error");
      this.callbacks.onStatus(`${reason} — couldn't reconnect. Click the mic to try again.`);
      return;
    }
    const delay = this.reconnectAttempts === 0 ? 0 : Math.min(2000 * 2 ** (this.reconnectAttempts - 1), 15000);
    this.reconnectAttempts += 1;
    this.callbacks.onConnectionState("connecting");
    this.callbacks.onStatus(`${reason} — reconnecting… (Looper starts a fresh session; earlier chat context resets.)`);
    this.clearReconnectTimer();
    this.reconnectTimer = window.setTimeout(() => {
      if (!this.closedByUser) void this.connect();
    }, delay);
  }

  private teardown(): void {
    this.sessionGen += 1;
    const dc = this.dc;
    const pc = this.pc;
    this.dc = null;
    this.pc = null;
    dc?.close();
    pc?.close();
    this.micStream?.getTracks().forEach((track) => track.stop());
    this.micStream = null;
    if (this.audioEl) {
      this.audioEl.srcObject = null;
      this.audioEl = null;
    }
    this.stopOutputMeter();
    this.currentAssistantText = "";
    this.responseActive = false;
    this.pendingResponseCreate = false;
    this.activeToolCalls = 0;
    this.toolRunning = false;
    this.handledCallIds.clear();
  }

  private async handleServerEvent(raw: string): Promise<void> {
    const event = safeParseEvent(raw);
    if (!event.type) return;

    if (event.type === "error") {
      // OpenAI hard-stops Realtime sessions at 60 minutes — that's routine,
      // not an error face: reconnect into a fresh session automatically.
      if (event.error?.code === "session_expired") {
        void this.handleDrop("Voice session hit OpenAI's 60-minute limit");
        return;
      }
      // A response.create that raced a still-active response (typed barge-in
      // right behind response.cancel) is not lost: retry it once the active
      // response reaches response.done.
      if (event.error?.code === "conversation_already_has_active_response") {
        this.pendingResponseCreate = true;
        return;
      }
      // Benign races stay status-only; real server errors show the error
      // face so the mood can't sit on "thinking"/"working" forever.
      const benign = event.error?.code === "response_cancel_not_active";
      if (!benign) this.setMood("error");
      this.callbacks.onStatus(event.error?.message || "Realtime API returned an error.");
      return;
    }

    if (event.type === "response.created") {
      this.responseActive = true;
      this.currentAssistantText = "";
      return;
    }

    if (event.type === "input_audio_buffer.speech_started") {
      this.turnGen += 1; // speaking over a running tool supersedes its turn
      this.pendingResponseCreate = false; // the new speech creates its own response
      this.setMood("listening");
      return;
    }

    if (event.type === "input_audio_buffer.speech_stopped") {
      this.setMood("thinking");
      return;
    }

    // Note: over WebRTC the reply audio arrives on the media track, not as
    // response.output_audio.delta data-channel events — the "speaking" mood
    // is driven by the output meter in startOutputMeter() instead.

    if (
      event.type === "response.audio_transcript.delta" ||
      event.type === "response.output_audio_transcript.delta" ||
      event.type === "response.output_text.delta"
    ) {
      this.currentAssistantText += event.delta || "";
      return;
    }

    if (event.type === "conversation.item.input_audio_transcription.completed") {
      const transcript = event.transcript || collectItemText(event.item);
      if (transcript) this.callbacks.onTranscript(newEntry("user", transcript));
      return;
    }

    if (event.type === "conversation.item.input_audio_transcription.failed") {
      this.callbacks.onTranscript(newEntry("system", "(couldn't transcribe that — Looper still heard you)"));
      return;
    }

    // Low-latency tool dispatch: a completed function_call item arrives here
    // before response.done — start the tool immediately instead of waiting
    // out the rest of the model's turn.
    if (event.type === "response.output_item.done" && event.item?.type === "function_call") {
      const item = event.item;
      if (item.call_id && item.name && item.status === "completed" && !this.handledCallIds.has(item.call_id)) {
        this.handledCallIds.add(item.call_id);
        await this.executeFunctionCalls([
          { type: "function_call", call_id: item.call_id, name: item.name, arguments: item.arguments },
        ]);
      }
      return;
    }

    if (event.type === "response.done") {
      this.responseActive = false;
      const cancelled = event.response?.status === "cancelled";
      const output = event.response?.output || [];
      const spoken = this.currentAssistantText || output.map(collectOutputText).filter(Boolean).join("\n");
      // Transcript deltas stream ahead of audio — an interrupted reply's tail
      // was never heard, so label it instead of logging it as said.
      if (spoken) this.callbacks.onTranscript(newEntry("looper", cancelled ? `${spoken} … (interrupted)` : spoken));
      this.currentAssistantText = "";

      // Safety net for function calls the output_item.done path didn't see.
      // Half-emitted calls from a cancelled response are skipped. This must
      // run BEFORE any deferred response.create fires, or the model answers
      // without the missed call's output — executeFunctionCalls flushes the
      // pending create itself once every call has returned.
      const functionCalls = output.filter(
        (item) =>
          item.type === "function_call" &&
          item.name &&
          item.call_id &&
          item.status !== "incomplete" &&
          !this.handledCallIds.has(item.call_id),
      );
      if (functionCalls.length > 0) {
        for (const item of functionCalls) {
          if (item.call_id) this.handledCallIds.add(item.call_id);
        }
        await this.executeFunctionCalls(functionCalls);
      } else {
        this.maybeCreateResponse();
        if (!this.toolRunning && this.mood !== "speaking" && this.mood !== "listening") {
          this.setMood("idle");
        }
      }
    }
  }

  // The model may emit several function calls in one response, and each
  // response.output_item.done handler runs concurrently — the follow-up
  // response.create may only fire once EVERY in-flight call has returned its
  // function_call_output, or a slow tool's result misses the model's answer.
  private maybeCreateResponse(): void {
    if (this.pendingResponseCreate && !this.responseActive && this.activeToolCalls === 0) {
      this.pendingResponseCreate = false;
      this.sendEvent({ type: "response.create" });
    }
  }

  private async executeFunctionCalls(items: ResponseOutputItem[]): Promise<void> {
    const gen = this.sessionGen;
    const turn = this.turnGen;
    this.activeToolCalls += 1;
    this.toolRunning = true;
    this.setMood("working");
    let shouldCreateResponse = false;

    try {
      for (const item of items) {
        if (gen !== this.sessionGen) return; // session died mid-run — results belong to nobody
        const callId = item.call_id;
        const name = item.name;
        if (!callId || !name) continue;

        try {
          const parsedArgs = parseToolArguments(item.arguments || "{}");
          const knownTool = this.toolSpecs.some((tool) => tool.name === name);
          if (!knownTool) {
            await this.returnToolOutput(callId, {
              ok: false,
              error: `Tool is not available: ${name}`,
            });
            shouldCreateResponse = true;
            continue;
          }

          this.callbacks.onTranscript(newEntry("tool", `Running ${name}`));
          if (name === "image_generate") {
            this.callbacks.onArtifact({
              title: "Generating Image",
              kind: "imageLoading",
              content: typeof parsedArgs.prompt === "string" ? parsedArgs.prompt : "Looper is generating an image.",
            });
          }
          if (name === "thumbnail_generate" || name === "thumbnail_edit") {
            const loadingResult = await window.looper.executeTool({
              name: "thumbnail_loading_prepare",
              arguments: {
                ...parsedArgs,
                mode: name === "thumbnail_edit" ? "edit" : "generate",
              },
            } satisfies LooperToolCall);
            if (typeof loadingResult.runId === "string") parsedArgs.runId = loadingResult.runId;
            if (typeof loadingResult.targetId === "string") parsedArgs.targetId = loadingResult.targetId;
            if (loadingResult.artifact) this.callbacks.onArtifact(loadingResult.artifact);
          }
          const result = await window.looper.executeTool({ name, arguments: parsedArgs } satisfies LooperToolCall);
          if (gen !== this.sessionGen) return; // stale call_id must not enter the new session
          if (result.mode === "display" || result.mode === "computer") {
            this.callbacks.onMode(result.mode);
          }
          if (result.artifact) this.callbacks.onArtifact(result.artifact);
          if (result.thumbnailReady === true) this.callbacks.onThumbnailReady();
          if (result.silent !== true) shouldCreateResponse = true;
          await this.returnToolOutput(callId, result);
        } catch (error) {
          if (gen !== this.sessionGen) return;
          // The model must always get an answer per call_id, or the
          // conversation dead-ends waiting for a function_call_output.
          await this.returnToolOutput(callId, {
            ok: false,
            error: error instanceof Error ? error.message : String(error),
          });
          shouldCreateResponse = true;
        }
      }

      // A tool whose turn was superseded (the user typed or spoke while it
      // ran) still posted its output above for context, but must not queue a
      // spoken follow-up on top of the new turn's answer.
      if (shouldCreateResponse && gen === this.sessionGen && turn === this.turnGen) {
        this.pendingResponseCreate = true;
      }
    } finally {
      // A stale invocation's session already reset these counters — only the
      // generation that incremented them may decrement.
      if (gen === this.sessionGen) {
        this.activeToolCalls -= 1;
        if (this.activeToolCalls === 0) this.toolRunning = false;
        // Fires only once the model's turn is over AND no sibling call is
        // still running (also re-checked by the response.done handler).
        this.maybeCreateResponse();
        // A silent tool (e.g. thumbnail generation) queues no follow-up —
        // don't leave the face stuck on "working" forever.
        if (
          this.activeToolCalls === 0 &&
          !this.responseActive &&
          !this.pendingResponseCreate &&
          this.mood === "working"
        ) {
          this.setMood("idle");
        }
      }
    }
  }

  private async returnToolOutput(callId: string, result: LooperToolResult): Promise<void> {
    this.sendEvent({
      type: "conversation.item.create",
      item: {
        type: "function_call_output",
        call_id: callId,
        output: JSON.stringify(sanitizeToolResult(result)),
      },
    });
  }

  private sendEvent(event: Record<string, unknown>): void {
    if (this.dc?.readyState === "open") {
      this.dc.send(JSON.stringify(event));
    } else {
      this.callbacks.onStatus("Voice link not open — an event was dropped.");
    }
  }

  private setMood(mood: LooperMood): void {
    if (this.mood === mood) return;
    this.mood = mood;
    this.callbacks.onMood(mood);
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer) {
      window.clearTimeout(this.reconnectTimer);
      this.reconnectTimer = 0;
    }
  }

  private clearGraceTimer(): void {
    if (this.disconnectGraceTimer) {
      window.clearTimeout(this.disconnectGraceTimer);
      this.disconnectGraceTimer = 0;
    }
  }

  private startOutputMeter(stream: MediaStream): void {
    this.stopOutputMeter();

    const audioContext = new AudioContext();
    const source = audioContext.createMediaStreamSource(stream);
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 1024;
    analyser.smoothingTimeConstant = 0.72;
    source.connect(analyser);

    this.audioContext = audioContext;
    this.outputAnalyser = analyser;

    const samples = new Uint8Array(analyser.fftSize);
    const frequencies = new Uint8Array(analyser.frequencyBinCount);
    const tick = () => {
      analyser.getByteTimeDomainData(samples);
      analyser.getByteFrequencyData(frequencies);
      let total = 0;
      for (const sample of samples) {
        const centered = (sample - 128) / 128;
        total += centered * centered;
      }
      const rms = Math.sqrt(total / samples.length);
      const energy = clamp01(rms * 10.5);
      const bands = getSpeechBands(frequencies);

      // Over WebRTC there are no audio-delta data-channel events, so the
      // reply audio itself is the source of truth for the "speaking" mood:
      // it starts when sound starts and ends when the sound actually ends.
      if (energy > 0.06) {
        this.lastAudibleAt = performance.now();
        // Audible output wins even mid-tool: a spoken ack before a long tool
        // call should show a talking face; the silence branch below restores
        // "working" once the audio ends.
        if (this.mood !== "speaking" && this.mood !== "listening") {
          this.setMood("speaking");
        }
      } else if (this.mood === "speaking" && performance.now() - this.lastAudibleAt > 450) {
        this.setMood(this.toolRunning ? "working" : "idle");
      }

      // Simple realtime viseme approximation: low energy rounds the mouth,
      // mid energy opens it, high energy stretches it for consonants/ee sounds.
      const target: MouthShape = {
        open: clamp01(energy * 0.75 + bands.mid * 0.45 - bands.high * 0.16),
        width: clamp01(0.28 + bands.mid * 0.55 + bands.high * 0.74 - bands.low * 0.28),
        round: clamp01(0.08 + bands.low * 0.95 + energy * 0.1 - bands.high * 0.42),
        teeth: clamp01(bands.high * 1.4 + bands.mid * 0.25 - bands.low * 0.35),
      };

      this.smoothedMouthShape = smoothMouthShape(this.smoothedMouthShape, target, 0.36);
      this.callbacks.onMouthShape(this.smoothedMouthShape);
      this.outputMeterFrame = window.requestAnimationFrame(tick);
    };
    tick();
  }

  private stopOutputMeter(): void {
    if (this.outputMeterFrame) {
      window.cancelAnimationFrame(this.outputMeterFrame);
      this.outputMeterFrame = 0;
    }
    void this.audioContext?.close();
    this.audioContext = null;
    this.outputAnalyser = null;
    this.smoothedMouthShape = silentMouthShape();
  }
}

function friendlyErrorMessage(error: unknown): string {
  const raw = error instanceof Error ? error.message : String(error);
  // ipcMain.handle rejections arrive wrapped — strip the Electron noise.
  return raw.replace(/^Error invoking remote method '[^']+': (?:Error: )?/, "");
}

function silentMouthShape(): MouthShape {
  return { open: 0, width: 0.18, round: 0, teeth: 0 };
}

function smoothMouthShape(current: MouthShape, target: MouthShape, amount: number): MouthShape {
  return {
    open: lerp(current.open, target.open, amount),
    width: lerp(current.width, target.width, amount),
    round: lerp(current.round, target.round, amount),
    teeth: lerp(current.teeth, target.teeth, amount),
  };
}

function getSpeechBands(frequencies: Uint8Array): { low: number; mid: number; high: number } {
  const low = averageRange(frequencies, 2, 14) / 255;
  const mid = averageRange(frequencies, 14, 48) / 255;
  const high = averageRange(frequencies, 48, 110) / 255;
  return { low: clamp01(low * 2.2), mid: clamp01(mid * 2.1), high: clamp01(high * 2.8) };
}

function averageRange(values: Uint8Array, start: number, end: number): number {
  const cappedEnd = Math.min(end, values.length);
  if (start >= cappedEnd) return 0;
  let total = 0;
  for (let index = start; index < cappedEnd; index += 1) {
    total += values[index];
  }
  return total / (cappedEnd - start);
}

function lerp(from: number, to: number, amount: number): number {
  return from + (to - from) * amount;
}

function clamp01(value: number): number {
  return Math.min(1, Math.max(0, value));
}

export function newEntry(role: TranscriptEntry["role"], text: string): TranscriptEntry {
  return {
    id: crypto.randomUUID(),
    text,
    role,
    at: new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }),
  };
}

function safeParseEvent(raw: string): ServerEvent {
  try {
    return JSON.parse(raw) as ServerEvent;
  } catch {
    return {};
  }
}

function parseToolArguments(raw: string): Record<string, unknown> {
  try {
    const parsed = JSON.parse(raw) as unknown;
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? (parsed as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

function sanitizeToolResult(result: LooperToolResult): LooperToolResult {
  if (!result.artifact) return result;

  const { artifact, ...rest } = result;
  return {
    ...rest,
    artifact: {
      title: artifact.title,
      kind: artifact.kind,
      content:
        artifact.kind === "thumbnailBoard"
          ? "Thumbnail board rendered in the UI. Use the compact board field for exact numbers, selected state, and loading state."
          : artifact.kind === "image" || artifact.kind === "imageLoading"
            ? "Image rendered in the UI."
            : artifact.content.length > 1200
              ? `${artifact.content.slice(0, 1200)}...`
              : artifact.content,
      language: artifact.language,
      fullscreen: artifact.fullscreen,
    },
  };
}

function collectItemText(item: ServerEvent["item"]): string {
  return item?.content?.map((part) => part.transcript || part.text || "").filter(Boolean).join("\n") || "";
}

function collectOutputText(item: ResponseOutputItem): string {
  return item.content?.map((part) => part.transcript || part.text || "").filter(Boolean).join("\n") || "";
}
