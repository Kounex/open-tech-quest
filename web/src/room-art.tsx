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
function OpenShiftArt() {
  return (
    <div className="cluster-art" aria-hidden="true">
      <div className="cluster-label">Application platform</div>
      <div className="cluster-nodes">
        <span>Build</span>
        <i />
        <span>Deploy</span>
        <i />
        <span>Scale</span>
      </div>
      <div className="cluster-base">
        <span>Containers</span>
        <span>Kubernetes</span>
        <span>OpenShift</span>
      </div>
    </div>
  );
}
function AnsibleArt() {
  return (
    <div className="playbook-art" aria-hidden="true">
      <span className="code-comment">One playbook. Repeatable outcomes.</span>
      <code>
        <span>- hosts:</span> your_infrastructure
        <br />
        <span> tasks:</span>
        <br /> - configure
        <br /> - automate
        <br /> - verify
      </code>
      <div className="playbook-result">
        <span /> Consistent by design
      </div>
    </div>
  );
}
function RhelArt() {
  return (
    <div className="terminal-art" aria-hidden="true">
      <div className="terminal-bar">Red Hat Enterprise Linux</div>
      <code>
        <span>$</span> whoami
        <br />
        problem-solver
        <br />
        <span>$</span> systemctl status your-skills
        <br />
        <b>●</b> ready to run
      </code>
      <div className="terminal-foot">The foundation starts here</div>
    </div>
  );
}
function SecurityArt() {
  return (
    <div className="security-art" aria-hidden="true">
      <div className="trust-boundary">
        <span className="trust-label">Trust is verified</span>
        <div className="security-inner">
          <span>Identity</span>
          <span>Policy</span>
          <span>Evidence</span>
        </div>
      </div>
      <div className="security-caption">Observe → investigate → protect</div>
    </div>
  );
}
function AIArt() {
  return (
    <div className="ai-art" aria-hidden="true">
      <div className="ai-input">Your question</div>
      <div className="ai-path" />
      <div className="ai-model">
        <span>Context</span>
        <strong>Model</strong>
        <span>Evaluation</span>
      </div>
      <div className="ai-path" />
      <div className="ai-output">A useful answer</div>
    </div>
  );
}
export function RoomArt({
  room,
  compact = false,
}: {
  room: Room;
  compact?: boolean;
}) {
  const hero = assetUrl(room.theme?.hero_url);
  const key = (room.theme?.layout || room.slug).toLowerCase();
  return (
    <div
      className={`room-art art-${key}${compact ? " compact" : ""}`}
      style={roomThemeStyle(room)}
    >
      {hero ? (
        <img src={hero} alt="" className="room-hero-image" />
      ) : key.includes("openshift") ? (
        <OpenShiftArt />
      ) : key.includes("ansible") ? (
        <AnsibleArt />
      ) : key.includes("rhel") || key.includes("linux") ? (
        <RhelArt />
      ) : key.includes("security") ? (
        <SecurityArt />
      ) : key === "ai" ? (
        <AIArt />
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
