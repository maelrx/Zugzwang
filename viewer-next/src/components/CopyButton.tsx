import { useState } from "react";
import { Icon } from "./Icon";
export function CopyButton({ text, label }: { text: string; label: string }) {
  const [state, setState] = useState<"idle" | "copied" | "error">("idle");
  return <span className="copy-control"><button className="button compact" disabled={!text} onClick={async () => {
    try { await navigator.clipboard.writeText(text); setState("copied"); } catch { setState("error"); }
  }} onBlur={() => setState("idle")}><Icon name={state === "copied" ? "check" : "copy"} size={14}/>{state === "copied" ? "Copiado" : label}</button><span className="sr-only" role="status">{state === "error" ? "Não foi possível copiar. Selecione o texto nos detalhes." : state === "copied" ? "Texto copiado" : ""}</span></span>;
}
