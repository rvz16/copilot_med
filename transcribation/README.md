# 🎙️ MedCoPilot Transcription Microservice

A high-performance, resilient microservice engineered specifically for the **real-time transcription of medical dialogues**.

This service tackles the fundamental challenges of streaming speech-to-text (STT) inference, such as severed words at chunk boundaries, loss of grammatical context, and model hallucinations during silence. It achieves offline-level accuracy in a real-time streaming context by utilizing a Sliding Window architecture, Neural Voice Activity Detection (VAD) audio masking, and Fuzzy Text Alignment.

## 🚀 Key Features & Capabilities

- **Dual Engine STT:** Native support for the ultra-fast **Groq API** (`whisper-large-v3-turbo`) as the primary engine for near-zero latency, with seamless automated fallback to a **local Faster-Whisper** (CT2) model to guarantee high availability in offline or high-load scenarios.
    
- **Zero-Hallucination Pipeline:** Whisper models inherently hallucinate (e.g., outputting "Thank you for watching") when exposed to background noise without speech. This service utilizes an integrated neural Silero VAD to dynamically "mask" non-speech segments with absolute digital silence (zeros) _before_ STT processing, completely eradicating hallucinations.
    
- **Smart Context (Sliding Window):** Medical terms and complex drug names often span across the arbitrary boundaries of audio chunks. By prepending a configurable "tail" of the previous audio chunk to the current one, the STT engine always receives full context, ensuring perfect declension, case matching, and terminology recognition.
    
- **Fuzzy Text Deduplication:** Overlapping audio context naturally produces duplicate transcribed text. Cloud APIs generate fluctuating timestamps, making timestamp-based deduplication unreliable. This service uses a sophisticated fuzzy string matching algorithm (`difflib.SequenceMatcher`) to find the exact overlap point and extract only the genuinely new words (the delta).
    
- **Self-Healing Architecture:** Built-in retry mechanisms and a decoupled audio-buffer state. If a network timeout occurs with Groq, the audio chunk is not lost; it is preserved in the in-memory context and appended to the next chunk, guaranteeing zero data loss.
    

## 🧠 Architectural Deep Dive: The Real-Time Pipeline

The processing pipeline is executed on every incoming audio chunk (recommended chunk size: 10 seconds). It consists of 5 highly optimized stages:

### 1. Neural VAD Pre-filtering & Audio Masking (`app/audio.py`)

Raw PCM audio is analyzed by the embedded Silero VAD model (processing takes ~5-15ms).

- **If no speech is detected:** The API call is bypassed entirely, saving token costs and API rate limits. To maintain the timeline integrity for the Session Manager, an array of zeros representing the silence is appended to the session buffer.
    
- **If speech is detected:** The VAD identifies exact speech timestamps. All audio outside these timestamps (paper rustling, chair squeaks, heavy breathing) is replaced with absolute zeros (`numpy.zeros`). The STT engine receives pristine speech isolated within digital silence.
    

### 2. Audio Context Orchestration (`app/routes.py`)

To prevent "severed word" syndrome, the masked chunk is concatenated with the audio tail from the previous request (stored in `session_store`). For example, a 10-second incoming chunk is prepended with 10 seconds of historical audio, resulting in a 20-second payload. This provides the Whisper model with the grammatical preamble required for accurate punctuation and spelling.

### 3. STT Processing (`app/model.py`)

The concatenated audio is sent to Groq API (or the local model). To further constrain the model and prevent language switching (a known issue with Whisper recognizing Russian speech over background noise), a hardcoded Cyrillic anchor prompt is injected into the request.

### 4. Aggressive Hallucination Filtering (`app/model.py`)

The verbose JSON response is scrutinized. Segments are dropped if:

- The `no_speech_prob` exceeds a strict threshold (e.g., `> 0.2`).
    
- The `avg_logprob` (model confidence) is critically low.
    
- The segment triggers specific regex patterns targeting common YouTube/Podcast training data artifacts (e.g., "Subtitles by Amara").
    

### 5. Fuzzy Text Alignment & Extraction (`app/transcript_alignment.py`)

The newly generated transcript is compared against the previously confirmed "stable" text of the session. A heuristic-based overlap detection algorithm scans the tail of the stable text and the prefix of the new text to find the exact overlap point. It seamlessly stitches the texts together, discarding the duplicated overlap and returning only the novel `delta_text`.

## 🛠 Installation & Deployment

The microservice is designed to be deployed as part of the broader `MedCoPilot` stack via Docker Compose.

```
# Boot up the entire MedCoPilot stack
docker-compose up -d

# Rebuild and start only the transcription microservice
docker-compose up -d --build transcribation
```

## ⚙️ Configuration & Tuning (`.env`)

The service is highly configurable. Variables are mapped from the global `.env` file located in the MedCoPilot project root.

### 1. STT Engine Settings

|Variable|Default|Description|
|---|---|---|
|`TRANSCRIBATION_USE_GROQ_API`|`true`|Set to `true` to utilize Groq API. Set to `false` to force local `faster-whisper` inference.|
|`TRANSCRIBATION_GROQ_API_KEY`|_(empty)_|Your Groq API key. Mandatory if `USE_GROQ_API=true`.|
|`TRANSCRIBATION_GROQ_MODEL`|`whisper-large-v3-turbo`|Target Groq model. `turbo` is highly recommended for optimal speed-to-accuracy ratio.|

### 2. Context & Sliding Window Settings

|Variable|Default|Description|
|---|---|---|
|`AUDIO_CONTEXT_SECONDS`|`10.0`|The duration of historical audio appended to the current chunk. Best practice: keep this equal to the chunk length configured in the Session Manager.|

### 3. Voice Activity Detection (Silero VAD) Tuning

_These parameters govern how aggressively the system filters out background noise. Tune them based on the clinical environment's microphone quality._

|Variable|Default|Description & Tuning Advice|
|---|---|---|
|`VAD_THRESHOLD`|`0.2`|**Sensitivity (0.0 - 1.0).** Decrease to `0.1` if quiet speech is being ignored. Increase to `0.4` or `0.5` if paper rustling/typing is falsely recognized as speech.|
|`VAD_MIN_SPEECH_MS`|`200`|**Anti-click protection (ms).** Minimum duration of sound to be considered a word. Increase to `300` if coughs or mouse clicks are leaking into the STT.|
|`VAD_MIN_SILENCE_MS`|`500`|Minimum silence duration (ms) required to split speech segments within a chunk.|
|`VAD_PAD_MS`|`400`|**Speech padding (ms).** Adds buffer time before and after detected speech. Increase to `500` or `600` if the endings of words (especially unvoiced consonants like "s" or "sh") are being prematurely cut off.|

### 4. Local Model Kaggle Authentication (Fallback)

If falling back to the local Faster-Whisper deployment, these Kaggle API variables are required to bootstrap the model weights:

- `KAGGLE_API_TOKEN`
    
- `KAGGLE_USERNAME`
    
- `KAGGLE_KEY`
    

## 📂 Project Structure

- `app/main.py` — FastAPI application entry point. Orchestrates lifecycle events and intelligently manages memory footprint (bypasses local model loading if Groq API is active).
    
- `app/routes.py` — The core orchestration controller. Handles incoming chunk ingestion, invokes VAD masking, manages contextual overlap, interacts with the STT engine, and returns cleanly aligned text to the Session Manager.
    
- `app/audio.py` — Audio processing utilities. Manages `ffmpeg` subprocessing to decode incoming audio streams (WebM/WAV) to float32 PCM arrays and applies the Silero VAD neural masking.
    
- `app/model.py` — The STT unified interface. Contains client wrappers for both Groq API and local Faster-Whisper. Features robust retry mechanisms, timeout handling, dynamic prompt anchoring, and rigorous post-transcription filtering.
    
- `app/transcript_alignment.py` — The Fuzzy Text Alignment engine. Replaces fragile timestamp logic with a robust `difflib.SequenceMatcher` heuristic to seamlessly stitch textual delta.
    
- `app/session_audio_context.py` — Thread-safe, in-memory dictionary acting as the temporal audio buffer for active medical sessions.
    
- `app/config.py` — Centralized environment variable parsing and type casting.
    

## 📡 API Reference

This internal API is strictly typed and is designed to be exclusively consumed by the **Session Manager** microservice.

### `POST /transcribe-chunk`

Processes an incremental audio chunk in a streaming session.

- **Form Payload:**
    
    - `session_id` (str): Unique identifier for the current medical consultation.
        
    - `seq` (int): Sequential index of the chunk.
        
    - `is_final` (bool): Flag indicating if this is the final chunk of the session.
        
    - `existing_stable_text` (str): The confirmed text accumulated so far.
        
    - `file` (UploadFile): The audio blob (e.g., `audio/webm` or `audio/wav`).
        
- **Response (JSON):**
    
    - `delta_text` (str): The newly recognized, non-duplicated words.
        
    - `stable_text` (str): The newly combined, fully aligned session transcript.
        
    - `speech_detected` (bool): True if VAD/STT recognized actual voice.
        

### `POST /transcribe`

Standard endpoint for offline, batch processing of entire audio files (utilized for asynchronous fallback analytics and EHR generation).

### `POST /finalize-session-transcript`

Gracefully cleans up in-memory data. Deletes the `session_id` buffer from the audio context dictionary to prevent memory leaks after the consultation concludes.
