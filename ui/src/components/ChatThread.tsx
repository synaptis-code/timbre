import { useEffect, useRef } from "react";

export interface ChatMessage {
  id: number;
  role: "user" | "ai" | "error";
  text: string;
  /** Bulle IA encore en cours de streaming (le prochain ai_chunk s'y ajoute). */
  streaming?: boolean;
  /** Tour coupé (Stop ou nouvelle prise de parole) : affiché tel quel, marqué. */
  interrupted?: boolean;
  /** Une capture d'écran accompagnait ce message. */
  withImage?: boolean;
}

const NEAR_BOTTOM_PX = 160;

export function ChatThread({ messages, persona }: { messages: ChatMessage[]; persona: string }) {
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
      <div className="thread-inner">
        {messages.length === 0 ? (
          <div className="thread-empty">
            <h2 className="thread-empty-title">Comment puis-je t'aider&nbsp;?</h2>
            <p className="thread-empty-hint">
              Active le micro et parle, partage ton écran, ou écris un message.
            </p>
          </div>
        ) : (
          messages.map((message) =>
            message.role === "error" ? (
              <p key={message.id} className="msg-error">
                {message.text}
              </p>
            ) : message.role === "user" ? (
              <div
                key={message.id}
                className={`msg-user ${message.withImage ? "msg-user--image" : ""}`}
              >
                {message.text}
              </div>
            ) : (
              <div key={message.id} className="msg-ai">
                <p className="eyebrow msg-ai-label">{persona}</p>
                <div
                  className={`msg-ai-text ${message.streaming ? "msg--streaming" : ""} ${
                    message.interrupted ? "msg--interrupted" : ""
                  }`}
                >
                  {message.text}
                </div>
              </div>
            ),
          )
        )}
      </div>
    </main>
  );
}
