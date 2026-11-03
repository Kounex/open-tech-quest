import type { CSSProperties } from "react";
import type { Room } from "./types";
import { assetUrl } from "./api";
export function roomThemeStyle(room: Room): CSSProperties {
  return {
    "--room-accent": /^#[0-9a-fA-F]{6}$/.test(room.theme?.accent || "")
      ? room.theme.accent
      : "#008b9a",
  } as CSSProperties;
}
const artwork: Record<string, { scene: string; alt: string }> = {
  openshift: {
    scene: "openshift",
    alt: "An illustrated deployment workshop with connected server bays and a service gateway",
  },
  ansible: {
    scene: "ansible",
    alt: "An illustrated automation control room coordinating connected workstations",
  },
  rhel: {
    scene: "rhel",
    alt: "An illustrated Linux engine room with server racks and a maintenance bench",
  },
  security: {
    scene: "security",
    alt: "An illustrated security operations room with verification stations and a protected gateway",
  },
  ai: {
    scene: "ai",
    alt: "An illustrated AI research lab connecting data preparation, compute and evaluation",
  },
};
const artBase = "/plugins/open_tech_quest/assets/branding/room-art";
export function RoomArt({
  room,
  compact = false,
}: {
  room: Room;
  compact?: boolean;
}) {
  const customHero = assetUrl(room.theme?.hero_url);
  const key = (room.theme?.layout || room.slug).toLowerCase();
  const art = artwork[key];
  const hero = customHero || (art && `${artBase}/${art.scene}-hero.webp`);
  return (
    <div
      className={`room-art art-${key}${compact ? " compact" : ""}`}
      style={roomThemeStyle(room)}
    >
      {hero ? (
        <img
          src={hero}
          srcSet={
            !customHero && art
              ? `${artBase}/${art.scene}-card.webp 640w, ${hero} 1536w`
              : undefined
          }
          sizes={
            compact
              ? "(max-width: 700px) 90vw, (max-width: 1150px) 44vw, 30vw"
              : "(max-width: 700px) 90vw, 44vw"
          }
          width={1536}
          height={1024}
          alt={!compact && !customHero && art ? art.alt : ""}
          className="room-hero-image"
          loading={compact ? "lazy" : "eager"}
          fetchPriority={compact ? "auto" : "high"}
          decoding="async"
        />
      ) : (
        <div className="custom-art">
          <span>{room.name}</span>
          <p>{room.subtitle || "A new path for your team"}</p>
        </div>
      )}
    </div>
  );
}
export function RoomLogo({ room }: { room: Room }) {
  const key = room.slug.toLowerCase();
  const defaults: Record<string, string> = {
    openshift: "openshift.png",
    ansible: "ansible.png",
    rhel: "rhel.png",
    security: "openshift.png",
    ai: "ai.webp",
  };
  const logo = assetUrl(
    room.theme?.logo_url ||
      (defaults[key]
        ? `/plugins/open_tech_quest/assets/branding/${defaults[key]}`
        : undefined),
  );
  return logo ? <img className="room-logo" src={logo} alt="" /> : null;
}
