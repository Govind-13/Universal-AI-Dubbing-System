import { ArrowRight, Music, PenLine, Sparkles } from 'lucide-react'

const scriptTiles = [
  { glyph: 'A', font: 'font-display' },
  { glyph: 'த', font: 'font-tamil', active: true },
  { glyph: 'अ', font: 'font-deva' },
  { glyph: 'అ', font: 'font-telugu' },
]

const moreScripts = [
  { glyph: 'ಅ', font: 'font-kannada' },
  { glyph: 'അ', font: 'font-malayalam' },
  { glyph: '∑', font: 'font-display' },
]

function Tile({ glyph, font, active }) {
  return (
    <span className={`flex h-14 w-14 items-center justify-center rounded-xl text-2xl ${font} ${active ? 'bg-accent text-white' : 'bg-night-line text-lilac-3'}`}>
      {glyph}
    </span>
  )
}

function LineCard({ lines }) {
  return (
    <div className="flex flex-col gap-3.5">
      {lines.map(([time, text]) => (
        <div key={time} className="flex gap-3">
          <span className="text-xs font-semibold text-faint">{time}</span>
          <span className="text-[13px] leading-snug text-lilac-3">{text}</span>
        </div>
      ))}
    </div>
  )
}

function Collage() {
  return (
    <div aria-hidden="true" className="absolute inset-y-0 right-0 hidden w-[680px] opacity-60 xl:block">
      <div className="absolute left-[40px] top-6 flex h-[200px] w-[300px] flex-col items-center justify-center gap-1.5 rounded-[14px] bg-night-3 font-display text-lilac-2">
        <span className="text-2xl font-medium">det(A − λI) = 0</span>
        <span className="text-lg">λ² − 5λ + 6 = 0</span>
        <span className="mt-4 rounded-[5px] bg-black/55 px-2.5 py-1 font-sans text-[13px] text-white">Appo lambda equals two or three.</span>
      </div>
      <div className="absolute left-[360px] top-[-40px] h-[220px] w-[300px] rounded-[14px] border border-night-line bg-night-2 px-5 pb-5 pt-[60px]">
        <LineCard
          lines={[
            ['0:03', 'Ippo namma matrix A-oda eigenvalues-a find pannalaam.'],
            ['0:07', 'Mudhalla characteristic equation ezhudhunga.'],
          ]}
        />
      </div>
      <div className="absolute left-[40px] top-[244px] flex h-[150px] w-[300px] items-center justify-center gap-3 rounded-[14px] border border-night-line bg-night-2">
        {scriptTiles.map((tile) => <Tile key={tile.glyph} {...tile} />)}
      </div>
      <div className="absolute left-[360px] top-[200px] flex h-[140px] w-[300px] flex-col justify-between rounded-[14px] bg-night-3 p-5">
        <svg width="260" height="56" viewBox="0 0 260 56" fill="none" stroke="#9D8DE6" strokeWidth="4" strokeLinecap="round">
          <path d="M4 24v8M16 16v24M28 8v40M40 20v16M52 12v32M64 22v12M76 4v48M88 14v28M100 20v16M112 10v36M124 24v8M136 16v24M148 6v44M160 18v20M172 12v32M184 22v12M196 8v40M208 16v24M220 24v8M232 14v28M244 20v16M256 26v4" />
        </svg>
        <span className="text-[13px] text-lilac-2">Rachel · Multilingual v2</span>
      </div>
      <div className="absolute left-[40px] top-[414px] flex h-[160px] w-[300px] items-center justify-center rounded-[14px] bg-night-3">
        <span className="flex h-[60px] w-[60px] items-center justify-center rounded-full bg-white/90">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="#3A27A6"><path d="M8 5.5v13l11-6.5z" /></svg>
        </span>
      </div>
      <div className="absolute left-[360px] top-[360px] flex h-[200px] w-[300px] flex-col gap-1.5 rounded-[14px] border border-night-line bg-night-2 p-5 text-[13px] leading-normal text-lilac-2">
        <span className="text-faint">12</span>
        <span>00:00:17,000 --&gt; 00:00:21,000</span>
        <span className="text-white">Appo lambda equals two or three.</span>
      </div>
      <div className="absolute left-[40px] top-[594px] h-[230px] w-[300px] rounded-[14px] border border-night-line bg-night-2 p-5">
        <LineCard
          lines={[
            ['0:12', 'Idha expand panna lambda squared minus five lambda plus six varum.'],
            ['0:17', 'Appo lambda equals two or three.'],
          ]}
        />
      </div>
      <div className="absolute left-[360px] top-[580px] flex h-[240px] w-[300px] items-center justify-center gap-3 rounded-[14px] bg-night-3">
        {moreScripts.map((tile) => <Tile key={tile.glyph} {...tile} />)}
      </div>
    </div>
  )
}

function HomeScreen({ languageCount, backendOnline, onStart }) {
  return (
    <main className="flex min-h-screen flex-col gap-6 px-6 pb-7 pt-9 sm:px-11">
      <section aria-label="GR Studio introduction" className="relative min-h-[640px] flex-grow overflow-hidden rounded-[20px] bg-night">
        <Collage />
        <div
          aria-hidden="true"
          className="absolute inset-0"
          style={{ background: 'linear-gradient(90deg, #14111F 40%, rgba(20,17,31,0.6) 62%, rgba(20,17,31,0.15) 100%)' }}
        />

        <div className="absolute bottom-[72px] left-6 top-0 flex max-w-[560px] flex-col justify-center gap-[22px] pr-6 sm:left-12">
          <span className="flex h-[30px] items-center gap-2 self-start rounded-lg border border-night-edge px-3 text-[13px] font-semibold text-lilac-3">
            <Sparkles className="h-3.5 w-3.5 text-lilac" strokeWidth={1.8} />
            Built for The Apprentice Project
          </span>
          <h1 className="m-0 font-display text-6xl font-semibold leading-[0.95] tracking-[-0.035em] text-white sm:text-[88px]">GR Studio</h1>
          <p className="m-0 text-[21px] leading-[1.45] text-lilac-3">
            Teach once. Be understood in every classroom language — voice, subtitles and maths, all in sync.
          </p>
          <div className="mt-1.5 flex items-center gap-3">
            <button type="button" onClick={onStart} className="btn-primary h-[52px] rounded-xl bg-accent-bright px-6 text-base hover:bg-accent">
              Start dubbing
              <ArrowRight className="h-[18px] w-[18px]" strokeWidth={2} />
            </button>
          </div>
        </div>

        <div className="absolute inset-x-0 bottom-0 flex min-h-[72px] flex-wrap items-center gap-x-12 gap-y-2 border-t border-[#2A2540] bg-night/85 px-6 py-3 text-[15px] text-lilac-3 sm:px-12">
          <span className="flex items-center gap-2.5">
            <span className="font-tamil text-lg text-lilac">த</span>
            {languageCount} classroom languages
          </span>
          <span className="flex items-center gap-2.5">
            <span className="font-display text-lg font-semibold text-lilac">λ</span>
            Maths read aloud naturally
          </span>
          <span className="flex items-center gap-2.5">
            <Music className="h-[18px] w-[18px] text-lilac" strokeWidth={2} />
            Background music kept
          </span>
          <span className="flex items-center gap-2.5">
            <PenLine className="h-[18px] w-[18px] text-lilac" strokeWidth={2} />
            Every line editable
          </span>
        </div>
      </section>

      <div className="flex justify-end">
        <div
          role="status"
          className={`flex h-9 items-center gap-2 rounded-[10px] border px-3.5 text-sm font-medium ${
            backendOnline ? 'border-ok-line bg-[#F1F8F4] text-ok-ink' : 'border-[#F0D2CE] bg-[#FCF1EF] text-[#8E2B20]'
          }`}
        >
          <span className={`h-2 w-2 rounded-full ${backendOnline ? 'bg-ok' : 'bg-[#C0392B]'}`} />
          {backendOnline ? 'Backend connected' : 'Backend not reachable · start it on :8000'}
        </div>
      </div>
    </main>
  )
}

export default HomeScreen
