/* Export the mock or real API implementation based on `VITE_USE_MOCK`. */

import type { SessionApi } from '../types/types';
import { mockSessionApi } from './mockSessionApi';
import { sessionApi } from './sessionApi';

const useMock = import.meta.env.VITE_USE_MOCK === 'true';

export const api: SessionApi = useMock ? mockSessionApi : sessionApi;
