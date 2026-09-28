import { useEffect, useMemo, useState } from 'react'
import axios from 'axios'

import Sidebar, { MobileBar } from './components/Sidebar'
import HomeScreen from './components/HomeScreen'
import SetupScreen from './components/SetupScreen'
import ProcessingScreen from './components/ProcessingScreen'
import ReviewScreen from './components/ReviewScreen'
import { API_BASE, languages, voiceName } from './constants'

const statusProgress = {
  Queued: 5,
  'Extracting source audio': 10,
  'Separating background music': 18,
  'Creating same-language transcript': 35,
  'Translating transcript': 50,
  'Verifying translated transcript': 62,
  'Generating ElevenLabs audio': 72,
  'Mixing background music with narration': 82,
  'Preparing subtitles': 88,
  'Replacing video audio': 94,
  'Using uploaded audio track': 30,
  'Extracting existing audio track': 30,
  'Running lip-sync': 60,
}

function App() {
  const [view, setView] = useState('home')
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [jobStatus, setJobStatus] = useState('')
  const [result, setResult] = useState(null)
  const [recent, setRecent] = useState([])
  const [activeRecentId, setActiveRecentId] = useState(null)
  const [backendOnline, setBackendOnline] = useState(false)
  const [pipelineMode, setPipelineMode] = useState('full')
  const [separateAudioFile, setSeparateAudioFile] = useState(null)
  const [selectedLang, setSelectedLang] = useState('hi')
  const [selectedVoice, setSelectedVoice] = useState('default')
  const [ttsModel, setTtsModel] = useState('eleven_multilingual_v2')
  const [ttsSpeed, setTtsSpeed] = useState(0.9)
  const [ttsStability, setTtsStability] = useState(0.75)
  const [ttsSimilarityBoost, setTtsSimilarityBoost] = useState(0.64)
  const [ttsStyle, setTtsStyle] = useState(0)
  const [ttsSpeakerBoost, setTtsSpeakerBoost] = useState(true)
  const [enableLipSync, setEnableLipSync] = useState(true)
  const [errorMessage, setErrorMessage] = useState('')

  const selectedLanguage = useMemo(
    () => languages.find((lang) => lang.code === selectedLang) ?? languages[0],
    [selectedLang]
  )

  useEffect(() => {
    let cancelled = false
    const check = async () => {
      try {
        await axios.get(`${API_BASE}/api/health`, { timeout: 4000 })
        if (!cancelled) setBackendOnline(true)
      } catch {
        if (!cancelled) setBackendOnline(false)
      }
    }
    check()
    const timer = setInterval(check, 15000)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [])

  const canOpenStep = (step) => {
    if (uploading) return false
    if (step === 'setup') return true
    if (step === 'review') return Boolean(result)
    return false
  }

  const navigate = (nextView, mode) => {
    if (mode) setPipelineMode(mode)
    if (nextView === 'setup' && uploading) return
    setView(uploading && nextView !== 'home' ? 'processing' : nextView)
  }

  const resetWorkflow = () => {
    setFile(null)
    setResult(null)
    setActiveRecentId(null)
    setProgress(0)
    setJobStatus('')
    setErrorMessage('')
    setSeparateAudioFile(null)
    setView('setup')
  }

  const openRecent = (id) => {
    const item = recent.find((entry) => entry.id === id)
    if (!item) return
    setResult(item.result)
    setActiveRecentId(id)
    setPipelineMode(item.result.mode === 'lipsync_only' ? 'lipsync_only' : 'full')
    setView('review')
  }

  const handleRerender = (rerenderResult) => {
    const next = {
      ...result,
      video_url: rerenderResult.video_url + '?t=' + Date.now(),
      subtitle_url: rerenderResult.subtitle_url,
      subtitle: rerenderResult.subtitle,
      tts: rerenderResult.tts ?? result.tts,
      lip_sync: rerenderResult.lip_sync ?? result.lip_sync,
      lip_sync_status: rerenderResult.lip_sync_status ?? result.lip_sync_status,
      bgm: rerenderResult.bgm ?? result.bgm,
      translation: {
        ...result.translation,
        segments: rerenderResult.translation.segments,
        text: rerenderResult.subtitle?.content ?? result.translation.text,
        json_url: rerenderResult.translation?.json_url ?? result.translation.json_url,
        json_filename: rerenderResult.translation?.json_filename ?? result.translation.json_filename,
      },
    }
    setResult(next)
    setRecent((entries) => entries.map((entry) => (entry.id === activeRecentId ? { ...entry, result: next } : entry)))
  }

  const handleUpload = async () => {
    if (!file) return

    setUploading(true)
    setErrorMessage('')
    setProgress(5)
    setJobStatus('Queued')
    setResult(null)
    setView('processing')

    const formData = new FormData()
    formData.append('file', file)
    if (pipelineMode === 'lipsync_only' && separateAudioFile) {
      formData.append('audio_file', separateAudioFile)
    }

    const fail = (message) => {
      setUploading(false)
      setProgress(0)
      setJobStatus('')
      setErrorMessage(message)
      setView('setup')
    }

    try {
      const paramsObj = { pipeline_mode: pipelineMode }
      if (pipelineMode === 'full') {
        Object.assign(paramsObj, {
          target_language: selectedLang,
          tts_voice_id: selectedVoice,
          tts_model_id: ttsModel,
          tts_speed: String(ttsSpeed),
          tts_stability: String(ttsStability),
          tts_similarity_boost: String(ttsSimilarityBoost),
          tts_style: String(ttsStyle),
          tts_speaker_boost: String(ttsSpeakerBoost),
          enable_lip_sync: String(enableLipSync),
        })
      }
      const uploadParams = new URLSearchParams(paramsObj)
      const response = await axios.post(`${API_BASE}/upload?${uploadParams.toString()}`, formData)
      const jobId = response.data.job_id
      const lessonName = file.name.replace(/\.[^.]+$/, '')

      const pollInterval = setInterval(async () => {
        try {
          const { data: job } = await axios.get(`${API_BASE}/status/${jobId}`)

          if (job.status === 'Completed') {
            clearInterval(pollInterval)
            setProgress(100)
            setJobStatus('Completed')
            setResult(job.result)
            setRecent((entries) => [{ id: jobId, name: lessonName, result: job.result }, ...entries].slice(0, 5))
            setActiveRecentId(jobId)
            setUploading(false)
            setView('review')
          } else if (job.status === 'Failed') {
            clearInterval(pollInterval)
            fail(job.error || 'Processing failed.')
          } else if (job.status) {
            setJobStatus(job.status)
            if (statusProgress[job.status]) setProgress(statusProgress[job.status])
          }
        } catch (pollErr) {
          if (pollErr?.response?.status === 404) {
            clearInterval(pollInterval)
            fail('The backend restarted and lost this job. Please start it again.')
          }
        }
      }, 2000)
    } catch (error) {
      fail(error?.response?.data?.detail || 'Processing could not start. Please confirm the backend is running and try again.')
    }
  }

  const stepClick = (step) => {
    if (step === 'setup') setView('setup')
    if (step === 'review' && result) setView('review')
  }

  if (view === 'home') {
    return (
      <HomeScreen
        languageCount={languages.length}
        backendOnline={backendOnline}
        onStart={() => setView(uploading ? 'processing' : result ? 'review' : 'setup')}
      />
    )
  }

  return (
    <div className="flex min-h-screen flex-col bg-paper lg:flex-row">
      <MobileBar onHome={() => setView('home')} />
      <Sidebar
        view={view}
        pipelineMode={pipelineMode}
        busy={uploading}
        backendOnline={backendOnline}
        recent={recent}
        activeRecentId={activeRecentId}
        onNavigate={navigate}
        onNewLesson={resetWorkflow}
        onOpenRecent={openRecent}
      />

      {view === 'setup' ? (
        <SetupScreen
          pipelineMode={pipelineMode}
          onModeChange={setPipelineMode}
          file={file}
          onFileChange={setFile}
          uploading={uploading}
          errorMessage={errorMessage}
          separateAudioFile={separateAudioFile}
          onSeparateAudioChange={setSeparateAudioFile}
          selectedLang={selectedLang}
          onLangChange={setSelectedLang}
          selectedVoice={selectedVoice}
          onVoiceChange={setSelectedVoice}
          ttsModel={ttsModel}
          onModelChange={setTtsModel}
          ttsSpeed={ttsSpeed}
          onSpeedChange={setTtsSpeed}
          ttsStability={ttsStability}
          onStabilityChange={setTtsStability}
          ttsSimilarityBoost={ttsSimilarityBoost}
          onSimilarityChange={setTtsSimilarityBoost}
          ttsStyle={ttsStyle}
          onStyleChange={setTtsStyle}
          ttsSpeakerBoost={ttsSpeakerBoost}
          onSpeakerBoostChange={setTtsSpeakerBoost}
          enableLipSync={enableLipSync}
          onLipSyncChange={setEnableLipSync}
          onStart={handleUpload}
          onStepClick={stepClick}
          canOpenStep={canOpenStep}
        />
      ) : null}

      {view === 'processing' ? (
        <ProcessingScreen
          file={file}
          jobStatus={jobStatus}
          progress={progress}
          pipelineMode={pipelineMode}
          languageName={selectedLanguage.name}
          voiceLabel={voiceName(selectedVoice)}
          enableLipSync={enableLipSync}
          onStepClick={stepClick}
          canOpenStep={canOpenStep}
        />
      ) : null}

      {view === 'review' && result ? (
        <ReviewScreen
          key={result.video_url}
          result={result}
          onRerender={handleRerender}
          onStepClick={stepClick}
          canOpenStep={canOpenStep}
        />
      ) : null}
    </div>
  )
}

export default App
