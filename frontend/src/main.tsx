import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
// Polices auto-hébergées (pas d'appel à Google Fonts : l'adresse IP des visiteurs n'est pas transmise)
import "@fontsource-variable/bricolage-grotesque";
import "@fontsource/atkinson-hyperlegible/400.css";
import "@fontsource/atkinson-hyperlegible/700.css";
import "@fontsource/atkinson-hyperlegible/400-italic.css";
import "./styles.css";
import { App } from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
