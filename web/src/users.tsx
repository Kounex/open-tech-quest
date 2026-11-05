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
type UserAction = {
  path: string;
  method: "PATCH" | "DELETE";
  body: Record<string, unknown>;
  message: string;
};

export function Users({ onChanged }: { onChanged: () => Promise<void> }) {
  const resource = useResource<{ users: ManagedUser[] }>("/admin/users", 15000);
  const [query, setQuery] = useState(""),
    [role, setRole] = useState("all"),
    [busy, setBusy] = useState<number | null>(null),
    [message, setMessage] = useState(""),
    [error, setError] = useState("");
  async function perform(user: ManagedUser, action: UserAction) {
    setBusy(user.id);
    setMessage("");
    setError("");
    try {
      await request(`/admin/users/${user.id}${action.path}`, action.method, {
        ...action.body,
        confirm: true,
        identity: user.identity,
      });
      await Promise.all([resource.refresh(), onChanged()]);
      setMessage(action.message);
    } catch (error) {
      setError((error as Error).message);
      throw error;
    } finally {
      setBusy(null);
    }
  }
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
          <h2>Users and account access</h2>
          <p>
            Manage participant and challenge maintainer accounts. Bans deny
            access and exclude that account's contributions from team progress
            and rankings while retaining all recorded history. Unused accounts
            can be deleted when safe.
          </p>
        </div>
        <a href="/admin/submissions" className="button secondary">
          Submission history
        </a>
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
      {error && (
        <Notice tone="error" retry={() => void resource.refresh()}>
          {error}
        </Notice>
      )}
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
        <div className="managed-users-table user-lifecycle-table">
          <table>
            <thead>
              <tr>
                <th scope="col">Account</th>
                <th scope="col">Role</th>
                <th scope="col">Team and attendance</th>
                <th scope="col">Room access</th>
                <th scope="col">Account access</th>
                <th scope="col">Permanent removal</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => {
                const target =
                  user.role === "maintainer" ? "participant" : "maintainer";
                const targetActive = user.banned;
                const disabled = busy !== null || !user.identity;
                return (
                  <tr key={`${user.id}-${user.identity}`}>
                    <th scope="row">
                      {user.name}
                      <small>{user.email}</small>
                      <small>
                        <a
                          className="text-button user-records"
                          href={`/admin/users/${user.id}`}
                        >
                          View account records
                        </a>
                      </small>
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
                    {user.role === "administrator" ? (
                      <td colSpan={3}>
                        <span className="meta">
                          Native administrator · Read-only here
                        </span>
                        <a
                          className="text-button"
                          href={`/admin/users/${user.id}`}
                        >
                          Manage in CTFd
                        </a>
                      </td>
                    ) : (
                      <>
                        <td className="user-control-cell">
                          <Confirm
                            key={`role-${user.identity}-${user.role}-${user.can_change_role}`}
                            label={
                              target === "maintainer"
                                ? "Make maintainer"
                                : "Return to participant"
                            }
                            description={
                              target === "maintainer"
                                ? `Give ${user.name} permission to configure rooms and author challenges? This makes them staff, clears attendance and removes unused provisional team membership. They will not participate in teams or awards.`
                                : `Return ${user.name} to the Participant role? Maintainer access ends immediately. The account will be unassigned and unconfirmed, and must follow the current attendance and roster rules before joining the quest.`
                            }
                            disabled={disabled || !user.can_change_role}
                            onConfirm={() =>
                              perform(user, {
                                path: "/role",
                                method: "PATCH",
                                body: { role: target },
                                message: `${user.name} is now ${target === "maintainer" ? "a challenge maintainer" : "a participant"}`,
                              })
                            }
                          />
                          {!user.can_change_role && (
                            <small className="role-change-reason">
                              {user.role_change_reason ||
                                "Role changes are not available for this account"}
                            </small>
                          )}
                        </td>
                        <td className="user-control-cell">
                          <Confirm
                            key={`access-${user.identity}-${user.banned}-${user.can_set_active}`}
                            label={
                              targetActive ? "Unban account" : "Ban account"
                            }
                            description={
                              targetActive
                                ? `Unban ${user.name}'s account? Access resumes under its current role. Eligible retained contributions can count again, with each challenge counted only once per team. This creates no new attendance confirmation or team assignment, and all recorded history stays saved.`
                                : `Ban ${user.name}'s account? Access is denied, and any contributions from this account stop counting toward team progress, challenge availability and rankings. Teammates may re-solve affected challenges. All recorded history is retained. An unused provisional assignment and check-in may be cleared before optimization; established rosters remain saved.`
                            }
                            disabled={disabled || !user.can_set_active}
                            danger={!targetActive}
                            onConfirm={() =>
                              perform(user, {
                                path: "/access",
                                method: "PATCH",
                                body: { active: targetActive },
                                message: targetActive
                                  ? `${user.name}'s account unbanned; eligible retained contributions can count again`
                                  : `${user.name}'s account banned; their contributions no longer count`,
                              })
                            }
                          />
                          {!user.can_set_active && (
                            <small className="role-change-reason">
                              {user.access_reason ||
                                "Account access cannot be changed here"}
                            </small>
                          )}
                        </td>
                        <td className="user-control-cell user-delete-cell">
                          <Confirm
                            key={`delete-${user.identity}-${user.can_delete}`}
                            label="Delete account"
                            description={`Permanently delete ${user.name}'s unused account? This cannot be undone. Credentials, attendance and maintainer access for this account are removed. Provisional membership is detached while the team and authored challenges remain. Accounts with competition history or frozen roster membership cannot be deleted.`}
                            disabled={disabled || !user.can_delete}
                            danger
                            onConfirm={() =>
                              perform(user, {
                                path: "",
                                method: "DELETE",
                                body: {},
                                message: `${user.name}'s account deleted; team and authored challenges preserved`,
                              })
                            }
                          />
                          {!user.can_delete && (
                            <small className="role-change-reason">
                              {user.delete_reason ||
                                "This account cannot be deleted"}
                            </small>
                          )}
                        </td>
                      </>
                    )}
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
