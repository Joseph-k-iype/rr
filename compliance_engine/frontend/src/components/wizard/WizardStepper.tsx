const steps = [
  'Country', 'Scenario', 'Rule Text', 'AI Analysis', 'AI Dictionary',
  'Review', 'Edit', 'Sandbox', 'Test', 'Approve',
];

export function WizardStepper({ currentStep }: { currentStep: number }) {
  return (
    <div className="flex items-center gap-1 mb-6 overflow-x-auto pb-2">
      {steps.map((label, i) => {
        const stepNum = i + 1;
        const isActive = stepNum === currentStep;
        const isDone = stepNum < currentStep;
        return (
          <div key={i} className="flex items-center">
            <div className={`flex items-center gap-1.5 px-2 py-1 rounded-full text-xs whitespace-nowrap ${
              isActive ? 'bg-blue-600 text-white' :
              isDone ? 'bg-green-100 text-green-700' :
              'bg-gray-100 text-gray-500'
            }`}>
              <span className="font-bold">{stepNum}</span>
              <span>{label}</span>
            </div>
            {i < steps.length - 1 && (
              <div className={`w-4 h-0.5 mx-0.5 ${isDone ? 'bg-green-300' : 'bg-gray-200'}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}
