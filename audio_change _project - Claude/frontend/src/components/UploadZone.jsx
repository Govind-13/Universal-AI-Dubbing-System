import { FileVideo, Upload, X } from 'lucide-react'
import { useRef, useState } from 'react'

function formatFileSize(size) {
  if (!size) return '0 MB'
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

function DropArt() {
  return (
    <div className="relative h-[92px] w-[150px]" aria-hidden="true">
      <div className="absolute left-[22px] top-0 h-[72px] w-[108px] -rotate-6 rounded-[10px] bg-[#E1DAFA]" />
      <div className="absolute left-[14px] top-2 flex h-[76px] w-[112px] flex-col items-center justify-center gap-2 rounded-[10px] border border-[#DCD5F5] bg-white shadow-lift">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="#5A3FD1"><path d="M8 5.5v13l11-6.5z" /></svg>
        <svg width="64" height="12" viewBox="0 0 64 12" fill="none" stroke="#9D8DE6" strokeWidth="2" strokeLinecap="round">
          <path d="M2 5v2M8 3v6M14 1v10M20 4v4M26 2v8M32 4v4M38 1v10M44 3v6M50 5v2M56 3v6M62 5v2" />
        </svg>
      </div>
      <div className="absolute bottom-0 right-0 flex h-[34px] w-11 items-center justify-center rounded-[9px] bg-accent font-tamil text-base font-medium text-white">த</div>
    </div>
  )
}

function UploadZone({ file, onFileSelect, onClearFile, disabled, hint }) {
  const [isDragging, setIsDragging] = useState(false)
  const inputRef = useRef(null)

  const applyFile = (nextFile) => {
    if (!nextFile || disabled) return
    onFileSelect(nextFile)
  }

  const handleDragOver = (event) => {
    event.preventDefault()
    if (!disabled) setIsDragging(true)
  }

  const handleDragLeave = (event) => {
    event.preventDefault()
    setIsDragging(false)
  }

  const handleDrop = (event) => {
    event.preventDefault()
    setIsDragging(false)
    applyFile(event.dataTransfer.files?.[0])
  }

  const handleInputChange = (event) => {
    if (event.target.files?.[0]) applyFile(event.target.files[0])
    event.target.value = ''
  }

  return (
    <div
      className={`m-4 flex min-h-[270px] flex-col items-center justify-center gap-3 rounded-[14px] border-[1.5px] border-dashed p-6 text-center transition-colors ${
        isDragging ? 'border-accent bg-accent-tint' : file ? 'border-solid border-accent-line bg-white' : 'border-accent-line bg-accent-wash'
      } ${disabled ? 'opacity-70' : ''}`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      <input ref={inputRef} type="file" accept="video/*" onChange={handleInputChange} disabled={disabled} className="hidden" />

      {!file ? (
        <>
          <DropArt />
          <div className="font-display text-[22px] font-semibold tracking-[-0.01em]">Drop a lesson video here</div>
          <div className="text-sm text-muted">{hint}</div>
          <button type="button" onClick={() => inputRef.current?.click()} disabled={disabled} className="btn-primary">
            <Upload className="h-[18px] w-[18px]" strokeWidth={2} />
            Choose a video
          </button>
          <div className="text-xs text-muted">MP4, MOV, MKV and most other formats</div>
        </>
      ) : (
        <div className="flex w-full flex-col items-center gap-5 sm:flex-row sm:justify-between sm:text-left">
          <div className="flex min-w-0 items-center gap-4">
            <div className="flex h-14 w-14 flex-none items-center justify-center rounded-xl bg-accent-tint text-accent">
              <FileVideo className="h-7 w-7" strokeWidth={1.8} />
            </div>
            <div className="min-w-0">
              <p className="m-0 truncate font-display text-lg font-semibold">{file.name}</p>
              <p className="m-0 mt-1 text-sm text-muted">{formatFileSize(file.size)} · ready to dub</p>
            </div>
          </div>
          <div className="flex flex-none gap-2">
            <button type="button" onClick={() => inputRef.current?.click()} disabled={disabled} className="btn-secondary">
              Replace
            </button>
            <button type="button" onClick={onClearFile} disabled={disabled} className="btn-secondary px-3" aria-label="Remove video">
              <X className="h-4 w-4" strokeWidth={2} />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default UploadZone
