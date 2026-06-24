import { useMemo, useState } from 'react'
import {
  Languages,
  WandSparkles,
  Globe2,
} from 'lucide-react'
import axios from 'axios'

import ProgressPanel from './components/ProgressPanel'
import ResultsPanel from './components/ResultsPanel'
import UploadZone from './components/UploadZone'

const languages = [
  { code: 'en', name: 'English + English', detail: 'Clean English voiceover with synced subtitles' },
  { code: 'hi', name: 'Hinglish', detail: 'Hindi + English classroom mix' },
  { code: 'ta', name: 'Tamil + English', detail: 'Tamil script + English classroom mix' },
  { code: 'tanglish', name: 'Tanglish', detail: 'Roman Tamil + English classroom mix' },
  { code: 'te', name: 'Tenglish', detail: 'Telugu + English classroom mix' },
  { code: 'kn', name: 'Kanglish', detail: 'Kannada + English classroom mix' },
  { code: 'ml', name: 'Manglish', detail: 'Malayalam + English classroom mix' },
  { code: 'bn', name: 'Benglish', detail: 'Bengali + English classroom mix' },
  { code: 'mr', name: 'Minglish', detail: 'Marathi + English classroom mix' },
  { code: 'gu', name: 'Gujlish', detail: 'Gujarati + English classroom mix' },
  { code: 'pa', name: 'Punglish', detail: 'Punjabi + English classroom mix' },
  { code: 'or', name: 'Odlish', detail: 'Odia + English classroom mix' },
  { code: 'as', name: 'Assamese + English', detail: 'Assamese classroom mix' },
  { code: 'ur', name: 'Urlish', detail: 'Urdu + English classroom mix' },
  { code: 'sa', name: 'Sanskrit + English', detail: 'Sanskrit classroom mix' },
  { code: 'gom', name: 'Konkani + English', detail: 'Konkani classroom mix' },
  { code: 'ks', name: 'Kashmiri + English', detail: 'Kashmiri classroom mix' },
  { code: 'mai', name: 'Maithili + English', detail: 'Maithili classroom mix' },
  { code: 'sat', name: 'Santali + English', detail: 'Santali classroom mix' },
  { code: 'doi', name: 'Dogri + English', detail: 'Dogri classroom mix' },
  { code: 'brx', name: 'Bodo + English', detail: 'Bodo classroom mix' },
  { code: 'mni-mtei', name: 'Manipuri + English', detail: 'Manipuri classroom mix' },
  { code: 'sd', name: 'Sindhi + English', detail: 'Sindhi classroom mix' },
]

const elevenLabsModels = [
  { id: 'eleven_multilingual_v2', name: 'Multilingual v2' },
  { id: 'eleven_v3', name: 'Eleven v3' },
  { id: 'eleven_turbo_v2_5', name: 'Turbo v2.5' },
  { id: 'eleven_flash_v2_5', name: 'Flash v2.5' },
]

const elevenLabsVoices = [
  { id: 'default', name: 'Default Studio Voice' },
  { id: 'pGYsZruQzo8cpdFVZyJc', name: 'Aria - Studio Female' },
  { id: '21m00Tcm4TlvDq8ikWAM', name: 'Rachel - Warm narration' },
  { id: 'AZnzlk1XvdvUeBnXmlld', name: 'Domi - Bright female' },
  { id: 'EXAVITQu4vr4xnSDxMaL', name: 'Bella - Soft female' },
  { id: 'ErXwobaYiN019PkySvjV', name: 'Antoni - Natural male' },
  { id: 'TxGEqnHWrfWFTfGW9XjX', name: 'Josh - Deep male' },
  { id: 'VR6AewLTigWG4xSOukaG', name: 'Arnold - Strong male' },
  { id: 'pNInz6obpgDQGcFmaJgB', name: 'Adam - Crisp male' },
  { id: 'yoZ06aMxZJJ28mfd3POQ', name: 'Sam - Conversational male' },
]

function Header() {
  return (
    <header className="sticky top-0 z-50 w-full border-b border-white/10 bg-brand-dark/90 backdrop-blur-md">
      <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-6">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded bg-brand-gold text-black">
            <Globe2 className="h-6 w-6" />
          </div>
          <div className="flex flex-col justify-center">
            <span className="text-[10px] font-bold leading-none tracking-widest text-brand-gold uppercase">LinguistAI</span>
            <span className="text-lg font-bold leading-tight tracking-tight text-white mt-0.5">
              Classroom Dubbing Studio
            </span>
          </div>
        </div>

        <nav className="hidden items-center gap-8 md:flex">
          <a href="#" className="text-sm font-semibold text-white hover:text-brand-gold transition-colors">Home</a>
          <a href="#" className="text-sm font-semibold text-white hover:text-brand-gold transition-colors">Services</a>
          <a href="#" className="text-sm font-semibold text-brand-gold hover:text-brand-gold transition-colors">Growth Tools</a>
          <a href="#" className="text-sm font-semibold text-white hover:text-brand-gold transition-colors">About</a>
        </nav>

        <div className="flex items-center gap-4">
          <button className="hidden rounded-lg border-2 border-brand-gold px-5 py-2.5 text-sm font-bold text-brand-gold transition-all hover:bg-brand-gold/10 md:block">
            Free Tools
          </button>
          <button className="rounded-lg bg-brand-gold px-5 py-2.5 text-sm font-bold text-black transition-all hover:scale-105 hover:bg-brand-gold-hover shadow-[0_4px_14px_rgba(242,193,102,0.4)]">
            Get Quote
          </button>
        </div>
      </div>
    </header>
  )
}

function Hero() {
  return (
    <section className="relative overflow-hidden py-16 sm:py-24">
      <div className="mx-auto max-w-7xl px-6 text-center">
        <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight text-white mb-6 uppercase">
          DUBBING <span className="text-brand-gold">TOOLS</span>
        </h1>
        <p className="mx-auto max-w-2xl text-lg text-brand-muted mb-10">
          Turn educational videos into natural classroom-style Indian language + English dubbing with synced subtitles and voice controls.
        </p>
      </div>
    </section>
  )
}

function App() {
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [status, setStatus] = useState('idle')
  const [result, setResult] = useState(null)
  const [selectedLang, setSelectedLang] = useState('hi')
  const [selectedVoice, setSelectedVoice] = useState('default')
  const [ttsModel, setTtsModel] = useState('eleven_multilingual_v2')
  const [ttsSpeed, setTtsSpeed] = useState(0.9)
  const [ttsStability, setTtsStability] = useState(0.75)
  const [ttsSimilarityBoost, setTtsSimilarityBoost] = useState(0.64)
  const [ttsStyle, setTtsStyle] = useState(0)
  const [ttsSpeakerBoost, setTtsSpeakerBoost] = useState(true)
  const [errorMessage, setErrorMessage] = useState('')

  const selectedLanguage = useMemo(
    () => languages.find((lang) => lang.code === selectedLang) ?? languages[0],
    [selectedLang]
  )

  const pipelineStages = useMemo(() => {
    const currentStage = progress >= 100 ? 5 : progress >= 86 ? 4 : progress >= 76 ? 3 : progress >= 46 ? 2 : progress > 0 ? 1 : 0

    return [
      {
        key: 'upload',
        label: 'Input video',
        detail: file ? `Loaded: ${file.name}` : 'Upload source video',
        state: status === 'done' || currentStage > 0 ? 'complete' : file ? 'current' : 'upcoming',
      },
      {
        key: 'transcript',
        label: 'Same-language text',
        detail: 'Input audio to transcript text',
        state: status === 'done' || currentStage > 1 ? 'complete' : currentStage === 1 ? 'current' : 'upcoming',
      },
      {
        key: 'translation',
        label: 'Translation text',
        detail: `${selectedLanguage.name}: ${selectedLanguage.detail}`,
        state: status === 'done' || currentStage > 2 ? 'complete' : currentStage === 2 ? 'current' : 'upcoming',
      },
      {
        key: 'voice',
        label: 'ElevenLabs audio',
        detail: 'Translated text to synced voice audio',
        state: status === 'done' || currentStage > 3 ? 'complete' : currentStage === 3 ? 'current' : 'upcoming',
      },
      {
        key: 'render',
        label: 'Final output',
        detail: 'Remove old audio, add new synced audio',
        state: status === 'done' ? 'complete' : currentStage === 4 ? 'current' : 'upcoming',
      },
    ]
  }, [file, progress, selectedLanguage.detail, selectedLanguage.name, status])

  const resultSummary = useMemo(() => {
    if (!result?.translation?.segments?.length) {
      return null
    }

    const segments = result.translation.segments
    const duration = segments[segments.length - 1]?.end ?? 0

    return {
      duration,
      segments: segments.length,
      language: selectedLanguage.name,
      transcriptText:
        result.translation?.transcript_text ??
        result.translation?.text ??
        segments.map((segment) => segment.text).join(' '),
      subtitleText:
        result.translation?.text ??
        segments.map((segment) => segment.text).join(' '),
    }
  }, [result, selectedLanguage.name])

  const resetWorkflow = () => {
    setStatus('idle')
    setFile(null)
    setResult(null)
    setProgress(0)
    setUploading(false)
    setErrorMessage('')
  }

  const handleRerender = (rerenderResult) => {
    setResult((prev) => ({
      ...prev,
      video_url: rerenderResult.video_url + '?t=' + Date.now(),
      subtitle_url: rerenderResult.subtitle_url,
      subtitle: rerenderResult.subtitle,
      tts: rerenderResult.tts ?? prev.tts,
      translation: {
        ...prev.translation,
        segments: rerenderResult.translation.segments,
        text: rerenderResult.subtitle?.content ?? prev.translation.text,
        json_url: rerenderResult.translation?.json_url ?? prev.translation.json_url,
        json_filename: rerenderResult.translation?.json_filename ?? prev.translation.json_filename,
      },
    }))
  }

  const handleUpload = async () => {
    if (!file) return

    setUploading(true)
    setStatus('uploading')
    setErrorMessage('')
    setProgress(8)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const uploadParams = new URLSearchParams({
        target_language: selectedLang,
        tts_voice_id: selectedVoice,
        tts_model_id: ttsModel,
        tts_speed: String(ttsSpeed),
        tts_stability: String(ttsStability),
        tts_similarity_boost: String(ttsSimilarityBoost),
        tts_style: String(ttsStyle),
        tts_speaker_boost: String(ttsSpeakerBoost),
      })

      const response = await axios.post(
        `http://localhost:8000/upload?${uploadParams.toString()}`,
        formData
      )

      const jobId = response.data.job_id;

      const pollInterval = setInterval(async () => {
        try {
          const statusRes = await axios.get(`http://localhost:8000/status/${jobId}`);
          const job = statusRes.data;

          if (job.status === 'Completed') {
            clearInterval(pollInterval);
            setProgress(100);
            setResult(job.result);
            setStatus('done');
            setTimeout(() => setUploading(false), 500);
          } else if (job.status === 'Failed') {
            clearInterval(pollInterval);
            setStatus('error');
            setUploading(false);
            setProgress(0);
            setErrorMessage(job.error || 'Processing failed.');
          } else {
            // Update progress based on actual backend status
            const statusMap = {
              "Queued": 10,
              "Extracting Audio": 20,
              "Extracting source audio": 20,
              "Transcribing": 40,
              "Creating same-language transcript": 40,
              "Translating": 60,
              "Translating transcript": 60,
              "Generating Subtitles": 70,
              "Preparing subtitles": 70,
              "Generating TTS Audio": 80,
              "Generating ElevenLabs audio": 80,
              "Re-composing Video": 90,
              "Replacing video audio": 90,
            };
            if (statusMap[job.status]) {
                setProgress(statusMap[job.status]);
            }
          }
        } catch (pollErr) {
          console.error('Polling error', pollErr);
        }
      }, 2000);
    } catch (error) {
      console.error('Upload failed', error)
      setStatus('error')
      setUploading(false)
      setProgress(0)
      setErrorMessage(
        error?.response?.data?.detail ||
        'Processing could not be completed. Please confirm the backend is running and try again.'
      )
    }
  }

  return (
    <div className="min-h-screen bg-brand-dark text-white font-sans">
      <Header />

      <main className="pb-24">
        <Hero />

        <div className="mx-auto max-w-7xl px-6">
          <div className="grid gap-8 lg:grid-cols-[1.5fr_1fr]">
            <div className="space-y-8">
              <div className="surface-panel section-panel">
                <div className="section-heading">
                  <div>
                    <p className="section-kicker">Core Studio Tool</p>
                    <h2 className="section-title">Classroom Dubbing Pipeline</h2>
                  </div>
                  <span className="section-chip">Source {'->'} Code-mix {'->'} Export</span>
                </div>

                <div className="mt-8 space-y-6">
                  <UploadZone
                    file={file}
                    onFileSelect={setFile}
                    onClearFile={() => setFile(null)}
                    disabled={uploading}
                  />

                  <div className="grid gap-6 sm:grid-cols-2">
                    <div className="subtle-card">
                      <div className="flex items-start gap-4">
                        <div className="icon-badge">
                          <Languages className="h-5 w-5" />
                        </div>
                        <div className="flex-1">
                          <h4 className="text-base font-bold text-white">Target Language</h4>
                          <p className="mt-1 text-sm text-brand-muted">
                            Choose the classroom code-mixed output style
                          </p>
                          <select
                            value={selectedLang}
                            onChange={(event) => setSelectedLang(event.target.value)}
                            className="app-input mt-4 w-full"
                            disabled={uploading}
                          >
                            {languages.map((lang) => (
                              <option key={lang.code} value={lang.code}>
                                {lang.name} - {lang.detail}
                              </option>
                            ))}
                          </select>
                          <p className="mt-3 text-xs leading-5 text-brand-muted">
                            Technical, math, science, model, and tool names stay in English.
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="subtle-card sm:col-span-2">
                      <div className="flex items-start gap-4">
                        <div className="icon-badge">
                          <WandSparkles className="h-5 w-5" />
                        </div>
                        <div className="grid flex-1 gap-5 md:grid-cols-2">
                          <div>
                            <h4 className="text-base font-bold text-white">Voice Selection</h4>
                            <select
                              value={selectedVoice}
                              onChange={(event) => setSelectedVoice(event.target.value)}
                              className="app-input mt-4 w-full"
                              disabled={uploading}
                            >
                              {elevenLabsVoices.map((voice) => (
                                <option key={voice.id} value={voice.id}>
                                  {voice.name}
                                </option>
                              ))}
                            </select>
                            <input
                              type="text"
                              value={selectedVoice}
                              onChange={(event) => setSelectedVoice(event.target.value)}
                              className="app-input mt-2 w-full text-xs"
                              disabled={uploading}
                              placeholder="Or paste custom Voice ID"
                            />
                          </div>

                          <div>
                            <h4 className="text-base font-bold text-white">Model</h4>
                            <select
                              value={ttsModel}
                              onChange={(event) => setTtsModel(event.target.value)}
                              className="app-input mt-4 w-full"
                              disabled={uploading}
                            >
                              {elevenLabsModels.map((model) => (
                                <option key={model.id} value={model.id}>
                                  {model.name}
                                </option>
                              ))}
                            </select>
                          </div>

                          <label className="block">
                            <span className="label-text">Speed: {ttsSpeed.toFixed(2)}</span>
                            <input
                              type="range"
                              min="0.7"
                              max="1.2"
                              step="0.01"
                              value={ttsSpeed}
                              onChange={(event) => setTtsSpeed(Number(event.target.value))}
                              className="mt-3 w-full accent-brand-gold"
                              disabled={uploading}
                            />
                          </label>

                          <label className="block">
                            <span className="label-text">Stability: {ttsStability.toFixed(2)}</span>
                            <input
                              type="range"
                              min="0"
                              max="1"
                              step="0.01"
                              value={ttsStability}
                              onChange={(event) => setTtsStability(Number(event.target.value))}
                              className="mt-3 w-full accent-brand-gold"
                              disabled={uploading}
                            />
                          </label>

                          <label className="block">
                            <span className="label-text">Similarity boost: {ttsSimilarityBoost.toFixed(2)}</span>
                            <input
                              type="range"
                              min="0"
                              max="1"
                              step="0.01"
                              value={ttsSimilarityBoost}
                              onChange={(event) => setTtsSimilarityBoost(Number(event.target.value))}
                              className="mt-3 w-full accent-brand-gold"
                              disabled={uploading}
                            />
                          </label>

                          <label className="block">
                            <span className="label-text">Style: {ttsStyle.toFixed(2)}</span>
                            <input
                              type="range"
                              min="0"
                              max="1"
                              step="0.01"
                              value={ttsStyle}
                              onChange={(event) => setTtsStyle(Number(event.target.value))}
                              className="mt-3 w-full accent-brand-gold"
                              disabled={uploading}
                            />
                          </label>

                          <label className="flex items-center gap-3 rounded-lg border border-white/10 bg-brand-dark px-4 py-3 text-sm font-semibold text-white">
                            <input
                              type="checkbox"
                              checked={ttsSpeakerBoost}
                              onChange={(event) => setTtsSpeakerBoost(event.target.checked)}
                              className="h-4 w-4 accent-brand-gold"
                              disabled={uploading}
                            />
                            Speaker boost
                          </label>
                        </div>
                      </div>
                    </div>

                    <div className="subtle-card flex flex-col justify-center">
                      <button
                        onClick={handleUpload}
                        disabled={!file || uploading}
                        className="btn-primary w-full h-full min-h-[5rem]"
                      >
                        <WandSparkles className="h-5 w-5" />
                        {uploading ? 'Processing...' : 'Start Classroom Dubbing'}
                      </button>

                      {status === 'error' && errorMessage ? (
                        <div className="status-banner status-banner-error mt-4">
                          <p className="font-bold text-red-100">Processing Failed</p>
                          <p className="mt-1 text-sm text-red-200">{errorMessage}</p>
                        </div>
                      ) : null}
                    </div>
                  </div>
                </div>
              </div>

              <div className="surface-panel section-panel">
                <div className="section-heading">
                  <div>
                    <p className="section-kicker">Results</p>
                    <h3 className="section-title">Review Classroom Output</h3>
                  </div>
                </div>

                <ResultsPanel
                  result={result}
                  selectedLanguage={selectedLanguage}
                  summary={resultSummary}
                  onReset={resetWorkflow}
                  onRerender={handleRerender}
                />
              </div>
            </div>

            <div className="space-y-8">
              <ProgressPanel
                uploading={uploading}
                status={status}
                progress={progress}
                stages={pipelineStages}
                selectedLanguage={selectedLanguage.name}
                hasFile={Boolean(file)}
                hasResult={Boolean(result)}
              />
            </div>
          </div>
        </div>
      </main>

      {/* Floating WhatsApp Icon */}
      <a href="#" className="fixed bottom-6 right-6 flex h-14 w-14 items-center justify-center rounded-full bg-brand-green text-white shadow-lg shadow-brand-green/30 hover:scale-110 transition-transform">
        <svg fill="currentColor" viewBox="0 0 24 24" className="h-7 w-7"><path d="M12.031 6.172c-3.181 0-5.767 2.586-5.768 5.766-.001 1.298.38 2.27 1.019 3.287l-.582 2.128 2.182-.573c.978.58 1.911.928 3.145.929 3.178 0 5.767-2.587 5.768-5.766.001-3.187-2.575-5.77-5.764-5.771zm3.392 8.244c-.144.405-.837.774-1.17.824-.299.045-.677.063-1.092-.069-.252-.08-.575-.187-.988-.365-1.739-.751-2.874-2.502-2.961-2.617-.087-.116-.708-.94-.708-1.793s.448-1.273.607-1.446c.159-.173.346-.217.462-.217l.332.006c.106.005.249-.04.39.298.144.347.491 1.2.534 1.287.043.087.072.188.014.304-.058.116-.087.188-.173.289l-.26.304c-.087.086-.177.18-.076.354.101.174.449.741.964 1.201.662.591 1.221.774 1.394.86s.274.072.376-.043c.101-.116.433-.506.549-.68.116-.173.231-.145.39-.087s1.011.477 1.184.564.289.13.332.202c.045.072.045.419-.1.824zm-3.423-14.416c-6.627 0-12 5.373-12 12s5.373 12 12 12 12-5.373 12-12-5.373-12-12-12zm.029 18.88c-1.161 0-2.305-.292-3.318-.844l-3.677.964.984-3.595c-.607-1.052-.927-2.246-.926-3.468.001-5.824 4.74-10.563 10.567-10.564 5.823 0 10.564 4.745 10.564 10.568s-4.741 10.564-10.564 10.564z" /></svg>
      </a>
    </div>
  )
}

export default App
