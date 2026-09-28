export const API_BASE = 'http://localhost:8000'

export const languages = [
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

export const elevenLabsModels = [
  { id: 'eleven_multilingual_v2', name: 'Multilingual v2' },
  { id: 'eleven_v3', name: 'Eleven v3' },
  { id: 'eleven_turbo_v2_5', name: 'Turbo v2.5' },
  { id: 'eleven_flash_v2_5', name: 'Flash v2.5' },
]

export const elevenLabsVoices = [
  { id: 'default', name: 'Default · Studio voice' },
  { id: 'pGYsZruQzo8cpdFVZyJc', name: 'Aria · Studio female' },
  { id: '21m00Tcm4TlvDq8ikWAM', name: 'Rachel · Warm narration' },
  { id: 'AZnzlk1XvdvUeBnXmlld', name: 'Domi · Bright female' },
  { id: 'EXAVITQu4vr4xnSDxMaL', name: 'Bella · Soft female' },
  { id: 'ErXwobaYiN019PkySvjV', name: 'Antoni · Natural male' },
  { id: 'TxGEqnHWrfWFTfGW9XjX', name: 'Josh · Deep male' },
  { id: 'VR6AewLTigWG4xSOukaG', name: 'Arnold · Strong male' },
  { id: 'pNInz6obpgDQGcFmaJgB', name: 'Adam · Crisp male' },
  { id: 'yoZ06aMxZJJ28mfd3POQ', name: 'Sam · Conversational male' },
]

export function voiceName(voiceId) {
  return elevenLabsVoices.find((voice) => voice.id === voiceId)?.name.split(' · ')[0] ?? 'Custom voice'
}

export function modelName(modelId) {
  return elevenLabsModels.find((model) => model.id === modelId)?.name ?? modelId
}

export function formatTime(seconds) {
  if (!Number.isFinite(seconds)) return '0:00'
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = Math.floor(seconds % 60)
  return `${minutes}:${String(remainingSeconds).padStart(2, '0')}`
}
