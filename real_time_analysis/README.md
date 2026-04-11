# MedCoPilot — Realtime Insight Service

Контейнер №1 платформы MedCoPilot. Принимает текст врачебной консультации, обогащает его данными пациента из FHIR и возвращает клинические подсказки в реальном времени.

## Архитектура

```
┌──────────────┐     POST /v1/assist      ┌─────────────────────────┐
│   Клиент     │ ──────────────────────── │  Realtime Insight        │
│  (фронт/API) │ ◄─── JSON response ──── │  Service (FastAPI)       │
└──────────────┘                          │  :8000                   │
                                          └───┬──────────┬──────────┘
                                              │          │
                              ┌───────────────┘          └───────────────┐
                              ▼                                          ▼
                    ┌──────────────────┐                       ┌─────────────────┐
                    │  Ollama / vLLM   │                       │  FHIR Server    │
                    │  (LLM inference) │                       │  (HAPI FHIR R4) │
                    │  :11434          │                       │  :8092          │
                    └──────────────────┘                       └─────────────────┘
```

### Как это работает

1. Клиент отправляет `POST /v1/assist` с текстом консультации и (опционально) `patient_id`
2. Запускаются:
   - **FHIR-запрос** → HAPI FHIR R4 сервер: Patient, Condition, MedicationRequest, AllergyIntolerance
   - **LLM-запрос** → Ollama или OpenAI-совместимый hosted API генерирует структурированный JSON: диагнозы, вопросы, предупреждения, лекарственные взаимодействия
3. **Эвристики** (regex) извлекают симптомы, лекарства, витальные показатели из текста
4. Результаты LLM + эвристик **мержатся**, FHIR-контекст пациента добавляется в ответ
5. Ответ возвращается как JSON

### Потоки данных

- **LLM** — либо нативный Ollama API (`/api/chat`), либо OpenAI-совместимый endpoint (`/chat/completions`) для OpenRouter, Google AI Developer compatibility layer, vLLM и similar gateways
- **FHIR** — стандартный REST: `GET Patient/{id}`, `GET Condition?patient={id}`, `GET MedicationRequest?patient={id}`, `GET AllergyIntolerance?patient={id}` (параллельно через asyncio)
- **Эвристики** — детерминированные regex-правила для drug interactions (warfarin+NSAIDs и др.) и извлечения фактов

## Структура файлов

```
app/
├── main.py                      # FastAPI app, lifespan, create_app()
├── schemas.py                   # Pydantic модели (request/response)
├── llm_client.py                # Async клиент к Ollama и OpenAI-compatible APIs
├── fhir_client.py               # Async FHIR R4 клиент (httpx)
├── heuristics.py                # Regex-эвристики, drug interaction rules
└── controllers/
    └── assist_controller.py     # POST /v1/assist, GET /health
tests/
├── conftest.py
└── test_assist_contract.py      # Тесты с моками LLM и FHIR
scripts/
└── create_clearml_qwen3_task.py # Деплой vLLM на GPU через ClearML
Dockerfile
docker-compose.yml
requirements.txt
```

## API

### `GET /health`

Проверка работоспособности.

```json
{
  "status": "ok",
  "model": "qwen3:4b",
  "vllm_url": "http://localhost:11434",
  "fhir_url": "http://158.160.84.63:8092/hapi-fhir-jpaserver/fhir"
}
```

### `POST /v1/assist`

Основной эндпоинт. Принимает текст консультации, возвращает клинические подсказки.

**Request:**
```json
{
  "request_id": "req-123",
  "patient_id": "1",
  "transcript_chunk": "Пациент жалуется на боль в животе, тошноту.",
  "context": {
    "language": "ru",
    "fhir_base_url": null
  }
}
```

| Поле | Тип | Обязательное | Описание |
|------|-----|:---:|----------|
| `request_id` | string | да | Уникальный ID запроса |
| `patient_id` | string | нет | ID пациента в FHIR. Если указан — подтягивается контекст из EHR |
| `transcript_chunk` | string | да | Текст консультации (транскрипт) |
| `context.language` | "ru" \| "en" | нет | Язык (default: "en") |
| `context.fhir_base_url` | string | нет | Переопределить FHIR сервер для этого запроса |

**Response:**
```json
{
  "request_id": "req-123",
  "latency_ms": 5369,
  "model": { "name": "qwen3:4b", "quantization": "none" },
  "suggestions": [
    {
      "type": "diagnosis_suggestion",
      "text": "Проверить гипертонию",
      "confidence": 0.7,
      "evidence": ["Пациент жалуется на головную боль..."]
    }
  ],
  "drug_interactions": [
    {
      "drug_a": "warfarin",
      "drug_b": "ibuprofen",
      "severity": "high",
      "rationale": "Higher bleeding risk when anticoagulants combined with NSAIDs.",
      "confidence": 0.91
    }
  ],
  "extracted_facts": {
    "symptoms": ["боль в животе", "тошнота"],
    "conditions": [],
    "medications": ["ibuprofen", "warfarin"],
    "allergies": [],
    "vitals": { "age": null, "weight_kg": null, "height_cm": null, "bp": "140/90", "hr": null, "temp_c": 38.2 }
  },
  "knowledge_refs": [
    { "source": "mock_kb", "title": "General Symptom Triage Checklist", "snippet": "...", "url": null, "confidence": 0.6 }
  ],
  "patient_context": {
    "patient_name": "Abdul Koepp",
    "gender": "male",
    "birth_date": "1954-10-02",
    "conditions": ["Body mass index 30+ - obesity (finding)", "Viral sinusitis (disorder)"],
    "medications": ["Ibuprofen 200 MG Oral Tablet"],
    "allergies": []
  },
  "errors": []
}
```

| Поле | Описание |
|------|----------|
| `suggestions` | Подсказки от LLM + эвристик. type: `diagnosis_suggestion`, `question_to_ask`, `next_step`, `warning` |
| `drug_interactions` | Лекарственные взаимодействия (severity: low/medium/high) |
| `extracted_facts` | Извлечённые факты из транскрипта (симптомы, лекарства, витальные показатели) |
| `knowledge_refs` | Ссылки на медицинские источники |
| `patient_context` | Данные пациента из FHIR (null если patient_id не указан) |
| `errors` | Ошибки (пустой список = всё ок) |

## Переменные окружения

| Переменная | Default | Описание |
|------------|---------|----------|
| `LLM_PROVIDER` | `ollama` | `ollama` или `openai_compatible` |
| `MODEL_NAME` | `qwen3:4b` | Имя модели |
| `LLM_BASE_URL` | `http://localhost:11434` | URL Ollama или OpenAI-compatible сервера |
| `LLM_API_KEY` | empty | API key для hosted OpenAI-compatible провайдеров |
| `LLM_HTTP_REFERER` | empty | Опциональный `HTTP-Referer`, useful for OpenRouter |
| `LLM_X_TITLE` | `MedCoPilot` | Опциональный `X-Title`, useful for OpenRouter |
| `LLM_EXTRA_HEADERS_JSON` | empty | JSON object с дополнительными заголовками |
| `FHIR_BASE_URL` | `http://158.160.84.63:8092/hapi-fhir-jpaserver/fhir` | URL FHIR R4 сервера |
| `MAX_TOKENS` | `256` | Макс. токенов генерации LLM |
| `TEMPERATURE` | `0.0` | Температура генерации (0 = детерминированный) |
| `LLM_TIMEOUT` | `30.0` | Таймаут запроса к LLM (секунды) |
| `LOG_LEVEL` | `INFO` | Уровень логирования |

## Запуск

### Локально (без Docker)

```bash
# 1. Установи и запусти Ollama
ollama pull qwen3:4b
ollama serve  # если ещё не запущен

# 2. Установи зависимости
pip install -r requirements.txt

# 3. Запусти
uvicorn app.main:app --reload --port 8000
```

### Docker

```bash
# Ollama должен быть запущен на хосте
ollama serve

# Запуск контейнера
docker compose up --build
```

Контейнер обращается к Ollama на хосте через `host.docker.internal:11434`.

### Hosted providers

#### OpenRouter

```bash
LLM_PROVIDER=openai_compatible \
MODEL_NAME=google/gemini-2.0-flash-exp:free \
LLM_BASE_URL=https://openrouter.ai/api/v1 \
LLM_API_KEY=your_openrouter_key \
LLM_HTTP_REFERER=http://localhost:3000 \
LLM_X_TITLE=MedCoPilot \
uvicorn app.main:app --reload --port 8000
```

#### Google AI Developer compatibility layer

```bash
LLM_PROVIDER=openai_compatible \
MODEL_NAME=gemini-2.5-flash \
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai \
LLM_API_KEY=your_google_ai_studio_key \
uvicorn app.main:app --reload --port 8000
```

### Docker (GPU, продакшен с vLLM)

Для GPU-окружения замени Ollama на vLLM. В `docker-compose.yml`:

```yaml
services:
  vllm:
    image: vllm/vllm-openai:latest
    command: >
      --model Qwen/Qwen3-4B
      --dtype bfloat16
      --max-model-len 4096
      --gpu-memory-utilization 0.90
      --trust-remote-code
      --enforce-eager
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  realtime-insight:
    build: .
    environment:
      - LLM_PROVIDER=openai_compatible
      - MODEL_NAME=Qwen/Qwen3-4B
      - LLM_BASE_URL=http://vllm:8000/v1
    depends_on:
      vllm:
        condition: service_healthy
```

## Интеграция с другими контейнерами

### Для других сервисов MedCoPilot

Этот контейнер — **Container 1 (Realtime Insight Service)** из общей архитектуры MedCoPilot. Для интеграции с Container 2 (Offline Analytics) и Container 3 (Documentation Service):

1. **Сеть**: все контейнеры должны быть в одной Docker network
2. **Вызов этого сервиса**: `POST http://realtime-insight:8000/v1/assist`
3. **FHIR**: все контейнеры могут использовать один FHIR сервер — передать `FHIR_BASE_URL`
4. **LLM**: все контейнеры могут использовать один Ollama/vLLM инстанс — передать `LLM_BASE_URL`

Пример docker-compose для всей системы:

```yaml
services:
  realtime-insight:
    build: ./realtime-insight
    ports: ["8000:8000"]
    environment:
      - LLM_BASE_URL=http://ollama:11434
      - FHIR_BASE_URL=http://158.160.84.63:8092/hapi-fhir-jpaserver/fhir

  offline-analytics:
    build: ./offline-analytics
    ports: ["8001:8000"]
    environment:
      - LLM_BASE_URL=http://ollama:11434
      - FHIR_BASE_URL=http://158.160.84.63:8092/hapi-fhir-jpaserver/fhir

  documentation-service:
    build: ./documentation-service
    ports: ["8002:8000"]
    environment:
      - LLM_BASE_URL=http://ollama:11434
      - FHIR_BASE_URL=http://158.160.84.63:8092/hapi-fhir-jpaserver/fhir

  ollama:
    image: ollama/ollama
    ports: ["11434:11434"]
    volumes:
      - ollama_data:/root/.ollama

volumes:
  ollama_data:
```

### Зависимости контейнера

| Зависимость | Обязательная | Описание |
|-------------|:---:|----------|
| Ollama / vLLM | да | LLM inference. Без него suggestions будут пустыми (fallback на эвристики) |
| FHIR Server | нет | Без него `patient_context` будет null, но сервис работает |

## Тесты

```bash
pip install pytest
python -m pytest tests/ -v
```

Тесты используют моки LLM и FHIR — не требуют запущенных внешних сервисов.

## Производительность

| Конфигурация | Latency | Примечание |
|--------------|---------|------------|
| Ollama qwen3:4b, M4 Mac, MAX_TOKENS=256 | ~5-8 сек | Локальная разработка |
| Ollama qwen3:1.7b, M4 Mac | ~3-4 сек | Быстрее, но ниже качество |
| vLLM Qwen3-4B, A100 GPU | <2.5 сек | Продакшен |
