import { EvaluatorForm } from '../components/evaluator/EvaluatorForm';
import { EvaluationResult } from '../components/evaluator/EvaluationResult';

export function EvaluatorPage() {
  return (
    <div>
      <h1 className="text-3xl font-bold text-gray-900 mb-6">Policy Evaluator</h1>
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        <div className="lg:col-span-3">
          <EvaluatorForm />
        </div>
        <div className="lg:col-span-2">
          <EvaluationResult />
        </div>
      </div>
    </div>
  );
}
