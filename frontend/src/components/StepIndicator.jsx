import { Check } from 'lucide-react'

const steps = [
  { key: 'setup', label: 'Add your video' },
  { key: 'processing', label: 'Dub & sync' },
  { key: 'review', label: 'Review & export' },
]

function StepIndicator({ current, onStepClick, canOpen }) {
  const currentIndex = steps.findIndex((step) => step.key === current)

  return (
    <ol aria-label="Progress" className="m-0 flex list-none flex-wrap items-center gap-4 p-0">
      {steps.map((step, index) => {
        const done = index < currentIndex
        const active = index === currentIndex
        const clickable = !active && canOpen(step.key)
        const label = clickable ? (
          <button type="button" onClick={() => onStepClick(step.key)} className="border-0 bg-transparent p-0 text-[15px] text-inherit hover:text-accent-ink">
            {step.label}
          </button>
        ) : (
          step.label
        )

        return (
          <li key={step.key} className="contents">
            {index > 0 ? (
              <span aria-hidden="true" className={`h-px w-14 ${index <= currentIndex ? 'bg-[#B8ABEE]' : 'bg-[#D6D1E0]'}`} />
            ) : null}
            <span
              aria-current={active ? 'step' : undefined}
              className={`flex items-center gap-2.5 text-[15px] ${active ? 'font-semibold text-ink' : done ? 'text-ink-2' : 'text-muted'}`}
            >
              {done ? (
                <span className="flex h-[26px] w-[26px] items-center justify-center rounded-full bg-accent-soft text-accent-ink">
                  <Check className="h-3.5 w-3.5" strokeWidth={2.6} />
                </span>
              ) : (
                <span
                  className={`flex h-[26px] w-[26px] items-center justify-center rounded-full text-[13px] ${
                    active ? 'bg-accent font-bold text-white' : 'border border-[#D6D1E0] bg-white font-semibold'
                  }`}
                >
                  {index + 1}
                </span>
              )}
              {label}
            </span>
          </li>
        )
      })}
    </ol>
  )
}

export default StepIndicator
