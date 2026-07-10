import type { ConversationMeta } from "../api";
import { GearIcon, PlusIcon, TrashIcon } from "../icons";
import type { ConnectionStatus } from "../ws";

interface SidebarProps {
  conversations: ConversationMeta[];
  activeId: string | null;
  filter: string;
  status: ConnectionStatus;
  onFilterChange: (value: string) => void;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onOpenSettings: () => void;
}

export function Sidebar({
  conversations,
  activeId,
  filter,
  status,
  onFilterChange,
  onSelect,
  onNew,
  onDelete,
  onOpenSettings,
}: SidebarProps) {
  const visible = conversations.filter((c) =>
    c.title.toLowerCase().includes(filter.trim().toLowerCase()),
  );

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">Timbre</div>

      <button type="button" className="btn-primary sidebar-new" onClick={onNew}>
        <PlusIcon size={16} />
        Nouvelle conversation
      </button>

      <input
        className="sidebar-search"
        value={filter}
        onChange={(event) => onFilterChange(event.target.value)}
        placeholder="Rechercher"
        aria-label="Rechercher une conversation"
      />

      <nav className="conv-list" aria-label="Conversations">
        {visible.length === 0 ? (
          <p className="conv-empty">Aucune conversation</p>
        ) : (
          visible.map((conversation) => (
            <div
              key={conversation.id}
              className={`conv-item ${conversation.id === activeId ? "conv-item--active" : ""}`}
            >
              <button
                type="button"
                className="conv-item-title"
                onClick={() => onSelect(conversation.id)}
                title={conversation.title}
              >
                {conversation.title}
              </button>
              <button
                type="button"
                className="conv-item-delete"
                onClick={() => onDelete(conversation.id)}
                title="Supprimer la conversation"
                aria-label={`Supprimer « ${conversation.title} »`}
              >
                <TrashIcon size={14} />
              </button>
            </div>
          ))
        )}
      </nav>

      <div className="sidebar-footer">
        <button type="button" className="btn-ghost" onClick={onOpenSettings}>
          <GearIcon size={16} />
          Réglages
        </button>
        <span className={`conn-dot conn-dot--${status}`} title={`Connexion : ${status}`} />
      </div>
    </aside>
  );
}
