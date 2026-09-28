import { useEffect, useMemo } from 'react'
import { Check, Clapperboard, Play } from 'lucide-react'

import StepIndicator from './StepIndicator'

function fullStages(languageName, enableLipSync) {
  return [
    { label: 'Pull out the audio', detail: 'Audio taken from the lesson video', statuses: ['Queued', 'Extracting source audio'] },
    { label: 'Separate the music', detail: 'Speech and background music split so the music can stay', statuses: ['Separating background music'] },
    { label: 'Transcribe', detail: 'ElevenLabs speech-to-text, Whisper as backup', statuses: ['Creating same-language transcript'] },
    { label: 'Translate', detail: `Classroom ${languageName} · maths made speakable, glossary terms protected`, statuses: ['Translating transcript'] },
    { label: 'Second read', detail: 'Checks the translation before it is voiced', statuses: ['Verifying translated transcript'] },
    { label: 'Record the new voice', detail: 'Each line timed to the original speaker', statuses: ['Generating ElevenLabs audio'] },
    { label: 'Mix in the music', detail: 'Original music laid back under the new voice', statuses: ['Mixing background music with narration'] },
    { label: 'Fit the subtitles', detail: 'Subtitles built from the same lines', statuses: ['Preparing subtitles'] },
    {
      label: enableLipSync ? 'Merge & lip-sync' : 'Merge the video',
      detail: enableLipSync ? 'New audio merged, then faces lip-synced (slow)' : 'New audio merged into the video',
      statuses: ['Replacing video audio'],
    },
  ]
}

const lipsyncStages = [
  { label: 'Get the audio', detail: 'From your dub track or the video itself', statuses: ['Queued', 'Using uploaded audio track', 'Extracting existing audio track'] },
  { label: 'Lip-sync faces', detail: 'Wav2Lip matches mouths to the audio — this is slow', statuses: ['Running lip-sync'] },
]

function StageRow({ stage, state }) {
  if (state === 'current') {
    return (
      <li aria-current="step" className="-mx-3 my-1 flex items-center gap-3.5 rounded-[10px] bg-accent-row px-3 py-2.5">
        <span className="spinner" aria-hidden="true" />
        <div className="flex flex-grow flex-col gap-px">
          <span className="text-[15px] font-semibold text-accent-ink">{stage.label}</span>
          <span className="text-[13px] text-[#4F4A63]">{stage.detail}</span>
        </div>
        <span className="text-[13px] font-semibold text-accent-ink">Working</span>
      </li>
    )
  }
  return (
    <li className="flex items-center gap-3.5 py-[9px]">
      {state === 'done' ? (
        <span className="flex h-7 w-7 flex-none items-center justify-center rounded-full bg-ok-soft text-ok">
          <Check className="h-3.5 w-3.5" strokeWidth={2.6} />
        </span>
      ) : (
        <span className="h-7 w-7 flex-none rounded-full border-[1.5px] border-[#D6D1E0]" />
      )}
      <div className="flex flex-grow flex-col gap-px">
        <span className={`text-[15px] ${state === 'done' ? 'font-semibold' : 'font-medium text-ink-2'}`}>{stage.label}</span>
        <span className="text-[13px] text-muted">{stage.detail}</span>
      </div>
      {state === 'done' ? <span className="text-[13px] font-semibold text-ok">Done</span> : null}
    </li>
  )
}

function ProcessingScreen({ file, jobStatus, progress, pipelineMode, languageName, voiceLabel, enableLipSync, onStepClick, canOpenStep }) {
  const previewUrl = useMemo(() => (file ? URL.createObjectURL(file) : null), [file])
  const stages = useMemo(
    () => (pipelineMode === 'lipsync_only' ? lipsyncStages : fullStages(languageName, enableLipSync)),
    [pipelineMode, languageName, enableLipSync]
  )
  const currentIndex = Math.max(0, stages.findIndex((stage) => stage.statuses.includes(jobStatus)))
  const current = stages[currentIndex]

  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl)
  }, [previewUrl])

  return (
    <main className="flex min-w-0 flex-grow flex-col gap-[22px] px-6 pb-7 pt-9 sm:px-11">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-2.5">
          <span className="kicker">Dubbing in progress</span>
          <h1 className="display-title">{pipelineMode === 'lipsync_only' ? 'Matching the faces.' : 'Finding the right words.'}</h1>
          <p className="m-0 text-base text-muted">Keep this page and the backend open. Nothing is final until you export.</p>
        </div>
        {file ? (
          <div className="flex items-center gap-3 rounded-xl border border-line bg-white px-3.5 py-2.5">
            <div className="flex h-9 w-14 items-center justify-center rounded-md bg-[#1E1A2E]">
              <Play className="h-3.5 w-3.5 fill-white text-white" />
            </div>
            <div className="flex min-w-0 flex-col gap-0.5">
              <span className="max-w-[260px] truncate text-sm font-semibold">{file.name}</span>
              <span className="text-[13px] text-muted">
                {pipelineMode === 'lipsync_only' ? 'Lip-sync only' : `To ${languageName} · ${voiceLabel}`}
              </span>
            </div>
          </div>
        ) : null}
      </div>

      <StepIndicator current="processing" onStepClick={onStepClick} canOpen={canOpenStep} />

      <div className="grid flex-grow gap-6 xl:grid-cols-2">
        <section className="card">
          <div className="flex flex-col gap-3 border-b border-divider px-6 pb-[18px] pt-[22px]">
            <div className="flex items-baseline justify-between">
              <span className="text-base font-semibold">{current.label}</span>
              <span className="font-display text-[26px] font-semibold text-accent-ink">{progress}%</span>
            </div>
            <div
              role="progressbar"
              aria-label="Overall progress"
              aria-valuenow={progress}
              aria-valuemin={0}
              aria-valuemax={100}
              className="h-2 overflow-hidden rounded bg-[#EEEBF6]"
            >
              <div className="h-2 rounded bg-accent transition-[width] duration-500" style={{ width: `${progress}%` }} />
            </div>
            <span className="text-[13px] text-muted">
              Step {currentIndex + 1} of {stages.length} · keep the backend running until it finishes
            </span>
          </div>
          <ol className="m-0 flex list-none flex-col px-6 pb-4 pt-2.5">
            {stages.map((stage, index) => (
              <StageRow
                key={stage.label}
                stage={stage}
                state={index < currentIndex ? 'done' : index === currentIndex ? 'current' : 'upcoming'}
              />
            ))}
          </ol>
        </section>

        <section className="card">
          <div className="card-head">
            <div className="card-title">
              <Clapperboard className="h-[18px] w-[18px] text-ink-2" strokeWidth={1.8} />
              Your video
            </div>
            <span className="flex items-center gap-2 text-[13px] font-semibold text-accent-ink">
              <span className="h-2 w-2 rounded-full bg-accent" />
              {jobStatus || 'Queued'}
            </span>
          </div>
          <div className="bg-[#16131F]">
            {previewUrl ? <video src={previewUrl} controls muted className="block aspect-video w-full object-contain" /> : null}
          </div>
          <dl className="m-0 grid grid-cols-2 gap-x-6 gap-y-4 p-5 text-sm">
            <div>
              <dt className="text-[13px] text-muted">Mode</dt>
              <dd className="m-0 mt-0.5 font-semibold">{pipelineMode === 'lipsync_only' ? 'Lip-sync only' : 'Full translation'}</dd>
            </div>
            {pipelineMode === 'full' ? (
              <>
                <div>
                  <dt className="text-[13px] text-muted">Translating to</dt>
                  <dd className="m-0 mt-0.5 font-semibold">{languageName}</dd>
                </div>
                <div>
                  <dt className="text-[13px] text-muted">Voice</dt>
                  <dd className="m-0 mt-0.5 font-semibold">{voiceLabel}</dd>
                </div>
                <div>
                  <dt className="text-[13px] text-muted">Lip-sync</dt>
                  <dd className="m-0 mt-0.5 font-semibold">{enableLipSync ? 'On · real faces' : 'Off · skipped'}</dd>
                </div>
              </>
            ) : null}
          </dl>
          <div className="mt-auto border-t border-divider px-5 py-3.5 text-[13px] text-muted">
            The translated lines appear on the next screen, where you can edit any of them and re-render.
          </div>
        </section>
      </div>
    </main>
  )
}

export default ProcessingScreen
