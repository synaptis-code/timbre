import { useEffect, useRef } from "react";

export interface ChatMessage {
  id: number;
  role: "user" | "ai" | "error";
  text: string;
  /** Bulle IA encore en cours de streaming (le prochain ai_chunk s'y ajoute). */
  streaming?: boolean;
  /** Tour coupé (Stop ou nouvelle prise de parole) : affiché tel quel, marqué. */
  interrupted?: boolean;
}

export function ChatThread({ messages }: { messages: ChatMessage[] }) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <main className="thread">
      {messages.length === 0 ? (
        <p className="thread-empty">Aucun message pour l'instant. Écris quelque chose !</p>
      ) : (
        messages.map((message) => (
          <div
            key={message.id}
            className={`bubble bubble--${message.role} ${message.interrupted ? "bubble--interrupted" : ""}`}
          >
            {message.text}
          </div>
        ))
      )}
      <div ref={endRef} />
    </main>
  );
}
