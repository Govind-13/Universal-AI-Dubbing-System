import { Activity, CheckCircle2, LoaderCircle, Sparkles } from 'lucide-react'

function ProgressPanel({ uploading, status, progress, stages, selectedLanguage, hasFile, hasResult }) {
  const stateLabel =
    status === 'done'
      ? 'Complete'
      : status === 'error'
        ? 'Attention needed'
        : uploading
          ? 'Processing'
          : hasFile
            ? 'Ready to start'
            : 'Waiting for input'

  return (
    <aside className="surface-panel section-panel progress-shell">
      <div className="section-heading">
        <div>
          <p className="section-kicker">Status</p>
          <h3 className="section-title">Job progress</h3>
        </div>
        <span className={`section-chip ${status === 'done' ? 'section-chip-success' : ''}`}>{stateLabel}</span>
      </div>

      <div className="mt-8 space-y-6">
        <div className="subtle-card">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-sm font-medium text-slate-300">Pipeline overview</p>
              <h4 className="mt-2 text-xl font-semibold text-white">
                {hasResult ? 'Classroom package ready' : uploading ? 'Classroom dubbing in progress' : 'Ready for a new run'}
              </h4>
            </div>
            <div className="icon-badge">
              {uploading ? <LoaderCircle className="h-5 w-5 animate-spin" /> : <Activity className="h-5 w-5" />}
            </div>
          </div>

          <div className="mt-6">
            <div className="flex items-center justify-between text-sm text-slate-300">
              <span>Overall progress</span>
              <span className="font-semibold text-white">{hasResult ? 100 : progress}%</span>
            </div>
            <div className="progress-track mt-3">
              <div className="progress-fill" style={{ width: `${hasResult ? 100 : progress}%` }} />
            </div>
          </div>

          <p className="mt-4 text-sm leading-6 text-slate-300">
            Target classroom style: <span className="font-semibold text-white">{selectedLanguage}</span>
          </p>
        </div>

        <div className="subtle-card">
          <div className="flex items-center gap-3">
            <div className="icon-badge">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <h4 className="text-base font-semibold text-white">Stage tracker</h4>
              <p className="text-sm text-slate-300">Visibility into transcript, code-mix, voice, and export stages.</p>
            </div>
          </div>

          <ol className="mt-6 space-y-4">
            {stages.map((stage) => (
              <li key={stage.key} className={`stage-row stage-row-${stage.state}`}>
                <div className="stage-icon">
                  {stage.state === 'complete' ? (
                    <CheckCircle2 className="h-4 w-4" />
                  ) : stage.state === 'current' ? (
                    <LoaderCircle className="h-4 w-4 animate-spin" />
                  ) : (
                    <span className="block h-2.5 w-2.5 rounded-full bg-slate-500/70" />
                  )}
                </div>
                <div className="min-w-0">
                  <div className="flex items-center justify-between gap-4">
                    <p className="text-sm font-semibold text-white">{stage.label}</p>
                    <span className="text-xs uppercase tracking-[0.2em] text-slate-400">
                      {stage.state === 'complete' ? 'Done' : stage.state === 'current' ? 'Running' : 'Queued'}
                    </span>
                  </div>
                  <p className="mt-1 text-sm leading-6 text-slate-300">{stage.detail}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>

        <div className="subtle-card">
          <h4 className="text-base font-semibold text-white">Status guidance</h4>
          <p className="mt-3 text-sm leading-7 text-slate-300">
            {!hasFile
              ? 'Start by choosing a source video in the upload panel.'
              : hasResult
                ? 'Review the finished output below, inspect text assets, and download the final deliverables.'
                : uploading
                  ? 'Keep this page open while transcript cleanup, classroom code-mix, voice, and export complete.'
                  : 'Everything is configured. Start classroom dubbing when you are ready.'}
          </p>
        </div>
      </div>
    </aside>
  )
}

export default ProgressPanel
