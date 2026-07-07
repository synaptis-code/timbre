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

const NEAR_BOTTOM_PX = 160;

export function ChatThread({ messages }: { messages: ChatMessage[] }) {
  const containerRef = useRef<HTMLElement>(null);

  // Suit le flux seulement si l'utilisateur est déjà en bas : on ne lui
  // arrache jamais la lecture d'un message plus haut.
  useEffect(() => {
    const container = containerRef.current;
    if (container === null) return;
    const distance = container.scrollHeight - container.scrollTop - container.clientHeight;
    if (distance < NEAR_BOTTOM_PX) {
      container.scrollTo({ top: container.scrollHeight });
    }
  }, [messages]);

  return (
    <main className="thread" ref={containerRef}>
      {messages.length === 0 ? (
        <p className="thread-empty">
          Active le micro et parle, ou écris un message pour commencer.
        </p>
      ) : (
        messages.map((message) => (
          <div
            key={message.id}
            className={[
              "bubble",
              `bubble--${message.role}`,
              message.streaming ? "bubble--streaming" : "",
              message.interrupted ? "bubble--interrupted" : "",
            ]
              .filter(Boolean)
              .join(" ")}
          >
            {message.text}
          </div>
        ))
      )}
    </main>
  );
}
