import { create } from 'zustand';
import type { RulesEvaluationResponse } from '../types/api';

interface EvaluationState {
  result: RulesEvaluationResponse | null;
  isLoading: boolean;
  error: string | null;

  setResult: (r: RulesEvaluationResponse) => void;
  setLoading: (l: boolean) => void;
  setError: (e: string | null) => void;
  clear: () => void;
}

export const useEvaluationStore = create<EvaluationState>((set) => ({
  result: null,
  isLoading: false,
  error: null,

  setResult: (r) => set({ result: r, isLoading: false, error: null }),
  setLoading: (l) => set({ isLoading: l }),
  setError: (e) => set({ error: e, isLoading: false }),
  clear: () => set({ result: null, error: null, isLoading: false }),
}));
