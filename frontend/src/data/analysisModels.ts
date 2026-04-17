import type { UiLanguage } from '../i18n';

export interface AnalysisModelOption {
  value: string;
  label: string;
  description: string;
}

export function getAnalysisModelOptions(language: UiLanguage): readonly AnalysisModelOption[] {
  if (language === 'en') {
    return [
      {
        value: '',
        label: 'Service default',
        description: 'Uses the model currently configured in the realtime analysis service.',
      },
      {
        value: 'llama-3.3-70b-versatile',
        label: 'Llama 3.3 70B',
        description: 'A stronger balance between response speed and clinical analysis quality.',
      },
      {
        value: 'openai/gpt-oss-20b',
        label: 'GPT OSS 20B',
        description: 'A fast open-weight model for structured clinical reasoning.',
      },
      {
        value: 'openai/gpt-oss-120b',
        label: 'GPT OSS 120B',
        description: 'The deepest model in the list for more complex reasoning-heavy analysis.',
      },
    ] as const;
  }

  return [
    {
      value: '',
      label: 'Системная модель',
      description: 'Использует модель, которая сейчас настроена в сервисе realtime analysis.',
    },
    {
      value: 'llama-3.3-70b-versatile',
      label: 'Llama 3.3 70B',
      description: 'Более сильный баланс между скоростью и качеством клинического анализа.',
    },
    {
      value: 'openai/gpt-oss-20b',
      label: 'GPT OSS 20B',
      description: 'Быстрая open-weight модель для структурированного клинического разбора.',
    },
    {
      value: 'openai/gpt-oss-120b',
      label: 'GPT OSS 120B',
      description: 'Самая глубокая модель из списка для более сложного reasoning-анализа.',
    },
  ] as const;
}
