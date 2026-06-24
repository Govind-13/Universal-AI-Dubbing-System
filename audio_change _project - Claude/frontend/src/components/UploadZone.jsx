import { FileVideo, FolderUp, X } from 'lucide-react'
import { useRef, useState } from 'react'

function formatFileSize(size) {
  if (!size) return '0 MB'
  return `${(size / (1024 * 1024)).toFixed(2)} MB`
}

function UploadZone({ file, onFileSelect, onClearFile, disabled }) {
  const [isDragging, setIsDragging] = useState(false)
  const inputRef = useRef(null)

  const applyFile = (nextFile) => {
    if (!nextFile || disabled) return
    onFileSelect(nextFile)
  }

  const handleDragOver = (event) => {
    event.preventDefault()
    if (!disabled) {
      setIsDragging(true)
    }
  }

  const handleDragLeave = (event) => {
    event.preventDefault()
    setIsDragging(false)
  }

  const handleDrop = (event) => {
    event.preventDefault()
    setIsDragging(false)

    const droppedFile = event.dataTransfer.files?.[0]
    applyFile(droppedFile)
  }

  const handleInputChange = (event) => {
    if (event.target.files?.[0]) {
      applyFile(event.target.files[0])
    }
  }

  return (
    <div
      className={`upload-zone ${file ? 'upload-zone-filled' : ''} ${isDragging ? 'upload-zone-dragging' : ''} ${
        disabled ? 'upload-zone-disabled' : ''
      }`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      <input
        ref={inputRef}
        type="file"
        accept="video/*"
        onChange={handleInputChange}
        disabled={disabled}
        className="hidden"
      />

      {!file ? (
        <div className="flex flex-col items-center text-center">
          <div className="upload-zone-icon">
            <FolderUp className="h-8 w-8" />
          </div>
          <h4 className="mt-6 text-2xl font-semibold text-white">Drop a source video into the workspace</h4>
          <p className="mt-3 max-w-md text-sm leading-7 text-slate-300">
            Drag and drop a lecture or lesson recording, or choose a file manually. The upload behavior and API flow
            remain unchanged.
          </p>

          <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row">
            <button type="button" onClick={() => inputRef.current?.click()} disabled={disabled} className="btn-primary">
              <FolderUp className="h-5 w-5" />
              Choose video
            </button>
            <span className="text-sm text-slate-400">MP4, MOV, AVI and similar classroom video formats</span>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-4">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-sky-300/20 bg-sky-400/10 text-sky-200">
              <FileVideo className="h-8 w-8" />
            </div>
            <div className="min-w-0">
              <p className="truncate text-lg font-semibold text-white">{file.name}</p>
              <p className="mt-1 text-sm text-slate-300">{formatFileSize(file.size)}</p>
              <p className="mt-1 text-sm text-slate-400">Ready for localization and subtitle generation.</p>
            </div>
          </div>

          <div className="flex gap-3">
            <button type="button" onClick={() => inputRef.current?.click()} disabled={disabled} className="btn-secondary">
              Replace file
            </button>
            <button type="button" onClick={onClearFile} disabled={disabled} className="btn-ghost">
              <X className="h-4 w-4" />
              Remove
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default UploadZone
