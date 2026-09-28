import { Clapperboard, Home, Plus, Smile } from 'lucide-react'

export function BrandMark({ className = 'h-[26px] w-[26px]' }) {
  return (
    <svg className={className} viewBox="0 0 26 26" fill="none" stroke="#5A3FD1" strokeWidth="3" strokeLinecap="round" aria-hidden="true">
      <path d="M4 10v6M10 5v16M16 8v10M22 11v4" />
    </svg>
  )
}

function NavButton({ icon, label, active, disabled, onClick }) {
  const Icon = icon
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-current={active ? 'page' : undefined}
      className={`flex h-11 w-full items-center gap-3 rounded-[10px] border-0 px-3 text-left text-[15px] transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
        active ? 'bg-accent-soft font-semibold text-accent-ink' : 'bg-transparent font-medium text-ink-2 hover:bg-white/70'
      }`}
    >
      <Icon className="h-[18px] w-[18px]" strokeWidth={1.8} />
      {label}
    </button>
  )
}

function Sidebar({ view, pipelineMode, busy, backendOnline, recent, activeRecentId, onNavigate, onNewLesson, onOpenRecent }) {
  const onSetup = view === 'setup' || view === 'processing'

  return (
    <aside className="sticky top-0 hidden h-screen w-60 flex-none flex-col gap-7 border-r border-line bg-side px-5 pb-5 pt-7 lg:flex">
      <div className="flex items-center gap-2.5 px-1.5">
        <BrandMark />
        <span className="font-display text-[22px] font-semibold tracking-[-0.02em]">GR Studio</span>
      </div>

      <button type="button" onClick={onNewLesson} disabled={busy} className="btn-secondary h-11 justify-start px-4">
        <Plus className="h-[18px] w-[18px]" strokeWidth={2} />
        New lesson
      </button>

      <nav aria-label="Studio" className="flex flex-col gap-1">
        <span className="px-2.5 pb-2 text-xs font-semibold uppercase tracking-[0.12em] text-muted">Studio</span>
        <NavButton icon={Home} label="Home" active={view === 'home'} onClick={() => onNavigate('home')} />
        <NavButton
          icon={Clapperboard}
          label="Classroom dubbing"
          active={(onSetup && pipelineMode === 'full') || (view === 'review' && pipelineMode === 'full')}
          disabled={busy}
          onClick={() => onNavigate('setup', 'full')}
        />
        <NavButton
          icon={Smile}
          label="Lip-sync only"
          active={(onSetup || view === 'review') && pipelineMode === 'lipsync_only'}
          disabled={busy}
          onClick={() => onNavigate('setup', 'lipsync_only')}
        />
      </nav>

      {recent.length ? (
        <div className="flex flex-col gap-0.5">
          <span className="px-2.5 pb-2 text-xs font-semibold uppercase tracking-[0.12em] text-muted">Recent</span>
          {recent.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => onOpenRecent(item.id)}
              disabled={busy}
              className={`flex items-center gap-2 truncate rounded-lg border-0 bg-transparent px-3 py-2 text-left text-sm disabled:cursor-not-allowed ${
                item.id === activeRecentId ? 'font-semibold text-ink' : 'text-ink-2 hover:bg-white/70'
              }`}
            >
              {item.id === activeRecentId ? <span className="h-1.5 w-1.5 flex-none rounded-full bg-ok" /> : null}
              <span className="truncate">{item.name}</span>
            </button>
          ))}
        </div>
      ) : null}

      <div className="flex-grow" />

      <div className="flex flex-col gap-2.5 rounded-[14px] border border-line bg-white p-[18px]">
        <div className="flex h-9 w-9 items-center justify-center rounded-[10px] bg-accent-tint font-display text-xl font-semibold text-accent">∑</div>
        <div className="font-display text-lg font-semibold leading-tight">Maths stays maths.</div>
        <p className="m-0 text-[13px] leading-relaxed text-muted">
          Equations are read aloud naturally, and your glossary terms are never translated.
        </p>
      </div>

      <div className="flex items-center gap-2.5 border-t border-line-strong pt-4">
        <div className="flex h-[34px] w-[34px] items-center justify-center rounded-full bg-[#DCD6F7] text-sm font-bold text-accent-ink">AP</div>
        <div className="flex flex-col">
          <span className="text-sm font-semibold">The Apprentice Project</span>
          <span className="flex items-center gap-1.5 text-xs text-muted">
            <span className={`h-1.5 w-1.5 rounded-full ${backendOnline ? 'bg-ok' : 'bg-[#C0392B]'}`} />
            {backendOnline ? 'Local backend · :8000' : 'Backend offline · :8000'}
          </span>
        </div>
      </div>
    </aside>
  )
}

export function MobileBar({ onHome }) {
  return (
    <div className="flex items-center justify-between border-b border-line bg-side px-5 py-4 lg:hidden">
      <button type="button" onClick={onHome} className="flex items-center gap-2.5 border-0 bg-transparent p-0">
        <BrandMark className="h-6 w-6" />
        <span className="font-display text-xl font-semibold tracking-[-0.02em] text-ink">GR Studio</span>
      </button>
    </div>
  )
}

export default Sidebar
