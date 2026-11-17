/**
 * The CV itself: one column, black on white, thin rules, no colour. The same layout is
 * used on screen, when printing, and in the downloaded HTML file.
 */

export const CV_LABELS = {
  fr: { summary: 'Profil', experience: 'Expérience', education: 'Formation', projects: 'Projets', skills: 'Compétences', languages: 'Langues' },
  en: { summary: 'Profile', experience: 'Experience', education: 'Education', projects: 'Projects', skills: 'Skills', languages: 'Languages' }
};

const SECTIONS = ['experience', 'education', 'projects'];

function contactLine(header) {
  return [header.email, header.phone, header.city, header.linkedin].filter(Boolean);
}

export function CvDocument({ cv, header, language = 'fr' }) {
  const L = CV_LABELS[language] || CV_LABELS.fr;
  return (
    <div className="cv-doc">
      <header>
        <h1>{header.name || 'Your name'}</h1>
        {header.headline && <p className="cv-headline">{header.headline}</p>}
        <p className="cv-contact">{contactLine(header).join('  ·  ')}</p>
      </header>

      {cv.summary && (
        <section>
          <h2>{L.summary}</h2>
          <p>{cv.summary}</p>
        </section>
      )}

      {SECTIONS.filter((k) => cv[k]?.length).map((k) => (
        <section key={k}>
          <h2>{L[k]}</h2>
          {cv[k].map((item, i) => (
            <div className="cv-item" key={i}>
              <div className="cv-item-head">
                <span>
                  <strong>{item.title}</strong>
                  {item.org && <> — {item.org}</>}
                </span>
                {item.period && <span className="cv-period">{item.period}</span>}
              </div>
              {!!item.points?.length && (
                <ul>
                  {item.points.map((p, j) => (
                    <li key={j}>{p}</li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </section>
      ))}

      {['skills', 'languages'].filter((k) => cv[k]?.length).map((k) => (
        <section key={k}>
          <h2>{L[k]}</h2>
          <p>{cv[k].join(' · ')}</p>
        </section>
      ))}
    </div>
  );
}

/** The minimal stylesheet, shared by the page (theme.css imports nothing from here) and the file. */
export const CV_CSS = `
.cv-doc{font-family:'Helvetica Neue',Arial,sans-serif;color:#111;font-size:10.5pt;line-height:1.45;max-width:720px;margin:0 auto}
.cv-doc h1{font-size:22pt;font-weight:600;letter-spacing:-.01em;margin:0}
.cv-doc .cv-headline{margin:2px 0 0;font-size:11.5pt;color:#333}
.cv-doc .cv-contact{margin:6px 0 0;font-size:9.5pt;color:#555}
.cv-doc section{margin-top:16px}
.cv-doc h2{font-size:9pt;font-weight:600;text-transform:uppercase;letter-spacing:.12em;color:#333;border-bottom:1px solid #ccc;padding-bottom:3px;margin:0 0 8px}
.cv-doc p{margin:0}
.cv-doc .cv-item{margin-bottom:9px;break-inside:avoid}
.cv-doc .cv-item-head{display:flex;justify-content:space-between;gap:12px}
.cv-doc .cv-period{color:#555;white-space:nowrap;font-size:9.5pt}
.cv-doc ul{margin:3px 0 0;padding-left:16px;list-style:disc}
.cv-doc li{margin:1px 0}
`;

const esc = (s) =>
  String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

/** A standalone HTML file of the CV, to keep, print or open in a word processor. */
export function cvToHtml(cv, header, language = 'fr') {
  const L = CV_LABELS[language] || CV_LABELS.fr;
  const parts = [`<header><h1>${esc(header.name)}</h1>`];
  if (header.headline) parts.push(`<p class="cv-headline">${esc(header.headline)}</p>`);
  parts.push(`<p class="cv-contact">${contactLine(header).map(esc).join('  ·  ')}</p></header>`);
  if (cv.summary) parts.push(`<section><h2>${L.summary}</h2><p>${esc(cv.summary)}</p></section>`);
  for (const k of SECTIONS) {
    if (!cv[k]?.length) continue;
    parts.push(`<section><h2>${L[k]}</h2>`);
    for (const it of cv[k]) {
      parts.push(
        `<div class="cv-item"><div class="cv-item-head"><span><strong>${esc(it.title)}</strong>${it.org ? ' — ' + esc(it.org) : ''}</span>` +
          `${it.period ? `<span class="cv-period">${esc(it.period)}</span>` : ''}</div>` +
          (it.points?.length ? `<ul>${it.points.map((p) => `<li>${esc(p)}</li>`).join('')}</ul>` : '') +
          '</div>'
      );
    }
    parts.push('</section>');
  }
  for (const k of ['skills', 'languages']) {
    if (cv[k]?.length) parts.push(`<section><h2>${L[k]}</h2><p>${cv[k].map(esc).join(' · ')}</p></section>`);
  }
  return (
    `<!doctype html><html lang="${language}"><head><meta charset="utf-8"><title>CV — ${esc(header.name)}</title>` +
    `<meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:32px 24px;background:#fff}` +
    `@page{margin:16mm}${CV_CSS}</style></head><body><div class="cv-doc">${parts.join('')}</div></body></html>`
  );
}
