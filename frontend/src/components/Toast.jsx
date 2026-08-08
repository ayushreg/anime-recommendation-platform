import React, { useEffect } from "react";

export function Toast({ message, onDone, tone = "info" }) {
  useEffect(() => {
    if (!message) return undefined;
    const t = setTimeout(onDone, 2800);
    return () => clearTimeout(t);
  }, [message, onDone]);
  if (!message) return null;
  return (
    <div className={`toast-float tone-${tone}`} role="status" aria-live="polite">
      {message}
    </div>
  );
}

export function useToast() {
  const [message, setMessage] = React.useState("");
  return {
    message,
    say: setMessage,
    clear: () => setMessage(""),
  };
}
