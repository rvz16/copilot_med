**Slide 1. Why Transcription Was a Core Engineering Problem**  
On-slide:
- Transcription was the entry point for all three MedCoPilot services
- Real-time assistant required low-latency, stable streaming text
- Offline analytics required high transcript fidelity
- Documentation required clinically coherent text for SOAP generation

Presenter script:  
Transcription was not just one supporting module in MedCoPilot. It was the foundation for the live consultation assistant, the offline analytics engine, and the documentation pipeline. Because of that, our objective was broader than speech-to-text accuracy alone: we needed a system that could handle Russian medical dialogue, stream reliably in real time, and produce stable text that downstream components could trust.

**Slide 2. Our Initial STT Foundation and Performance Optimization**  
On-slide:
- Selected a Whisper-based Russian transcription stack
- Chose `antony66/whisper-large-v3-russian` as the core model
- Pre-converted the model to CTranslate2
- Served it through `faster-whisper`
- Achieved roughly 2x faster inference
- On Kaggle T4: about 8.5 seconds of audio processed per 1 second

Presenter script:  
We began by building a strong offline-quality transcription core. Our model choice was a Russian-specialized Whisper checkpoint, optimized for practical deployment through CTranslate2 and Faster-Whisper. This gave us a substantial speedup and confirmed that the acoustic engine itself was strong enough for production-style experimentation. At this stage, the main lesson was that model throughput was no longer the bottleneck; the main challenge shifted to streaming quality.

**Slide 3. The Key Real-Time Failure: Naive Chunking**  
On-slide:
- First streaming version used fixed audio chunks
- Words were cut at chunk boundaries
- Linguistic and clinical context was lost between chunks
- Medical terms and long phrases became unstable
- Main conclusion: the problem was architectural, not only model-related

Presenter script:  
Our first real-time prototype worked technically, but it exposed the central weakness of simple streaming ASR. Fixed chunking creates artificial acoustic boundaries, so words can be split across requests, and the model loses the context needed to interpret phrases correctly. In clinical speech, this is especially damaging because meaning often depends on phrase continuation, terminology, and sentence structure. This was the turning point where we recognized that we had to redesign the pipeline, not just tune the model.

**Slide 4. Session-Aware Streaming Architecture**  
On-slide:
- Introduced per-session audio and transcript context
- Decoded incoming audio to 16 kHz mono PCM
- Stored the trailing audio tail for each active session
- Prepended historical audio context to new chunks before inference
- Preserved full API compatibility with the session manager

Presenter script:  
To solve the boundary problem, we moved from stateless chunk transcription to a session-aware design. Each consultation now has its own in-memory context: a recent audio tail and the current stable transcript. When a new chunk arrives, we decode it to PCM, attach the previous audio context, and transcribe the combined signal. This gave the model the acoustic continuity it needed while keeping the external API contract unchanged, which was critical for safe integration with the session manager.

**Slide 5. Hybrid Inference Strategy: Groq by Default, Local Whisper as Fallback**  
On-slide:
- Added Groq API as the default real-time backend
- Retained local Faster-Whisper as a fully supported alternative
- Switched backend through configuration, not API changes
- Avoided unnecessary local model loading in Groq mode
- Combined production responsiveness with deployment flexibility

Presenter script:  
After validating the local inference path, we added a second execution mode: Groq API as the default backend for fast real-time transcription. Importantly, we did not replace the local pipeline; we preserved it as a robust fallback and self-hosted option. This gave us a hybrid design with strong operational flexibility: the surrounding system continues to call the same endpoints, while the transcription service selects the inference engine internally based on configuration.

**Slide 6. Stabilizing Streaming Output: Fuzzy Text Alignment and Hallucination Control**  
On-slide:
- Replaced brittle timestamp-based overlap removal with text-based fuzzy alignment
- Compared new transcript windows against the stable transcript tail
- Extracted only truly new text as `delta_text`
- Added Russian medical prompt conditioning
- Added multi-stage hallucination filtering for silence and low-confidence output

Presenter script:  
Once overlapping audio was introduced, the next challenge was transcript duplication and instability. Timestamp-based overlap handling proved too fragile for streaming conditions, especially with cloud inference, so we replaced it with fuzzy text alignment. The system now compares the new transcript with the tail of the stabilized transcript and keeps only the genuinely new words. In parallel, we added decoder prompting and aggressive filtering to suppress hallucinations, especially the non-clinical artifacts that appear during silence or low-confidence regions.

**Slide 7. Solving Silence Robustly and Final Outcome**  
On-slide:
- Added neural VAD with speech-aware pre-filtering
- Masked non-speech regions with digital silence before transcription
- Skipped unnecessary STT calls when speech was absent
- Preserved timeline consistency during pauses
- Added retries, timeout handling, validation, and cleanup logic
- Result: a robust, production-oriented streaming transcription microservice

Presenter script:  
The last major step was making the system robust during silence and background noise. We integrated neural voice activity detection to decide whether speech is present before transcription, and we mask non-speech regions with zeros so the recognizer sees clean speech instead of noisy silence. Just as importantly, we preserve session timing even when no speech is detected, so the streaming timeline remains consistent. The final result is a significantly more stable transcription service that is fast, session-aware, medically oriented, and ready to serve as the textual foundation for the rest of MedCoPilot.

If you want, I can now turn this into a polished **speaker-ready 7-slide deck with shorter slide bullets and fuller oral script**.