import { useMemo, useState } from 'react'
import axios from 'axios'
import { AlertCircle, AudioLines, Check, Download, Headphones, Music, RefreshCw } from 'lucide-react'

import StepIndicator from './StepIndicator'
import { API_BASE, formatTime, modelName, voiceName } from '../constants'

function Badge({ tone, icon, children }) {
  const Icon = icon
  const tones = {
    ok: 'bg-ok-soft text-ok-ink',
    warn: 'bg-warn-soft text-warn-ink',
  }
  return (
    <span className={`badge ${tones[tone]}`}>
      <Icon className="h-3.5 w-3.5" strokeWidth={2.2} />
      {children}
    </span>
  )
}

function statusBadges(result) {
  const badges = []
  if (result.mode !== 'lipsync_only') {
    if (result.bgm?.state === 'mixed') badges.push({ tone: 'ok', icon: Music, text: 'Background music kept' })
    else badges.push({ tone: 'warn', icon: AlertCircle, text: 'Background music not separated' })
    badges.push({ tone: 'ok', icon: Check, text: 'Voice matched to timestamps' })
  }
  const lipState = result.lip_sync_status ?? result.lip_sync?.state
  const lipText = {
    completed: ['ok', Check, 'Lip-sync applied'],
    skipped: ['warn', AlertCircle, 'Lip-sync skipped · cartoon or non-human character'],
    skipped_no_face: ['warn', AlertCircle, 'Lip-sync skipped · no face found'],
    not_configured: ['warn', AlertCircle, 'Lip-sync skipped · Wav2Lip not set up'],
    failed: ['warn', AlertCircle, 'Lip-sync failed · dubbed without it'],
  }[lipState]
  if (lipText) badges.push({ tone: lipText[0], icon: lipText[1], text: lipText[2] })
  if (result.text_pipeline?.stage_status?.translation_review_fallback_used) {
    badges.push({ tone: 'warn', icon: AlertCircle, text: 'Check the translation · review used a fallback' })
  }
  return badges
}

function Slider({ label, value, min, max, onChange }) {
  return (
    <label className="flex flex-col gap-1 text-[13px] font-medium text-ink-2">
      <span className="flex justify-between">
        {label}
        <span className="font-semibold text-ink">{value.toFixed(2)}</span>
      </span>
      <input type="range" min={min} max={max} step="0.01" value={value} onChange={(event) => onChange(Number(event.target.value))} className="m-0" />
    </label>
  )
}

function DownloadLink({ href, label, primary }) {
  return (
    <a href={`${API_BASE}${href}`} download className={primary ? 'btn-primary' : 'btn-secondary'}>
      <Download className="h-4 w-4" strokeWidth={2} />
      {label}
    </a>
  )
}

function ReviewScreen({ result, onRerender, onStepClick, canOpenStep }) {
  const isLipsyncOnly = result.mode === 'lipsync_only'
  const segments = useMemo(() => result.translation?.segments ?? [], [result.translation?.segments])
  const originalSegments = result.transcription?.segments ?? []
  const hasOriginals = originalSegments.length === segments.length

  const settings = result.tts?.settings ?? {}
  const [drafts, setDrafts] = useState(() => segments.map((segment) => ({ ...segment })))
  const [voice, setVoice] = useState({
    speed: settings.speed ?? 0.9,
    stability: settings.stability ?? 0.75,
    similarity_boost: settings.similarity_boost ?? 0.64,
    style: settings.style ?? 0,
    use_speaker_boost: settings.use_speaker_boost ?? true,
  })
  const [editTiming, setEditTiming] = useState(false)
  const [tab, setTab] = useState('lines')
  const [rerendering, setRerendering] = useState(false)
  const [rerenderError, setRerenderError] = useState('')

  const isEdited = (draft, index) =>
    draft.text !== segments[index]?.text || draft.start !== segments[index]?.start || draft.end !== segments[index]?.end
  const editedCount = drafts.filter(isEdited).length

  const updateDraft = (index, field, value) => {
    setDrafts((previous) =>
      previous.map((draft, i) => (i === index ? { ...draft, [field]: field === 'text' ? value : parseFloat(value) || 0 } : draft))
    )
  }

  const handleRerender = async () => {
    setRerendering(true)
    setRerenderError('')
    try {
      const response = await axios.post(`${API_BASE}/rerender`, {
        video_filename: result.filename,
        target_language: result.translation.target_language,
        segments: drafts.map(({ start, end, text }) => ({ start, end, text })),
        tts_voice_id: result.tts?.voice_id ?? 'default',
        tts_model_id: settings.model_id ?? 'eleven_multilingual_v2',
        tts_speed: voice.speed,
        tts_stability: voice.stability,
        tts_similarity_boost: voice.similarity_boost,
        tts_style: voice.style,
        tts_speaker_boost: voice.use_speaker_boost,
        enable_lip_sync: result.lip_sync_status !== 'skipped',
      })
      onRerender(response.data)
    } catch (error) {
      setRerenderError(error?.response?.data?.detail || 'Re-render failed. Please try again.')
    } finally {
      setRerendering(false)
    }
  }

  const badges = statusBadges(result)

  return (
    <main className="flex min-w-0 flex-grow flex-col gap-[22px] px-6 pb-7 pt-9 sm:px-11">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-2.5">
          <span className="kicker text-ok">Ready to review</span>
          <h1 className="display-title">{isLipsyncOnly ? 'Watch and export.' : 'Listen, tweak, export.'}</h1>
          <p className="m-0 text-base text-muted">
            {isLipsyncOnly
              ? result.message ?? 'Lip-sync is done.'
              : 'Change any line or the voice, then re-render — no need to transcribe again.'}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          {result.subtitle_url ? <DownloadLink href={result.subtitle_url} label="Subtitles .srt" /> : null}
          {result.translation?.json_url ? <DownloadLink href={result.translation.json_url} label="Transcript .json" /> : null}
          {result.transcription?.json_url ? <DownloadLink href={result.transcription.json_url} label="Original .json" /> : null}
          <DownloadLink href={result.video_url} label="Download video" primary />
        </div>
      </div>

      <StepIndicator current="review" onStepClick={onStepClick} canOpen={canOpenStep} />

      <div className={`grid flex-grow gap-6 ${isLipsyncOnly ? '' : 'xl:grid-cols-[minmax(0,1.12fr)_minmax(0,1fr)]'}`}>
        <div className="flex flex-col gap-4">
          <section aria-label="Dubbed video" className="overflow-hidden rounded-2xl bg-[#16131F]">
            <video key={result.video_url} src={`${API_BASE}${result.video_url}`} controls className="block aspect-video w-full bg-[#1E1A2E] object-contain" />
          </section>

          {badges.length ? (
            <div className="flex flex-wrap gap-2">
              {badges.map((badge) => (
                <Badge key={badge.text} tone={badge.tone} icon={badge.icon}>{badge.text}</Badge>
              ))}
            </div>
          ) : null}

          {!isLipsyncOnly ? (
            <section className="flex flex-grow flex-col gap-3.5 rounded-2xl border border-line bg-white px-5 py-[18px]">
              <div className="card-title">
                <Headphones className="h-[18px] w-[18px] text-ink-2" strokeWidth={1.8} />
                Voice · {voiceName(result.tts?.voice_id)}, {modelName(settings.model_id)}
              </div>
              <div className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
                <Slider label="Speed" value={voice.speed} min="0.7" max="1.2" onChange={(speed) => setVoice((v) => ({ ...v, speed }))} />
                <Slider label="Stability" value={voice.stability} min="0" max="1" onChange={(stability) => setVoice((v) => ({ ...v, stability }))} />
                <Slider label="Likeness to voice" value={voice.similarity_boost} min="0" max="1" onChange={(similarity_boost) => setVoice((v) => ({ ...v, similarity_boost }))} />
                <Slider label="Expressiveness" value={voice.style} min="0" max="1" onChange={(style) => setVoice((v) => ({ ...v, style }))} />
              </div>
              <div className="flex items-center justify-between border-t border-divider pt-3">
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    role="switch"
                    aria-checked={voice.use_speaker_boost}
                    aria-label="Speaker boost"
                    onClick={() => setVoice((v) => ({ ...v, use_speaker_boost: !v.use_speaker_boost }))}
                    className="switch"
                  >
                    <span />
                  </button>
                  <span className="text-sm font-medium">Speaker boost</span>
                </div>
                <span className="text-[13px] text-muted">Applies on the next re-render</span>
              </div>
            </section>
          ) : null}
        </div>

        {!isLipsyncOnly ? (
          <section className="card max-h-[calc(100vh-120px)] min-h-[520px]">
            <div className="card-head">
              <div role="tablist" aria-label="Transcript view" className="flex h-full gap-6">
                {[
                  ['lines', 'Lines'],
                  ['subtitles', 'Subtitles'],
                ].map(([key, label]) => (
                  <button
                    key={key}
                    type="button"
                    role="tab"
                    aria-selected={tab === key}
                    onClick={() => setTab(key)}
                    className={`flex h-full items-center gap-2 border-0 border-b-2 bg-transparent px-0 text-[15px] ${
                      tab === key ? 'border-accent font-semibold text-accent-ink' : 'border-transparent font-medium text-muted'
                    }`}
                  >
                    {key === 'lines' ? <AudioLines className="h-4 w-4" strokeWidth={2} /> : null}
                    {label}
                  </button>
                ))}
              </div>
              <span className="text-[13px] text-muted">
                {segments.length} lines
                {editedCount ? <> · <span className="font-semibold text-accent-ink">{editedCount} edited</span></> : null}
              </span>
            </div>

            {tab === 'lines' ? (
              <>
                <div className="flex items-center justify-end border-b border-divider px-5 py-2">
                  <button
                    type="button"
                    onClick={() => setEditTiming((on) => !on)}
                    aria-pressed={editTiming}
                    className="border-0 bg-transparent p-0 text-[13px] font-semibold text-accent-ink"
                  >
                    {editTiming ? 'Hide timing' : 'Edit timing'}
                  </button>
                </div>
                <div className="flex-grow overflow-y-auto">
                  {drafts.map((draft, index) => {
                    const edited = isEdited(draft, index)
                    return (
                      <div key={index} className={`flex flex-col gap-2 border-b border-[#F1EEF4] px-5 py-3.5 ${edited ? 'bg-[#FBFAFF]' : ''}`}>
                        <div className="flex items-center justify-between gap-3">
                          {editTiming ? (
                            <div className="flex items-center gap-2 text-[13px] text-muted">
                              <input
                                type="number"
                                step="0.01"
                                min="0"
                                aria-label={`Line ${index + 1} start (seconds)`}
                                value={draft.start}
                                onChange={(event) => updateDraft(index, 'start', event.target.value)}
                                className="field-control h-8 w-24 px-2 text-[13px]"
                              />
                              to
                              <input
                                type="number"
                                step="0.01"
                                min="0"
                                aria-label={`Line ${index + 1} end (seconds)`}
                                value={draft.end}
                                onChange={(event) => updateDraft(index, 'end', event.target.value)}
                                className="field-control h-8 w-24 px-2 text-[13px]"
                              />
                            </div>
                          ) : (
                            <span className="text-[13px] font-semibold text-muted">
                              {formatTime(draft.start)} – {formatTime(draft.end)}
                            </span>
                          )}
                          {edited ? (
                            <span className="flex items-center gap-1.5 text-xs font-semibold text-accent-ink">
                              <span className="h-1.5 w-1.5 rounded-full bg-accent" />
                              Edited
                            </span>
                          ) : null}
                        </div>
                        {hasOriginals ? <span className="text-sm text-muted">{originalSegments[index]?.text}</span> : null}
                        <textarea
                          aria-label={`Translation, line ${index + 1}`}
                          rows={Math.min(8, Math.max(2, Math.ceil((draft.text?.length ?? 0) / 55)))}
                          value={draft.text}
                          onChange={(event) => updateDraft(index, 'text', event.target.value)}
                          className={`w-full resize-y rounded-lg bg-white px-3 py-2.5 text-[15px] leading-snug text-ink outline-none focus:ring-2 focus:ring-accent/20 ${
                            edited ? 'border-[1.5px] border-accent' : 'border border-line'
                          }`}
                        />
                      </div>
                    )
                  })}
                </div>
              </>
            ) : (
              <pre className="m-0 flex-grow overflow-auto whitespace-pre-wrap px-5 py-4 text-sm leading-7 text-ink-2">
                {result.subtitle?.content || 'No subtitles available.'}
              </pre>
            )}

            <div className="flex flex-col gap-2 border-t border-divider px-5 py-3.5">
              {rerenderError ? <p role="alert" className="m-0 text-sm text-[#8E2B20]">{rerenderError}</p> : null}
              <div className="flex items-center justify-between gap-4">
                <span className="text-[13px] text-muted">Re-render redoes subtitles, voice and mix only.</span>
                <button type="button" onClick={handleRerender} disabled={rerendering} className="btn-soft">
                  <RefreshCw className={`h-4 w-4 ${rerendering ? 'animate-spin' : ''}`} strokeWidth={2} />
                  {rerendering ? 'Re-rendering…' : 'Re-render with edits'}
                </button>
              </div>
            </div>
          </section>
        ) : null}
      </div>
    </main>
  )
}

export default ReviewScreen
