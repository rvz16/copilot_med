import type { LLMProvider, SessionLLMConfig, SessionLLMConfigInput } from '../types/types';

export interface LlmPreset {
  id: string;
  label: string;
  provider: LLMProvider;
  config: SessionLLMConfigInput;
  note: string;
}

export const DEFAULT_LLM_CONFIG: SessionLLMConfigInput = {
  provider: 'ollama',
  model_name: 'qwen3:4b',
  base_url: 'http://host.docker.internal:11434',
};

export const LLM_PRESETS: LlmPreset[] = [
  {
    id: 'ollama',
    label: 'Ollama',
    provider: 'ollama',
    config: {
      provider: 'ollama',
      model_name: 'qwen3:4b',
      base_url: 'http://host.docker.internal:11434',
    },
    note: 'Локальный Ollama через native `/api/chat`.',
  },
  {
    id: 'gemini',
    label: 'Gemini',
    provider: 'gemini',
    config: {
      provider: 'gemini',
      model_name: 'gemini-2.5-flash',
      base_url: 'https://generativelanguage.googleapis.com/v1beta/openai',
    },
    note: 'Gemini через OpenAI-compatible endpoint.',
  },
  {
    id: 'yandexgpt',
    label: 'YandexGPT',
    provider: 'yandexgpt',
    config: {
      provider: 'yandexgpt',
      model_name: 'gpt://<folder-id>/yandexgpt-lite/latest',
      base_url: '',
    },
    note: 'Укажите ваш Yandex endpoint и дополнительные заголовки при необходимости.',
  },
  {
    id: 'azure-openai',
    label: 'Azure OpenAI',
    provider: 'azure_openai',
    config: {
      provider: 'azure_openai',
      model_name: 'gpt-4.1-mini',
      base_url: 'https://your-resource.openai.azure.com',
      api_version: '2024-10-21',
    },
    note: 'ChatGPT deployment через Azure OpenAI.',
  },
];

export function cloneLlmConfig(config: SessionLLMConfigInput): SessionLLMConfigInput {
  return {
    provider: config.provider,
    model_name: config.model_name,
    base_url: config.base_url ?? '',
    api_key: config.api_key ?? '',
    api_version: config.api_version ?? '',
    http_referer: config.http_referer ?? '',
    x_title: config.x_title ?? '',
    extra_headers_json: config.extra_headers_json ?? '',
  };
}

export function publicConfigFromInput(config: SessionLLMConfigInput): SessionLLMConfig {
  return {
    provider: config.provider,
    model_name: config.model_name,
    base_url: config.base_url ?? null,
    api_version: config.api_version ?? null,
    http_referer: config.http_referer ?? null,
    x_title: config.x_title ?? null,
    has_api_key: Boolean(config.api_key?.trim()),
    has_extra_headers: Boolean(config.extra_headers_json?.trim()),
  };
}

export function llmProviderLabel(provider: LLMProvider): string {
  switch (provider) {
    case 'azure_openai':
      return 'Azure OpenAI';
    case 'gemini':
      return 'Gemini';
    case 'yandexgpt':
      return 'YandexGPT';
    case 'openai_compatible':
      return 'OpenAI Compatible';
    case 'ollama':
    default:
      return 'Ollama';
  }
}
