import type { ReactNode } from "react";
import { demoMode } from "../config";
import { useApp } from "../state/app";
import { ZoneSwitch } from "./ZoneSwitch";

const NAV = [
  { href: "#/", label: "Identifier", icon: "M4 8h3l2-3h6l2 3h3v11H4z M12 17a4 4 0 1 0 0-8 4 4 0 0 0 0 8z" },
  { href: "#/ornithotheque", label: "Ornithotèque", icon: "M4 5h7v14H4z M13 5h7v14h-7z M6.5 9h2 M15.5 9h2" },
  { href: "#/especes", label: "Espèces", icon: "M5 12c3-6 9-8 14-6-2 1-3 3-3 5 3 0 5 2 5 4-5-1-9 1-12 4-2-2-4-3-4-7z" },
  { href: "#/compte", label: "Compte", icon: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M4 20c1-4 4-6 8-6s7 2 8 6" },
];

function Icon({ d }: { d: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="icon">
      <path d={d} fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Shell({ route, children }: { route: string; children: ReactNode }) {
  const { toast } = useApp();
  const active = (href: string) => {
    const path = href.slice(1);
    return path === "/" ? route === "/" : route.startsWith(path);
  };
  return (
    <div className="shell">
      <a className="skip" href="#contenu">
        Aller au contenu
      </a>
      <header className="topbar">
        <a href="#/" className="brand" aria-label="BirdsFinder, accueil">
          <svg viewBox="0 0 64 64" aria-hidden="true">
            <path d="M14 38c6-14 20-22 34-18-3 2-5 5-6 8 5 0 8 3 9 6-9-2-16 1-21 7-5-3-11-4-16-3z" fill="currentColor" />
            <path d="M48 25l8-1-7 4z" fill="var(--signal)" />
          </svg>
          <span>BirdsFinder</span>
        </a>
        <nav className="topnav" aria-label="Navigation principale">
          {NAV.map((n) => (
            <a key={n.href} href={n.href} aria-current={active(n.href) ? "page" : undefined}>
              {n.label}
            </a>
          ))}
        </nav>
        <ZoneSwitch />
      </header>

      {demoMode && (
        <p className="demo-banner">
          Mode démo : le compte est fictif et tes observations restent sur cet appareil.
        </p>
      )}

      <main id="contenu" tabIndex={-1}>
        {children}
      </main>

      <footer className="footer">
        <a href="#/a-propos">Comment ça marche</a>
        <a href="#/confidentialite">Confidentialité</a>
        <span>Projet de formation Alyra, 2026</span>
      </footer>

      <nav className="tabbar" aria-label="Navigation principale">
        {NAV.map((n) => (
          <a key={n.href} href={n.href} aria-current={active(n.href) ? "page" : undefined}>
            <Icon d={n.icon} />
            <span>{n.label}</span>
          </a>
        ))}
      </nav>

      <div className="toast" role="status" aria-live="polite">
        {toast && <span>{toast}</span>}
      </div>
    </div>
  );
}
