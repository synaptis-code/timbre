/** Icônes vectorielles inline (trait, currentColor) — zéro média embarqué. */

interface IconProps {
  size?: number;
}

function svgProps(size: number | undefined) {
  return {
    width: size ?? 18,
    height: size ?? 18,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round",
    strokeLinejoin: "round",
  } as const;
}

export function MicIcon({ size }: IconProps) {
  return (
    <svg {...svgProps(size)} aria-hidden="true">
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M5 11a7 7 0 0 0 14 0" />
      <path d="M12 18v3" />
    </svg>
  );
}

export function ScreenIcon({ size }: IconProps) {
  return (
    <svg {...svgProps(size)} aria-hidden="true">
      <rect x="3" y="4" width="18" height="13" rx="2" />
      <path d="M8 21h8" />
      <path d="M12 17v4" />
    </svg>
  );
}

export function StopIcon({ size }: IconProps) {
  return (
    <svg {...svgProps(size)} aria-hidden="true">
      <rect x="7" y="7" width="10" height="10" rx="1.5" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function SendIcon({ size }: IconProps) {
  return (
    <svg {...svgProps(size)} aria-hidden="true">
      <path d="M12 19V5" />
      <path d="m6 11 6-6 6 6" />
    </svg>
  );
}

export function PlusIcon({ size }: IconProps) {
  return (
    <svg {...svgProps(size)} aria-hidden="true">
      <path d="M12 5v14" />
      <path d="M5 12h14" />
    </svg>
  );
}

export function GearIcon({ size }: IconProps) {
  return (
    <svg {...svgProps(size)} aria-hidden="true">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.87-.34 1.7 1.7 0 0 0-1.03 1.56V21a2 2 0 1 1-4 0v-.09a1.7 1.7 0 0 0-1.12-1.56 1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.7 1.7 0 0 0 .34-1.87 1.7 1.7 0 0 0-1.56-1.03H3a2 2 0 1 1 0-4h.09A1.7 1.7 0 0 0 4.65 8.9a1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.7 1.7 0 0 0 1.87.34h.08A1.7 1.7 0 0 0 10.12 3V3a2 2 0 1 1 4 0v.09c0 .68.4 1.3 1.03 1.56.6.27 1.3.14 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.7 1.7 0 0 0-.34 1.87v.08c.26.63.88 1.03 1.56 1.03H21a2 2 0 1 1 0 4h-.09c-.68 0-1.3.4-1.56 1.03Z" />
    </svg>
  );
}

export function TrashIcon({ size }: IconProps) {
  return (
    <svg {...svgProps(size)} aria-hidden="true">
      <path d="M4 7h16" />
      <path d="M10 11v6M14 11v6" />
      <path d="M6 7l1 13h10l1-13" />
      <path d="M9 7V4h6v3" />
    </svg>
  );
}

export function BackIcon({ size }: IconProps) {
  return (
    <svg {...svgProps(size)} aria-hidden="true">
      <path d="M15 6l-6 6 6 6" />
    </svg>
  );
}

export function SlidersIcon({ size }: IconProps) {
  return (
    <svg {...svgProps(size)} aria-hidden="true">
      <line x1="4" y1="6" x2="20" y2="6" />
      <line x1="4" y1="12" x2="20" y2="12" />
      <line x1="4" y1="18" x2="20" y2="18" />
      <circle cx="8" cy="6" r="2.2" fill="currentColor" />
      <circle cx="16" cy="12" r="2.2" fill="currentColor" />
      <circle cx="10" cy="18" r="2.2" fill="currentColor" />
    </svg>
  );
}

export function CameraIcon({ size }: IconProps) {
  return (
    <svg {...svgProps(size)} aria-hidden="true">
      <path d="M23 7l-7 5 7 5V7z" />
      <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
    </svg>
  );
}

export function UploadIcon({ size }: IconProps) {
  return (
    <svg {...svgProps(size)} aria-hidden="true">
      <rect x="3" y="3" width="18" height="18" rx="4" />
      <path d="M12 16V8" />
      <path d="m9 11 3-3 3 3" />
    </svg>
  );
}

export function XIcon({ size }: IconProps) {
  return (
    <svg {...svgProps(size)} aria-hidden="true">
      <path d="M18 6L6 18M6 6l12 12" />
    </svg>
  );
}

export function HeadphonesIcon({ size }: IconProps) {
  return (
    <svg {...svgProps(size)} aria-hidden="true">
      <path d="M3 18v-6a9 9 0 0 1 18 0v6" />
      <path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z" />
    </svg>
  );
}

export function DotsIcon({ size }: IconProps) {
  return (
    <svg {...svgProps(size)} aria-hidden="true">
      <circle cx="12" cy="12" r="1.5" fill="currentColor" />
      <circle cx="6" cy="12" r="1.5" fill="currentColor" />
      <circle cx="18" cy="12" r="1.5" fill="currentColor" />
    </svg>
  );
}

export function PencilIcon({ size }: IconProps) {
  return (
    <svg {...svgProps(size)} aria-hidden="true">
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
    </svg>
  );
}

export function ChevronDownIcon({ size }: IconProps) {
  return (
    <svg {...svgProps(size)} aria-hidden="true">
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
}

export function UserIcon({ size }: IconProps) {
  return (
    <svg {...svgProps(size)} aria-hidden="true">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  );
}

export function SearchIcon({ size }: IconProps) {
  return (
    <svg {...svgProps(size)} aria-hidden="true">
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.3-4.3" />
    </svg>
  );
}






