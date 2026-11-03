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
const artwork: Record<
  string,
  { scene: string; product: string; topic: string; alt: string }
> = {
  openshift: {
    scene: "openshift",
    product: "Red Hat OpenShift",
    topic: "Container orchestration",
    alt: "Application deployment branching into groups of container workloads on a red platform",
  },
  ansible: {
    scene: "ansible",
    product: "Red Hat Ansible",
    topic: "Playbook automation",
    alt: "An automation playbook coordinating server, laptop and network endpoints",
  },
  rhel: {
    scene: "rhel",
    product: "Red Hat Enterprise Linux",
    topic: "Linux systems and services",
    alt: "A Linux terminal and running services on a red operating-system foundation",
  },
  security: {
    scene: "security",
    product: "Security",
    topic: "Protect cloud-native workloads",
    alt: "A red shield protecting container workloads and a verified software-package chain",
  },
  ai: {
    scene: "ai",
    product: "Red Hat AI",
    topic: "Models and inference",
    alt: "Data flowing through a model processor into an inference response",
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
  const identity = artwork[room.slug.toLowerCase()] || art;
  const hero = customHero || (art && `${artBase}/${art.scene}-hero.webp`);
  return (
    <div
      className={`room-art art-${key}${compact ? " compact" : ""}${!customHero && art ? " has-bundled-art" : ""}`}
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
      {!customHero && art && (
        <div className="room-art-identity" aria-hidden="true">
          <RoomLogo room={room} />
          <div>
            <span className="product-name">{identity.product}</span>
            <span className="product-topic">{identity.topic}</span>
          </div>
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
