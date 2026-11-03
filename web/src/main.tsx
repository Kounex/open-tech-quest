import { decode } from "./api";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { usePath, useResource } from "./hooks";
import type { Bootstrap } from "./types";
import { Link, Notice } from "./ui";
import { Lobby, RoomPage } from "./participant";
import { StandingsPage, Stage } from "./standings";
import { Admin } from "./admin";
import "./style.css";
const branding = "/plugins/open_tech_quest/assets/branding";
const fonts = document.createElement("link");
fonts.rel = "stylesheet";
fonts.href = `${branding}/fonts.css`;
document.head.appendChild(fonts);
function App() {
  const path = usePath();
  const bootstrap = useResource<Bootstrap>("/bootstrap", 10000);
  const data = bootstrap.data;
  const stage = path.replace(/\/$/, "") === "/quest/stage";
  if (stage) return <Stage />;
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="masthead">
        <div className="masthead-inner">
          <Link
            href="/quest"
            className="brand"
            aria-label="Open Tech Quest home"
          >
            <img src={`${branding}/quest-mark.png`} alt="Open Tech Quest" />
          </Link>
          <div className="event-label">
            Red Hat Hands-On Day<span>Darmstadt</span>
          </div>
          <nav aria-label="Main navigation">
            <Link
              href="/quest"
              className={
                path === "/quest" ||
                path === "/quest/" ||
                path.includes("/rooms/")
                  ? "active"
                  : ""
              }
            >
              The rooms
            </Link>
            <Link
              href="/quest/standings"
              className={path.includes("standings") ? "active" : ""}
            >
              Standings
            </Link>
            {data?.viewer.admin && (
              <Link
                href="/quest/admin"
                className={path.includes("admin") ? "active" : ""}
              >
                Organize
              </Link>
            )}
          </nav>
          <div className="account-nav">
            {data?.viewer.authenticated ? (
              <>
                <span>{data.viewer.team_name || data.viewer.name}</span>
                <a href="/settings">Account</a>
              </>
            ) : (
              <>
                <a href="/login?next=/quest">Sign in</a>
                <a className="register-link" href="/register?next=/quest">
                  Register
                </a>
              </>
            )}
          </div>
        </div>
      </header>
      <main id="main" className="app-main">
        {!data ? (
          bootstrap.error ? (
            <Notice tone="error" retry={() => void bootstrap.refresh()}>
              {bootstrap.error}
            </Notice>
          ) : (
            <p className="loading" role="status">
              Connecting to the quest…
            </p>
          )
        ) : (
          <>
            {bootstrap.error && (
              <Notice tone="error" retry={() => void bootstrap.refresh()}>
                Showing last saved event information. {bootstrap.error}
              </Notice>
            )}
            {path === "/quest" || path === "/quest/" ? (
              <Lobby data={data} onRefresh={bootstrap.refresh} />
            ) : path.startsWith("/quest/rooms/") ? (
              <RoomPage
                slug={decode(
                  path.slice("/quest/rooms/".length).replace(/\/$/, ""),
                )}
                data={data}
                onRefresh={bootstrap.refresh}
              />
            ) : path === "/quest/standings" ? (
              <StandingsPage />
            ) : path === "/quest/admin" ? (
              data.viewer.admin ? (
                <Admin />
              ) : (
                <Notice tone="error">
                  Organizer access is required.{" "}
                  <Link href="/quest">Return to the rooms</Link>
                </Notice>
              )
            ) : (
              <Notice>
                This page isn’t part of the quest.{" "}
                <Link href="/quest">Return to the rooms</Link>
              </Notice>
            )}
          </>
        )}
      </main>
      <footer className="app-footer">
        <img src={`${branding}/redhat-on-light.svg`} alt="Red Hat" />
        <span>Open Tech Quest · Learn together. Solve together.</span>
        <a href="/settings">Account settings</a>
        {data?.viewer.team_id && <a href="/team">Your team</a>}
      </footer>
    </>
  );
}
const root =
  document.getElementById("root") || document.getElementById("quest-root");
if (root)
  createRoot(root).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
