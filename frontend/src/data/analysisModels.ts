export interface AnalysisModelOption {
  value: string;
  label: string;
  description: string;
}

export const ANALYSIS_MODEL_OPTIONS: readonly AnalysisModelOption[] = [
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
];
