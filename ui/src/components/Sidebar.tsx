import { useState } from "react";
import type { ConversationMeta } from "../api";
import {
  GearIcon,
  PlusIcon,
  TrashIcon,
  DotsIcon,
  PencilIcon,
  SearchIcon,
  BackIcon,
} from "../icons";

interface SidebarProps {
  conversations: ConversationMeta[];
  activeId: string | null;
  filter: string;
  onFilterChange: (value: string) => void;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onRename: (id: string) => void;
  // Settings integration
  view: "chat" | "settings";
  onOpenSettings: () => void;
  onBackToChat: () => void;
  activeSettingCategory: SettingsCategory;
  onSelectSettingCategory: (category: SettingsCategory) => void;
}

export type SettingsCategory =
  | "interface"
  | "providers"
  | "personas"
  | "diagnostic"
  | "support"
  | "feedback";

const SETTINGS_CATEGORIES: ReadonlyArray<readonly [SettingsCategory, string]> = [
  ["interface", "Interface"],
  ["providers", "Fournisseur d'IA"],
  ["personas", "Personas"],
  ["diagnostic", "Diagnostic"],
  ["support", "Soutenir"],
  ["feedback", "Contact"],
];

export function Sidebar({
  conversations,
  activeId,
  filter,
  onFilterChange,
  onSelect,
  onNew,
  onDelete,
  onRename,
  view,
  onOpenSettings,
  onBackToChat,
  activeSettingCategory,
  onSelectSettingCategory,
}: SidebarProps) {
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);

  const visible = conversations.filter((c) =>
    c.title.toLowerCase().includes(filter.trim().toLowerCase()),
  );

  return (
    <aside className="sidebar">
      {menuOpenId !== null && (
        <div className="conv-menu-backdrop" onClick={() => setMenuOpenId(null)} />
      )}

      <div className="sidebar-brand">Timbre</div>

      {view === "chat" ? (
        <>
          <div className="sidebar-search-row">
            <div className="sidebar-search-wrapper">
              <SearchIcon size={14} />
              <input
                className="sidebar-search"
                value={filter}
                onChange={(event) => onFilterChange(event.target.value)}
                placeholder="Rechercher"
                aria-label="Rechercher une conversation"
              />
            </div>
            <button
              type="button"
              className="sidebar-new-btn"
              onClick={onNew}
              title="Nouvelle conversation"
            >
              <PlusIcon size={16} />
            </button>
          </div>

          <nav className="conv-list" aria-label="Conversations">
            {visible.length === 0 ? (
              <p className="conv-empty">Aucune conversation</p>
            ) : (
              visible.map((conversation) => (
                <div
                  key={conversation.id}
                  className={`conv-item ${activeId === conversation.id ? "conv-item--active" : ""}`}
                >
                  <button
                    className="conv-item-title"
                    type="button"
                    onClick={() => onSelect(conversation.id)}
                  >
                    {conversation.title}
                  </button>

                  <div className="conv-item-actions-wrapper">
                    <button
                      type="button"
                      className="conv-item-menu-btn"
                      onClick={() =>
                        setMenuOpenId((prev) => (prev === conversation.id ? null : conversation.id))
                      }
                      title="Actions"
                    >
                      <DotsIcon size={16} />
                    </button>

                    {menuOpenId === conversation.id && (
                      <div className="conv-item-dropdown">
                        <button
                          type="button"
                          className="conv-dropdown-item"
                          onClick={() => {
                            setMenuOpenId(null);
                            onRename(conversation.id);
                          }}
                        >
                          <PencilIcon size={14} />
                          <span>Rename</span>
                        </button>
                        <button
                          type="button"
                          className="conv-dropdown-item conv-dropdown-item--danger"
                          onClick={() => {
                            setMenuOpenId(null);
                            onDelete(conversation.id);
                          }}
                        >
                          <TrashIcon size={14} />
                          <span>Delete Thread</span>
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
          </nav>
        </>
      ) : (
        <>
          <nav className="conv-list" aria-label="Catégories de réglages">
            {SETTINGS_CATEGORIES.map(([id, label]) => (
              <div
                key={id}
                className={`conv-item ${activeSettingCategory === id ? "conv-item--active" : ""}`}
              >
                <button
                  className="conv-item-title"
                  type="button"
                  onClick={() => onSelectSettingCategory(id)}
                >
                  {label}
                </button>
              </div>
            ))}
          </nav>
        </>
      )}

      <div className="sidebar-footer">
        {view === "chat" ? (
          <button type="button" className="sidebar-settings-btn" onClick={onOpenSettings}>
            <GearIcon size={16} />
            Réglages
          </button>
        ) : (
          <button type="button" className="sidebar-settings-btn" onClick={onBackToChat}>
            <BackIcon size={16} />
            Retour
          </button>
        )}
      </div>
    </aside>
  );
}
