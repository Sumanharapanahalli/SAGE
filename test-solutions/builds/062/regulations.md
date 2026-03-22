# Regulatory Compliance — Voice Assistant

**Domain:** ml_ai
**Solution ID:** 062
**Generated:** 2026-03-22T11:53:39.325993
**HITL Level:** standard

---

## 1. Applicable Standards

- **GDPR**
- **CCPA**
- **Biometric Privacy Laws**

## 2. Domain Detection Results

- ml_ai (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 19 | SECURITY | Perform security review of the voice assistant. Threat model: unauthorized micro | Threat modeling, penetration testing |

**Total tasks:** 20 | **Compliance tasks:** 1 | **Coverage:** 5%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | GDPR compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |
| 2 | CCPA compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 3 | Biometric Privacy Laws compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

## 5. Risk Assessment Summary

**Risk Level:** STANDARD — Compliance focus on data protection and quality

| Risk Category | Mitigation in Plan |
|--------------|-------------------|
| Data Privacy | SECURITY + LEGAL tasks |
| Service Quality | QA + SYSTEM_TEST tasks |
| Compliance Gap | REGULATORY tasks (if applicable) |

## 6. Agent Team Assignment

| Agent Role | Tasks Assigned | Team |
|-----------|---------------|------|
| developer | 10 | Engineering |
| data_scientist | 6 | Analysis |
| devops_engineer | 1 | Engineering |
| qa_engineer | 1 | Engineering |
| system_tester | 1 | Engineering |
| technical_writer | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 52/100 (FAIL) — 1 iteration(s)

**Summary:** This plan covers the full pipeline surface area and shows genuine ML/systems depth — the per-stage latency targets, ONNX export strategy, VAD-gated recording, and confidence-threshold clarification design are all sound. However, it has at least three showstopper-class omissions that will halt implementation before integration testing: (1) no Acoustic Echo Cancellation, which means the deployed system will loop on its own voice; (2) Docker audio passthrough is unaddressed, meaning the containerized acceptance criteria is physically unrunnable; and (3) the 2-second end-to-end latency target is impossible on CPU with Whisper base + Coqui VITS — the plan will need either a GPU requirement or a model downgrade. Additionally, the dialog layer's ReAct/multi-agent framing is architecturally confused — encoding models cannot perform reasoning loops — and the tool implementations are entirely missing. For an MVP, this scores 52: the individual component designs are reasonable, but the integration seams (audio hardware, real latency, generative dialog, tooling) have fundamental gaps that will consume significantly more time than the plan implies. A revised plan that drops the agentic dialog layer to a simple FSM, acknowledges GPU as a hard requirement for the latency targets, adds AEC, and specifies the Docker audio strategy would be credible at 68-72.

### Flaws Identified

1. Acoustic Echo Cancellation (AEC) is completely absent. When TTS plays through speakers, the microphone will pick it up and continuously re-trigger the wake word detector. This is a fundamental signal processing requirement for any voice assistant with co-located mic+speaker — not an edge case. Without AEC (or at minimum ducking + gating), the system will loop endlessly on its own output. This is a showstopper.
2. Docker audio access is not addressed. Step 16 containerizes everything, but sounddevice requires direct hardware audio (ALSA/PulseAudio on Linux). Containers have no microphone/speaker access without explicit device passthrough (--device /dev/snd, plus PulseAudio socket mounting or PipeWire bridging). The docker-compose.yaml will not work on cold state without this, directly contradicting the Step 16 acceptance criteria.
3. End-to-end 2-second latency target (Step 14) is unrealistic on CPU. Whisper base.en alone takes 3-8x real-time on CPU for a 5-second utterance (i.e., 15-40 seconds). Adding Coqui VITS synthesis (notoriously slow on CPU, often 5-15x real-time), DistilBERT inference, and audio buffering, the real figure on a modern laptop is closer to 8-20 seconds. The plan has no GPU dependency or hardware qualification — it cannot hit 2 seconds on CPU with this model stack.
4. Step 11 'ReAct loops' on top of ONNX DistilBERT is architecturally incoherent. ReAct requires an autoregressive LLM capable of chain-of-thought reasoning and dynamic tool invocation. DistilBERT is an encoder-only classification model that outputs a probability vector — it cannot loop, reason, or call tools. The entire agentic layer (ClarificationAgent, FulfillmentAgent, FallbackAgent) would require a separate generative LLM (e.g., Llama, GPT, Claude), which is never mentioned in the plan.
5. False accept rate definition contradicts itself. Step 4 description says '< 0.5 per hour' but the payload says target_false_accept_rate: 0.005 (dimensionless). These are incompatible units. A 0.5/hr FAR on a 1-second sliding window with 50% hop equates to roughly 0.5/(3600 * 2) ≈ 0.0000694 per window — completely different from 0.005. The acceptance criteria will pass or fail based on which interpretation QA uses.
6. No ASR fine-tuning data collection step exists. Step 5 fine-tunes Whisper on domain-specific vocabulary but depends only on Step 1 (setup). There is no data pipeline step for collecting or generating labeled transcribed audio for ASR fine-tuning. The NLU text corpus (Step 3) cannot substitute — Whisper needs audio+transcript pairs, not text JSONL.
7. Tool implementations for FulfillmentAgent are never built. Steps 11 and 14 reference set_timer_tool, search_music_tool, get_weather_tool, and smart_home_tool as callable, but no step anywhere in the plan implements these. No API integrations, no stub implementations, no acceptance criteria around tool execution. The FulfillmentAgent will have no working fulfillment path.
8. MOS evaluation requires human listeners and is operationally undefined. Step 7 targets MOS >= 3.8 but Mean Opinion Score requires human raters (ITU-T P.800 protocol). No evaluation protocol, rater pool, or automated proxy (UTMOS, MOSNet) is mentioned. The acceptance criteria 'TTS produces intelligible speech' is not a MOS test — it's a subjective binary pass.
9. Python-level audio buffer zeroization cannot be reliably verified by unit test. Step 19 requires 'audio buffers explicitly zeroed after ASR processing (verified by unit test)'. Python's GC manages memory; numpy arrays and bytes objects cannot be reliably wiped in pure Python without ctypes/mmap tricks. A unit test asserting the array is zeros after del() is not evidence of actual memory zeroization — it just checks the reference was cleared.
10. Wake word positive sample sourcing is unspecified. Step 2 requires 2000 positive samples of 'hey sage' spoken in varied conditions. It says 'collect and augment' but no collection methodology, speaker pool, consent process, or recording setup is defined. This is months of data collection work glossed over in one line. TTS synthesis of the wake word (a standard bootstrapping technique) is never mentioned.
11. Phrase cache contradicts audio data retention security goal. Step 12 caches TTS audio to disk keyed by SHA256 of the text. Step 19 says audio buffers must be zeroed after processing. The phrase cache is persistent audio storage on disk — these two requirements directly conflict. The cache must be in-scope for the retention threat model but is excluded.
12. Streaming partial transcription from Whisper is non-trivial and understated. Step 9 requires 'streaming partial results update at least every 300ms' from Whisper. Standard Whisper is batch-only. Achieving this requires either Distil-Whisper-streaming, chunked inference with beam search continuation, or a third-party streaming wrapper — none of which are mentioned. Chunked inference significantly degrades WER.

### Suggestions

1. Add an AEC/signal processing step before Step 8. Use WebRTC's built-in AEC (available via the webrtcvad package ecosystem or py-webrtc-audio-processing) or implement TTS-gated microphone muting: physically block microphone input while sounddevice is playing TTS output. The latter is simpler for MVP.
2. Replace the Docker audio approach with a hybrid deployment: containerize the API and NLU/ASR inference, but run the audio capture/playback pipeline as a native service on the host that communicates with the container over localhost WebSocket. Document this split clearly in the deployment guide.
3. Revise latency targets to be hardware-conditional. State explicitly: 'GPU (CUDA) target: 2s, CPU-only target: 8s.' Use faster models for CPU-only path: Whisper tiny.en (3x faster than base.en), Piper TTS instead of Coqui VITS (10-50x faster on CPU), and profile before committing to numbers.
4. Replace the ReAct/multi-agent dialog layer with a simpler finite state machine for MVP. A state machine with states (slot_filling, confirming, executing, fallback) driven by NLUResult fields is implementable, testable, and correct. Add an LLM-backed agent layer in a future iteration once the FSM is proven.
5. Add Step 2b: ASR fine-tuning data collection. Generate 500-1000 audio+transcript pairs using TTS synthesis of the NLU utterances from Step 3, record 100+ real-user utterances of common commands, and supplement with Mozilla Common Voice domain-filtered subsets.
6. Reduce tool scope for MVP. Implement only set_timer_tool (no external API needed, just a local countdown) and get_weather_tool (single OpenWeatherMap API call). Mark search_music_tool and smart_home_tool as stubs that return a canned FulfillmentResponse. This unblocks Step 11 testing without months of integration work.
7. Define MOS evaluation concretely or replace with automated proxy. Use UTMOS (a neural MOS predictor) as the automated CI check, targeting a UTMOS score > 3.5. Reserve human MOS evaluation for a quarterly benchmark, not a per-build acceptance criterion.
8. Add Step 2c: wake word bootstrap via TTS synthesis. Use a high-quality TTS model to synthesize 'hey sage' in 20+ voice styles, then augment. This is the industry-standard technique for cold-start wake word training and reduces real-recording burden to 200-300 samples for speaker diversity fine-tuning.

### Missing Elements

1. Acoustic Echo Cancellation (AEC) — no step, no library, no design. Required before any end-to-end test is meaningful.
2. Docker audio device passthrough strategy — --device flags, PulseAudio/PipeWire socket mounting, or host-network audio proxy pattern.
3. Tool implementation steps — set_timer_tool, get_weather_tool, search_music_tool, smart_home_tool need actual implementation steps, API keys, and acceptance criteria.
4. ASR fine-tuning dataset creation — Step 5 has no data dependency despite requiring domain audio+transcript pairs.
5. Model warm-up / startup time budget — loading 4 models (Whisper, DistilBERT, VITS, wake word ONNX) into RAM takes 30-90 seconds. No /health readiness probe or startup sequencing is defined.
6. Memory footprint analysis — PyTorch + 4 models simultaneously in RAM. Whisper base (~145MB), DistilBERT (~260MB), Coqui VITS (~150MB), PyTorch runtime (~1.5GB). Total ~2.5GB RAM floor on CPU. Never mentioned.
7. Wake word negative sample sourcing — Step 2 needs 10,000 negative samples. Where do these come from? LibriSpeech? ESC-50? MUSAN? Not specified.
8. GPU/CPU deployment flag — the entire model stack changes behavior (and meets/fails latency targets) depending on hardware. No mechanism to switch between CPU/GPU inference paths.
9. Noise robustness and far-field testing plan — wake word performance at 3 meters, SNR -5dB, with TV background is never tested. The Step 4 acceptance criteria only tests 'held-out test set' which is likely close-mic clean audio.
10. Session state persistence backing store — Step 11 ConversationContext 'persists across turns' but storage medium (in-memory dict, Redis, SQLite) is never specified. Service restart loses all sessions silently.
11. License compliance review — Coqui TTS has a custom license with attribution requirements; Whisper is MIT but fine-tuned derivatives may have distribution constraints. No legal review step.

### Security Risks

1. API key in plain HTTP header is logged by every reverse proxy, load balancer, and CDN by default. Production deployments will leak keys to access logs. Mitigate with short-lived JWT tokens or HMAC-signed requests, not static keys in X-API-Key headers.
2. The phrase cache (Step 12, SHA256 keyed) creates permanent audio files on disk containing synthesized speech of every unique response text. If the system is used with sensitive queries (medical info, personal data), these cached WAV files are unencrypted PII at rest. Step 19's audio zeroization applies to in-memory buffers only — the cache is excluded.
3. Step 19 frames 'prompt injection into NLU' as the threat, but the NLU model is ONNX DistilBERT — prompt injection is not a valid threat for a classifier. The actual adversarial threat is classifier evasion: crafted utterances that get misclassified into high-confidence wrong intents (e.g., triggering smart_home_tool with a sentence that looks like a weather query). This is unaddressed.
4. WebSocket endpoint /ws/stream accepts binary audio frames — no mention of maximum frame size limits. A client can stream arbitrarily large audio buffers, causing unbounded memory accumulation. The 10-second VAD timeout in Step 9 mitigates this at the application layer but not at the WebSocket protocol layer.
5. Model files downloaded by entrypoint script (Step 16) have no integrity verification. A compromised download source or MITM on the model download could substitute malicious ONNX files. ONNX runtime has a history of CVEs around malformed model parsing. SHA256 checksums for all model artifacts must be pinned in the download script.
6. Microphone access in a browser context (Step 15 Web UI) requires HTTPS. The plan deploys over HTTP in docker-compose with no TLS termination step. Chrome and Firefox block navigator.mediaDevices.getUserMedia() on non-localhost HTTP origins, breaking the entire frontend without HTTPS.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.326023
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)
