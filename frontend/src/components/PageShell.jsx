// src/components/PageShell.jsx
// Shared page layout. Keeps related content visually grouped into three
// distinct blocks — what this page is, what state it's in, and what's
// still to be built — rather than one flat wall of text.

export default function PageShell({
  group,
  icon,
  title,
  caption,
  status,
  roadmap,
  children,
}) {
  return (
    <div className="bb-page">
      <header className="bb-page-header">
        {group && <p className="bb-eyebrow">{group}</p>}
        <div className="bb-page-title-row">
          {icon && (
            <span className="bb-page-icon" aria-hidden="true">
              {icon}
            </span>
          )}
          <h2>{title}</h2>
        </div>
        {caption && <p className="bb-caption">{caption}</p>}
      </header>

      {status && (
        <div className="bb-card bb-status-card">
          <span className="bb-status-dot" aria-hidden="true" />
          <p>{status}</p>
        </div>
      )}

      {children}

      {roadmap && roadmap.length > 0 && (
        <div className="bb-card bb-roadmap">
          <p className="bb-roadmap-title">What's coming</p>
          <ul>
            {roadmap.map((line, i) => (
              <li key={i}>
                <span className="bb-roadmap-marker" aria-hidden="true" />
                {line}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
