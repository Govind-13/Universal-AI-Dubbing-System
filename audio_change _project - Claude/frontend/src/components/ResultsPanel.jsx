import { useMemo, useState } from 'react'
import axios from 'axios'
import {
  CheckCircle2,
  Download,
  FileText,
  ListVideo,
  Pencil,
  RefreshCcw,
  Subtitles,
  Video,
  X,
} from 'lucide-react'

const resultTabs = [
  { key: 'preview', label: 'Preview', icon: Video },
  { key: 'transcript', label: 'Transcript', icon: FileText },
  { key: 'segments', label: 'Segments', icon: ListVideo },
  { key: 'subtitles', label: 'SRT Transcript', icon: Subtitles },
]

function formatTime(seconds) {
  if (!Number.isFinite(seconds)) return '0:00'
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = Math.floor(seconds % 60)
  return `${minutes}:${String(remainingSeconds).padStart(2, '0')}`
}

function formatSrtTimestamp(seconds) {
  if (!Number.isFinite(seconds)) return '00:00:00,000'
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const wholeSeconds = Math.floor(seconds % 60)
  const milliseconds = Math.floor((seconds % 1) * 1000)
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(wholeSeconds).padStart(2, '0')},${String(milliseconds).padStart(3, '0')}`
}

function buildSrtPreview(segments) {
  if (!segments.length) return ''

  return segments
    .map(
      (segment, index) =>
        `${index + 1}\n${formatSrtTimestamp(segment.start)} --> ${formatSrtTimestamp(segment.end)}\n${segment.text?.trim() ?? ''}`
    )
    .join('\n\n')
}

function ResultsPanel({ result, selectedLanguage, summary, onReset, onRerender }) {
  const [activeTab, setActiveTab] = useState('preview')
  const [editMode, setEditMode] = useState(false)
  const [editedSegments, setEditedSegments] = useState([])
  const [rerendering, setRerendering] = useState(false)
  const [rerenderError, setRerenderError] = useState('')

  const enterEditMode = () => {
    setEditedSegments((result?.translation?.segments ?? []).map((s) => ({ ...s })))
    setEditMode(true)
    setRerenderError('')
  }

  const cancelEdit = () => {
    setEditMode(false)
    setEditedSegments([])
    setRerenderError('')
  }

  const updateSegment = (index, field, value) => {
    setEditedSegments((prev) =>
      prev.map((s, i) =>
        i === index
          ? { ...s, [field]: field === 'text' ? value : parseFloat(value) || 0 }
          : s
      )
    )
  }

  const handleRerender = async () => {
    setRerendering(true)
    setRerenderError('')
    try {
      const response = await axios.post('http://localhost:8000/rerender', {
        video_filename: result.filename,
        target_language: result.translation.target_language,
        segments: editedSegments,
        tts_voice_id: result.tts?.voice_id ?? 'default',
        tts_model_id: result.tts?.settings?.model_id ?? 'eleven_multilingual_v2',
        tts_speed: result.tts?.settings?.speed ?? 0.9,
        tts_stability: result.tts?.settings?.stability ?? 0.75,
        tts_similarity_boost: result.tts?.settings?.similarity_boost ?? 0.64,
        tts_style: result.tts?.settings?.style ?? 0,
        tts_speaker_boost: result.tts?.settings?.use_speaker_boost ?? true,
      })
      onRerender(response.data)
      setEditMode(false)
    } catch (error) {
      setRerenderError(error?.response?.data?.detail || 'Re-render failed. Please try again.')
    } finally {
      setRerendering(false)
    }
  }

  const segments = useMemo(() => result?.translation?.segments ?? [], [result?.translation?.segments])
  const transcriptionText = result?.transcription?.cleaned_text ?? result?.transcription?.text ?? ''
  const reviewedTranslationText = result?.translation?.transcript_text ?? ''
  const subtitleSrt = result?.subtitle?.content ?? buildSrtPreview(segments)
  const subtitleTitle =
    selectedLanguage?.code === 'tanglish'
      ? 'Tanglish classroom-style SRT transcript'
      : 'SRT transcript'

  const timelineSegments = useMemo(() => {
    if (!segments.length) return []
    const totalDuration = segments[segments.length - 1]?.end || 1

    return segments.map((segment, index) => ({
      id: `${index}-${segment.start}-${segment.end}`,
      left: (segment.start / totalDuration) * 100,
      width: Math.max(((segment.end - segment.start) / totalDuration) * 100, 2.5),
      ...segment,
    }))
  }, [segments])

  if (!result) {
    return (
      <div className="empty-results">
        <div className="empty-results-icon">
          <Video className="h-8 w-8" />
        </div>
        <h4 className="mt-6 text-2xl font-semibold text-white">Results will appear here</h4>
        <p className="mt-3 max-w-2xl text-center text-sm leading-7 text-slate-300">
          Once processing finishes, you will be able to preview the dubbed video, inspect the transcript and
          classroom code-mixed text, and download the generated assets.
        </p>
      </div>
    )
  }

  return (
    <div className="mt-8 space-y-8">
      <div className="grid gap-4 md:grid-cols-4">
        <div className="metric-card">
          <p className="metric-label">Status</p>
          <p className="metric-value">Complete</p>
        </div>
        <div className="metric-card">
          <p className="metric-label">Language</p>
          <p className="metric-value">{selectedLanguage.name}</p>
        </div>
        <div className="metric-card">
          <p className="metric-label">Segments</p>
          <p className="metric-value">{summary?.segments ?? segments.length}</p>
        </div>
        <div className="metric-card">
          <p className="metric-label">Estimated duration</p>
          <p className="metric-value">{formatTime(summary?.duration ?? 0)}</p>
        </div>
      </div>

      <div className="status-banner status-banner-success">
        <div className="flex items-start gap-3">
          <CheckCircle2 className="mt-0.5 h-5 w-5 flex-none text-emerald-200" />
          <div>
            <p className="font-medium text-emerald-50">Classroom dubbing completed successfully.</p>
            <p className="mt-1 text-sm text-emerald-50/80">
              Review the generated video and text outputs, then download the assets you need.
            </p>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap gap-3">
        <a href={`http://localhost:8000${result.video_url}`} download className="btn-primary">
          <Download className="h-5 w-5" />
          Download video
        </a>
        {result.subtitle_url ? (
          <a href={`http://localhost:8000${result.subtitle_url}`} download className="btn-secondary">
            <Subtitles className="h-5 w-5" />
            Download SRT
          </a>
        ) : null}
        {result.transcription?.json_url ? (
          <a href={`http://localhost:8000${result.transcription.json_url}`} download className="btn-secondary">
            <FileText className="h-5 w-5" />
            Original JSON
          </a>
        ) : null}
        {result.translation?.json_url ? (
          <a href={`http://localhost:8000${result.translation.json_url}`} download className="btn-secondary">
            <FileText className="h-5 w-5" />
            Translation JSON
          </a>
        ) : null}
        <button type="button" onClick={onReset} className="btn-ghost">
          <RefreshCcw className="h-4 w-4" />
          Process another video
        </button>
      </div>

      <div className="result-tabs">
        <div className="result-tab-list" role="tablist" aria-label="Result tabs">
          {resultTabs.map((tab) => {
            const Icon = tab.icon
            return (
              <button
                key={tab.key}
                type="button"
                role="tab"
                aria-selected={activeTab === tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`result-tab ${activeTab === tab.key ? 'result-tab-active' : ''}`}
              >
                <Icon className="h-4 w-4" />
                {tab.label}
              </button>
            )
          })}
        </div>

        <div className="result-panel">
          {activeTab === 'preview' ? (
            <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
              <div className="media-card">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium text-slate-300">Classroom output</p>
                    <h4 className="mt-1 text-xl font-semibold text-white">Preview dubbed video</h4>
                  </div>
                </div>
                <div className="mt-5 overflow-hidden rounded-2xl border border-white/10 bg-black/60">
                  <video
                    src={`http://localhost:8000${result.video_url}`}
                    controls
                    className="aspect-video w-full object-contain"
                  />
                </div>
              </div>

              <div className="space-y-4">
                <div className="subtle-card">
                  <h4 className="text-base font-semibold text-white">Output summary</h4>
                  <p className="mt-3 text-sm leading-7 text-slate-300">
                    The exported video, classroom code-mixed transcript, and subtitle package are ready for review and sharing.
                  </p>
                </div>

                <div className="subtle-card">
                  <h4 className="text-base font-semibold text-white">Timeline overview</h4>
                  <div className="timeline-track mt-5">
                    {timelineSegments.map((segment) => (
                      <div
                        key={segment.id}
                        className="timeline-segment"
                        style={{ left: `${segment.left}%`, width: `${segment.width}%` }}
                        title={`${formatTime(segment.start)} - ${formatTime(segment.end)} | ${segment.text}`}
                      />
                    ))}
                  </div>
                  <div className="mt-4 flex justify-between text-xs uppercase tracking-[0.22em] text-slate-400">
                    <span>Start</span>
                    <span>{formatTime(summary?.duration ?? 0)}</span>
                  </div>
                </div>
              </div>
            </div>
          ) : null}

          {activeTab === 'transcript' ? (
            <div className="grid gap-6 xl:grid-cols-2">
              <article className="subtle-card">
                <h4 className="text-base font-semibold text-white">Cleaned transcript</h4>
                <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-slate-300">{transcriptionText || 'No transcript available.'}</p>
              </article>
              <article className="subtle-card">
                <h4 className="text-base font-semibold text-white">Reviewed classroom code-mix</h4>
                <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-slate-300">
                  {reviewedTranslationText || 'No reviewed classroom code-mix available.'}
                </p>
              </article>
            </div>
          ) : null}

          {activeTab === 'segments' ? (
            <div>
              <div className="flex items-center justify-between mb-4">
                <p className="text-sm text-slate-400">
                  {segments.length} segment{segments.length !== 1 ? 's' : ''}
                </p>
                {!editMode ? (
                  <button
                    type="button"
                    onClick={enterEditMode}
                    className="btn-secondary flex items-center gap-2 px-3 py-1.5 text-sm"
                  >
                    <Pencil className="h-3.5 w-3.5" />
                    Edit Timeline
                  </button>
                ) : (
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={cancelEdit}
                      disabled={rerendering}
                      className="btn-ghost flex items-center gap-1.5 px-3 py-1.5 text-sm"
                    >
                      <X className="h-3.5 w-3.5" />
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={handleRerender}
                      disabled={rerendering}
                      className="btn-primary flex items-center gap-2 px-4 py-1.5 text-sm"
                    >
                      <RefreshCcw className={`h-3.5 w-3.5 ${rerendering ? 'animate-spin' : ''}`} />
                      {rerendering ? 'Re-rendering...' : 'Save & Re-render'}
                    </button>
                  </div>
                )}
              </div>

              {rerenderError ? (
                <div className="status-banner status-banner-error mb-4">
                  <p className="text-sm text-red-200">{rerenderError}</p>
                </div>
              ) : null}

              <div className="segment-list">
                {(editMode ? editedSegments : segments).map((segment, index) => (
                  <div key={`${segment.start}-${segment.end}-${index}`} className="segment-row">
                    {editMode ? (
                      <div className="space-y-2 w-full">
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-slate-500 w-5 text-right">{index + 1}</span>
                          <label className="text-xs text-slate-400">Start</label>
                          <input
                            type="number"
                            step="0.01"
                            min="0"
                            value={segment.start}
                            onChange={(e) => updateSegment(index, 'start', e.target.value)}
                            className="app-input w-24 py-1 text-xs"
                          />
                          <label className="text-xs text-slate-400">End</label>
                          <input
                            type="number"
                            step="0.01"
                            min="0"
                            value={segment.end}
                            onChange={(e) => updateSegment(index, 'end', e.target.value)}
                            className="app-input w-24 py-1 text-xs"
                          />
                          <span className="text-xs text-slate-500 ml-auto">
                            {formatTime(segment.start)} – {formatTime(segment.end)}
                          </span>
                        </div>
                        <textarea
                          value={segment.text}
                          onChange={(e) => updateSegment(index, 'text', e.target.value)}
                          rows={2}
                          className="app-input w-full text-sm resize-y"
                        />
                      </div>
                    ) : (
                      <>
                        <div className="segment-time">
                          {formatTime(segment.start)} – {formatTime(segment.end)}
                        </div>
                        <p className="segment-text">{segment.text}</p>
                      </>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {activeTab === 'subtitles' ? (
            <article className="subtle-card">
              <h4 className="text-base font-semibold text-white">{subtitleTitle}</h4>
              <p className="mt-2 text-sm leading-7 text-slate-400">
                Timestamped subtitle transcript formatted for direct SRT review.
              </p>
              <pre className="mt-4 overflow-x-auto whitespace-pre-wrap rounded-2xl border border-white/10 bg-black/30 p-4 font-mono text-sm leading-7 text-slate-300">
                {subtitleSrt || 'No SRT transcript available.'}
              </pre>
            </article>
          ) : null}
        </div>
      </div>
    </div>
  )
}

export default ResultsPanel
