import { EvaluatorForm } from '../components/evaluator/EvaluatorForm';
import { EvaluationResult } from '../components/evaluator/EvaluationResult';

export function EvaluatorPage() {
  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-4">Rule Evaluator</h1>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <EvaluatorForm />
        <EvaluationResult />
      </div>
    </div>
  );
}
