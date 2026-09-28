import { useState } from 'react'
import { ArrowRight, AudioLines, ChevronDown, Clapperboard, FileAudio, Globe, Sparkles } from 'lucide-react'

import StepIndicator from './StepIndicator'
import UploadZone from './UploadZone'
import { elevenLabsModels, elevenLabsVoices, languages } from '../constants'

function Switch({ checked, onChange, label, disabled }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className="switch"
    >
      <span />
    </button>
  )
}

function Slider({ label, value, min, max, onChange, disabled }) {
  return (
    <label className="flex flex-col gap-1 text-[13px] font-medium text-ink-2">
      <span className="flex justify-between">
        {label}
        <span className="font-semibold text-ink">{value.toFixed(2)}</span>
      </span>
      <input type="range" min={min} max={max} step="0.01" value={value} disabled={disabled} onChange={(event) => onChange(Number(event.target.value))} className="m-0" />
    </label>
  )
}

function TranscriptPreview() {
  return (
    <section className="card">
      <div className="flex h-[60px] items-center justify-between px-5">
        <div className="card-title">
          <AudioLines className="h-[18px] w-[18px] text-ink-2" strokeWidth={2} />
          Transcript
        </div>
        <span className="flex h-[26px] items-center rounded-md border border-line-strong px-2.5 text-xs font-semibold uppercase tracking-[0.08em] text-muted">Preview</span>
      </div>
      <div className="flex flex-grow flex-col items-center justify-center gap-3.5 border-t border-divider px-9 py-10 text-center">
        <div className="relative mb-2 h-[118px] w-[220px]" aria-hidden="true">
          <div className="absolute bottom-2.5 left-0 right-3.5 top-0 flex flex-col gap-3 rounded-xl border border-[#E7E2F4] bg-[#FBFAFF] px-[18px] py-4">
            {[
              ['0:03', 'w-[120px]'],
              ['0:07', 'w-[92px]'],
              ['0:12', 'w-[108px]'],
            ].map(([time, width]) => (
              <div key={time} className="flex items-center gap-2.5">
                <span className="text-[11px] font-semibold text-faint">{time}</span>
                <span className={`h-[5px] rounded-sm bg-accent-soft ${width}`} />
              </div>
            ))}
          </div>
          <div className="absolute bottom-0 right-0 flex h-9 w-9 items-center justify-center rounded-[10px] border border-[#DCD5F5] bg-white">
            <Sparkles className="h-[18px] w-[18px] text-accent" strokeWidth={1.8} />
          </div>
        </div>
        <div className="font-display text-[22px] font-semibold tracking-[-0.01em]">Your lesson, in their words.</div>
        <p className="m-0 max-w-[340px] text-sm leading-relaxed text-muted">
          The original and translated lines will sit side by side after dubbing — and you can fix any line before the final render.
        </p>
      </div>
      <div className="flex items-center gap-2.5 border-t border-divider px-5 py-3.5 text-[13px] text-muted">
        <span className="font-display text-base font-semibold text-accent">λ</span>
        Equations are spoken aloud: λ → “lambda”, x² → “x squared”.
      </div>
    </section>
  )
}

function DubAudioCard({ separateAudioFile, onSelect, disabled }) {
  return (
    <section className="card">
      <div className="card-head">
        <div className="card-title">
          <FileAudio className="h-[18px] w-[18px] text-ink-2" strokeWidth={1.8} />
          Dub audio
        </div>
        <span className="text-[13px] text-muted">Optional</span>
      </div>
      <div className="flex flex-grow flex-col gap-4 p-5">
        <p className="m-0 text-sm leading-relaxed text-muted">
          Add a separately dubbed audio track to lip-sync against. Leave it empty to use the video&apos;s own audio.
        </p>
        <label className="field">
          Audio file
          <input
            type="file"
            accept="audio/*"
            disabled={disabled}
            onChange={(event) => onSelect(event.target.files?.[0] ?? null)}
            className="field-control h-auto py-2.5 text-sm"
          />
        </label>
        {separateAudioFile ? <p className="m-0 text-sm text-ink-2">Selected: {separateAudioFile.name}</p> : null}
        <div className="mt-auto rounded-[10px] bg-paper px-3.5 py-3 text-[13px] leading-relaxed text-muted">
          Lip-sync only works on real human faces. Cartoon and 3D characters can&apos;t be detected.
        </div>
      </div>
    </section>
  )
}

function SetupScreen(props) {
  const {
    pipelineMode, onModeChange, file, onFileChange, uploading, errorMessage,
    separateAudioFile, onSeparateAudioChange,
    selectedLang, onLangChange, selectedVoice, onVoiceChange, ttsModel, onModelChange,
    ttsSpeed, onSpeedChange, ttsStability, onStabilityChange, ttsSimilarityBoost, onSimilarityChange,
    ttsStyle, onStyleChange, ttsSpeakerBoost, onSpeakerBoostChange, enableLipSync, onLipSyncChange,
    onStart, onStepClick, canOpenStep,
  } = props
  const [showTuning, setShowTuning] = useState(false)
  const isFull = pipelineMode === 'full'

  return (
    <main className="flex min-w-0 flex-grow flex-col gap-[22px] px-6 pb-7 pt-9 sm:px-11">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-2.5">
          <span className="kicker">{isFull ? 'Classroom dubbing' : 'Lip-sync only'}</span>
          <h1 className="display-title">{isFull ? 'Every lesson, in their language.' : 'Match lips to a new voice.'}</h1>
          <p className="m-0 text-base text-muted">
            {isFull
              ? 'Upload a lesson. We transcribe it, translate it into a classroom mix, and voice it back in sync.'
              : "Uses your video's own audio, or a dub track you add. No translation and no new voice."}
          </p>
        </div>
        <div className="flex h-9 items-center gap-2 rounded-[10px] border border-line bg-white px-3.5 text-sm text-ink-2">
          <Globe className="h-4 w-4 text-accent" strokeWidth={1.8} />
          {languages.length} classroom languages
        </div>
      </div>

      <StepIndicator current="setup" onStepClick={onStepClick} canOpen={canOpenStep} />

      <div className="grid flex-grow gap-6 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <section className="card">
          <div className="card-head">
            <div className="card-title">
              <Clapperboard className="h-[18px] w-[18px] text-ink-2" strokeWidth={1.8} />
              Your video
            </div>
            <div role="group" aria-label="Processing mode" className="segmented">
              <button
                type="button"
                aria-pressed={isFull}
                disabled={uploading}
                onClick={() => onModeChange('full')}
                className={`segmented-option ${isFull ? 'segmented-option-active' : ''}`}
              >
                Full translation
              </button>
              <button
                type="button"
                aria-pressed={!isFull}
                disabled={uploading}
                onClick={() => onModeChange('lipsync_only')}
                className={`segmented-option ${!isFull ? 'segmented-option-active' : ''}`}
              >
                Lip-sync only
              </button>
            </div>
          </div>

          <UploadZone
            file={file}
            onFileSelect={onFileChange}
            onClearFile={() => onFileChange(null)}
            disabled={uploading}
            hint={isFull ? 'Speech, maths and all — we keep the background music.' : 'Real people on camera work best.'}
          />

          {isFull ? (
            <div className="flex flex-grow flex-col gap-3.5 px-5 pb-5 pt-1">
              <div className="flex items-center justify-between">
                <span className="text-base font-semibold">Language &amp; voice</span>
                <button
                  type="button"
                  onClick={() => setShowTuning((open) => !open)}
                  aria-expanded={showTuning}
                  className="flex items-center gap-1 border-0 bg-transparent p-0 text-sm font-semibold text-accent-ink hover:text-[#36229A]"
                >
                  Voice fine-tuning
                  <ChevronDown className={`h-4 w-4 transition-transform ${showTuning ? 'rotate-180' : ''}`} strokeWidth={2} />
                </button>
              </div>

              <div className="grid gap-3.5 md:grid-cols-3">
                <label className="field">
                  Translate to
                  <select value={selectedLang} onChange={(event) => onLangChange(event.target.value)} disabled={uploading} className="field-control">
                    {languages.map((lang) => (
                      <option key={lang.code} value={lang.code} title={lang.detail}>
                        {lang.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  Voice
                  <select
                    value={elevenLabsVoices.some((voice) => voice.id === selectedVoice) ? selectedVoice : ''}
                    onChange={(event) => onVoiceChange(event.target.value)}
                    disabled={uploading}
                    className="field-control"
                  >
                    {elevenLabsVoices.some((voice) => voice.id === selectedVoice) ? null : <option value="">Custom voice ID</option>}
                    {elevenLabsVoices.map((voice) => (
                      <option key={voice.id} value={voice.id}>{voice.name}</option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  Voice model
                  <select value={ttsModel} onChange={(event) => onModelChange(event.target.value)} disabled={uploading} className="field-control">
                    {elevenLabsModels.map((model) => (
                      <option key={model.id} value={model.id}>{model.name}</option>
                    ))}
                  </select>
                </label>
              </div>

              {showTuning ? (
                <div className="flex flex-col gap-3.5 rounded-[10px] border border-divider p-4">
                  <label className="field">
                    Custom ElevenLabs voice ID
                    <input
                      type="text"
                      value={selectedVoice}
                      onChange={(event) => onVoiceChange(event.target.value)}
                      disabled={uploading}
                      placeholder="Paste a voice ID"
                      className="field-control text-sm"
                    />
                  </label>
                  <div className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
                    <Slider label="Speed" value={ttsSpeed} min="0.7" max="1.2" onChange={onSpeedChange} disabled={uploading} />
                    <Slider label="Stability" value={ttsStability} min="0" max="1" onChange={onStabilityChange} disabled={uploading} />
                    <Slider label="Likeness to voice" value={ttsSimilarityBoost} min="0" max="1" onChange={onSimilarityChange} disabled={uploading} />
                    <Slider label="Expressiveness" value={ttsStyle} min="0" max="1" onChange={onStyleChange} disabled={uploading} />
                  </div>
                  <div className="flex items-center gap-3">
                    <Switch checked={ttsSpeakerBoost} onChange={onSpeakerBoostChange} label="Speaker boost" disabled={uploading} />
                    <span className="text-sm font-medium">Speaker boost</span>
                  </div>
                </div>
              ) : null}

              <div className="flex items-center justify-between gap-4 rounded-[10px] bg-paper px-3.5 py-3">
                <div className="flex flex-col gap-0.5">
                  <span className="text-sm font-semibold">Lip-sync faces</span>
                  <span className="text-[13px] text-muted">For real people on camera. Turn off for cartoons and 3D animation.</span>
                </div>
                <Switch checked={enableLipSync} onChange={onLipSyncChange} label="Lip-sync faces" disabled={uploading} />
              </div>
            </div>
          ) : null}
        </section>

        {isFull ? (
          <TranscriptPreview />
        ) : (
          <DubAudioCard separateAudioFile={separateAudioFile} onSelect={onSeparateAudioChange} disabled={uploading} />
        )}
      </div>

      {errorMessage ? (
        <div role="alert" className="rounded-xl border border-[#F0D2CE] bg-[#FCF1EF] px-4 py-3 text-sm text-[#8E2B20]">
          <span className="font-semibold">Dubbing didn&apos;t finish. </span>
          {errorMessage}
        </div>
      ) : null}

      <div className="flex flex-wrap items-center justify-between gap-6">
        <div className="flex items-center gap-3.5">
          <div className="flex h-10 w-10 items-center justify-center rounded-[10px] bg-accent-tint">
            <Sparkles className="h-[18px] w-[18px] text-accent" strokeWidth={1.8} />
          </div>
          <div className="flex flex-col gap-0.5">
            <span className="text-[15px] font-semibold">{isFull ? 'Transcribe, translate, voice, sync.' : 'Lip-sync the faces to the audio.'}</span>
            <span className="text-[13px] text-muted">
              {isFull ? 'One run takes a few minutes. Every line stays editable afterwards.' : 'Lip-sync is slow on this computer — expect several minutes.'}
            </span>
          </div>
        </div>
        <button type="button" onClick={onStart} disabled={!file || uploading} className="btn-primary h-12 px-6 text-base">
          Start dubbing
          <ArrowRight className="h-[18px] w-[18px]" strokeWidth={2} />
        </button>
      </div>
    </main>
  )
}

export default SetupScreen
