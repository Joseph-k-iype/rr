import { create } from 'zustand';

interface WizardState {
  sessionId: string | null;
  currentStep: number;
  originCountry: string;
  receivingCountries: string[];
  scenarioType: string;
  dataCategories: string[];
  ruleText: string;
  isPiiRelated: boolean;
  analysisResult: Record<string, unknown> | null;
  dictionaryResult: Record<string, unknown> | null;
  editedRuleDefinition: Record<string, unknown> | null;
  editedTermsDictionary: Record<string, unknown> | null;
  sandboxGraphName: string | null;
  sandboxTestResults: Record<string, unknown>[];
  approved: boolean;
  isProcessing: boolean;
  error: string | null;

  setSessionId: (id: string) => void;
  setStep: (step: number) => void;
  setOriginCountry: (c: string) => void;
  setReceivingCountries: (c: string[]) => void;
  setScenarioType: (t: string) => void;
  setDataCategories: (c: string[]) => void;
  setRuleText: (t: string) => void;
  setIsPiiRelated: (p: boolean) => void;
  setAnalysisResult: (r: Record<string, unknown>) => void;
  setDictionaryResult: (r: Record<string, unknown>) => void;
  setEditedRuleDefinition: (r: Record<string, unknown>) => void;
  setEditedTermsDictionary: (r: Record<string, unknown>) => void;
  setSandboxGraphName: (n: string | null) => void;
  addSandboxTestResult: (r: Record<string, unknown>) => void;
  setApproved: (a: boolean) => void;
  setProcessing: (p: boolean) => void;
  setError: (e: string | null) => void;
  reset: () => void;
}

const initialState = {
  sessionId: null,
  currentStep: 1,
  originCountry: '',
  receivingCountries: [],
  scenarioType: 'transfer',
  dataCategories: [],
  ruleText: '',
  isPiiRelated: false,
  analysisResult: null,
  dictionaryResult: null,
  editedRuleDefinition: null,
  editedTermsDictionary: null,
  sandboxGraphName: null,
  sandboxTestResults: [],
  approved: false,
  isProcessing: false,
  error: null,
};

export const useWizardStore = create<WizardState>((set) => ({
  ...initialState,

  setSessionId: (id) => set({ sessionId: id }),
  setStep: (step) => set({ currentStep: step }),
  setOriginCountry: (c) => set({ originCountry: c }),
  setReceivingCountries: (c) => set({ receivingCountries: c }),
  setScenarioType: (t) => set({ scenarioType: t }),
  setDataCategories: (c) => set({ dataCategories: c }),
  setRuleText: (t) => set({ ruleText: t }),
  setIsPiiRelated: (p) => set({ isPiiRelated: p }),
  setAnalysisResult: (r) => set({ analysisResult: r }),
  setDictionaryResult: (r) => set({ dictionaryResult: r }),
  setEditedRuleDefinition: (r) => set({ editedRuleDefinition: r }),
  setEditedTermsDictionary: (r) => set({ editedTermsDictionary: r }),
  setSandboxGraphName: (n) => set({ sandboxGraphName: n }),
  addSandboxTestResult: (r) => set((s) => ({ sandboxTestResults: [...s.sandboxTestResults, r] })),
  setApproved: (a) => set({ approved: a }),
  setProcessing: (p) => set({ isProcessing: p }),
  setError: (e) => set({ error: e }),
  reset: () => set(initialState),
}));
