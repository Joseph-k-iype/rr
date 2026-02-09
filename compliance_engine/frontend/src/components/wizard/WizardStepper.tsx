const steps = [
  'Country', 'Scenario', 'Rule', 'Analysis', 'Dictionary',
  'Review', 'Edit', 'Sandbox', 'Test', 'Approve',
];

export function WizardStepper({ currentStep }: { currentStep: number }) {
  return (
    <div className="flex items-center gap-0 mb-6">
      {steps.map((label, i) => {
        const stepNum = i + 1;
        const isActive = stepNum === currentStep;
        const isDone = stepNum < currentStep;
        return (
          <div key={i} className="flex items-center">
            <div className={`flex items-center gap-1 px-2.5 py-1 text-[11px] tracking-wide ${
              isActive ? 'text-gray-900 font-medium' :
              isDone ? 'text-gray-400' :
              'text-gray-300'
            }`}>
              <span className={`w-4 h-4 flex items-center justify-center rounded-full text-[9px] font-medium ${
                isActive ? 'bg-gray-900 text-white' :
                isDone ? 'bg-gray-200 text-gray-500' :
                'bg-gray-100 text-gray-400'
              }`}>{stepNum}</span>
              <span className="hidden sm:inline">{label}</span>
            </div>
            {i < steps.length - 1 && (
              <div className={`w-3 h-px ${isDone ? 'bg-gray-300' : 'bg-gray-100'}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}
