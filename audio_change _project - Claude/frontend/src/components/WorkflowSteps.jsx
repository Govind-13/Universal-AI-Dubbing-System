function WorkflowSteps({ steps, status, hasFile, hasResult }) {
  const getStepState = (stepId) => {
    if (hasResult) {
      return 'complete'
    }

    if (status === 'uploading') {
      if (stepId === 'upload' || stepId === 'configure' || stepId === 'process') {
        return stepId === 'process' ? 'current' : 'complete'
      }
    }

    if (hasFile) {
      if (stepId === 'upload') return 'complete'
      if (stepId === 'configure') return 'current'
    }

    return stepId === 'upload' ? 'current' : 'upcoming'
  }

  return (
    <ol className="space-y-4">
      {steps.map((step, index) => {
        const state = getStepState(step.id)

        return (
          <li key={step.id} className={`workflow-step workflow-step-${state}`}>
            <div className="workflow-step-marker">
              <span>{index + 1}</span>
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-3">
                <p className="text-sm font-semibold text-white">{step.label}</p>
                <span className="workflow-step-state">
                  {state === 'complete' ? 'Done' : state === 'current' ? 'Active' : 'Next'}
                </span>
              </div>
              <p className="mt-2 text-sm leading-6 text-slate-300">{step.description}</p>
            </div>
          </li>
        )
      })}
    </ol>
  )
}

export default WorkflowSteps
