export interface WizardSession {
  session_id: string;
  status: string;
  current_step: number;
  origin_country?: string;
  receiving_countries: string[];
  scenario_type?: string;
  data_categories: string[];
  rule_text?: string;
  analysis_result?: Record<string, unknown>;
  dictionary_result?: Record<string, unknown>;
  edited_rule_definition?: Record<string, unknown>;
  edited_terms_dictionary?: Record<string, unknown>;
  sandbox_graph_name?: string;
  sandbox_test_results: Record<string, unknown>[];
  approved: boolean;
  error_message?: string;
  created_at: string;
  updated_at: string;
}

export interface WizardStepData {
  step: number;
  data: Record<string, unknown>;
}
