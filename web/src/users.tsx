import { useState } from "react";
import { dateTime, request } from "./api";
import { useResource } from "./hooks";
import type { ManagedUser } from "./types";
import { Confirm, Empty, Notice } from "./ui";
const roleNames = {
  participant: "Participant",
  maintainer: "Challenge maintainer",
  administrator: "Administrator",
};
export function Users({ onChanged }: { onChanged: () => Promise<void> }) {
  const resource = useResource<{ users: ManagedUser[] }>("/admin/users", 15000);
  const [query, setQuery] = useState(""),
    [role, setRole] = useState("all"),
    [busy, setBusy] = useState<number | null>(null),
    [message, setMessage] = useState("");
  if (!resource.data)
    return resource.error ? (
      <Notice tone="error" retry={() => void resource.refresh()}>
        {resource.error}
      </Notice>
    ) : (
      <p role="status">Loading user accounts…</p>
    );
  const users = resource.data.users.filter(
    (user) =>
      (role === "all" || user.role === role) &&
      `${user.name} ${user.email}`
        .toLocaleLowerCase()
        .includes(query.toLocaleLowerCase()),
  );
  return (
    <>
      <div className="section-heading">
        <div>
          <h2>Users and room access</h2>
          <p>
            Participants use personal accounts. Challenge maintainers prepare
            room content; administrators manage the whole event.
          </p>
        </div>
      </div>
      <div className="users-toolbar">
        <label>
          <span className="sr-only">Search users by name or email</span>
          <input
            type="search"
            placeholder="Search names or email"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <label>
          <span className="sr-only">Filter users by role</span>
          <select
            value={role}
            onChange={(event) => setRole(event.target.value)}
          >
            <option value="all">All roles</option>
            <option value="participant">Participants</option>
            <option value="maintainer">Challenge maintainers</option>
            <option value="administrator">Administrators</option>
          </select>
        </label>
        <span className="meta">
          {users.length} of {resource.data.users.length} accounts
        </span>
      </div>
      {message && <Notice tone="success">{message}</Notice>}
      {resource.error && (
        <Notice tone="error" retry={() => void resource.refresh()}>
          Showing saved accounts. {resource.error}
        </Notice>
      )}
      {!users.length ? (
        <Empty title="No matching accounts">
          Change the search or role filter. New participants register with their
          own native account.
        </Empty>
      ) : (
        <div className="managed-users-table">
          <table>
            <thead>
              <tr>
                <th scope="col">Account</th>
                <th scope="col">Role</th>
                <th scope="col">Team and attendance</th>
                <th scope="col">Room access</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => {
                const target =
                  user.role === "maintainer" ? "participant" : "maintainer";
                return (
                  <tr key={user.id}>
                    <th scope="row">
                      {user.name}
                      <small>{user.email}</small>
                      {user.banned && (
                        <span className="user-banned">Banned</span>
                      )}
                    </th>
                    <td>{roleNames[user.role]}</td>
                    <td>
                      {user.team_name || "Unassigned"}
                      <small>
                        {user.role !== "participant"
                          ? "Staff account"
                          : user.ready_at
                            ? `Checked in ${dateTime(user.ready_at)}`
                            : "Not checked in"}
                      </small>
                    </td>
                    <td>
                      {user.role === "administrator" ? (
                        <>
                          <span className="meta">
                            Native administrator · Read-only here
                          </span>
                          <a
                            className="text-button"
                            href={`/admin/users/${user.id}`}
                          >
                            Manage in CTFd
                          </a>
                        </>
                      ) : (
                        <>
                          <Confirm
                            key={`${user.id}-${user.role}-${user.can_change_role}`}
                            label={
                              target === "maintainer"
                                ? "Make maintainer"
                                : "Remove maintainer access"
                            }
                            description={
                              target === "maintainer"
                                ? `Give ${user.name} permission to configure rooms and author challenges? This makes them staff, clears attendance and removes unused provisional team membership. They will not participate in teams or awards.`
                                : `Return ${user.name} to Participant? Room management access ends immediately. The account remains unassigned and unconfirmed; ordinary attendance and roster rules apply.`
                            }
                            disabled={busy !== null || !user.can_change_role}
                            onConfirm={async () => {
                              setBusy(user.id);
                              setMessage("");
                              try {
                                await request(
                                  `/admin/users/${user.id}/role`,
                                  "PATCH",
                                  { role: target, confirm: true },
                                );
                                await Promise.all([
                                  resource.refresh(),
                                  onChanged(),
                                ]);
                                setMessage(
                                  `${user.name} is now ${target === "maintainer" ? "a challenge maintainer" : "a participant"}`,
                                );
                              } finally {
                                setBusy(null);
                              }
                            }}
                          />
                          {!user.can_change_role && (
                            <small className="role-change-reason">
                              {user.role_change_reason ||
                                "Role changes are not available for this account"}
                            </small>
                          )}
                        </>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
