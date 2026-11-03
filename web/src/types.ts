export type Phase = "draft" | "live" | "paused" | "closed" | "published";
export interface QuestEvent {
  name: string;
  status: Phase;
  start_at: string | null;
  end_at: string | null;
  paused_at: string | null;
  rosters_release_at: string | null;
  room_clock: "explicit" | "event";
  overall_clock: "event" | "team";
  server_now: string;
  results_published: boolean;
}
export interface Viewer {
  authenticated: boolean;
  id: number | null;
  name: string | null;
  team_id: number | null;
  team_name: string | null;
  admin: boolean;
}
export interface Step {
  id: number;
  title: string;
  position: number;
  state: "locked" | "available" | "solved";
  solved_at: string | null;
}
export interface Progress {
  solved: number;
  total: number;
  started_at: string | null;
  elapsed_ms: number | null;
  milestone_elapsed_ms: number | null;
  status: "not_started" | "active" | "complete";
}
export interface Room {
  id: number;
  slug: string;
  name: string;
  subtitle: string;
  description: string;
  position: number;
  theme: {
    accent?: string;
    logo_url?: string;
    hero_url?: string;
    layout?: string;
  };
  steps: Step[];
  progress: Progress;
}
export interface Bootstrap {
  event: QuestEvent;
  viewer: Viewer;
  rooms: Room[];
}
export interface RoomProgress {
  room_id: number;
  solved: number;
  total: number;
  milestone_elapsed_ms: number | null;
  rank: number | null;
  complete: boolean;
}
export interface StandingTeam {
  id: number;
  name: string;
  rank: number | null;
  total: number;
  overall_elapsed_ms: number | null;
  room_progress: RoomProgress[];
}
export interface Standings {
  event: QuestEvent;
  rooms: Room[];
  teams: StandingTeam[];
  room_leaders: Record<string, StandingTeam[]>;
  as_of: string;
}
export interface Projector {
  view: "overview" | "room" | "overall" | "awards";
  room_slug: string | null;
}
export interface Team {
  id: number;
  name: string;
  user_ids: number[];
  excluded: boolean;
  name_locked: boolean;
  ready_count: number;
}
export interface Participant {
  id: number;
  name: string;
  email: string;
  team_id: number | null;
  ready_at: string | null;
  late: boolean;
  banned: boolean;
}
export interface AdminState {
  onboarding: AttendanceState;
  demo: DemoContentState;
  event: QuestEvent;
  rooms: Room[];
  available_challenges: {
    id: number;
    name: string;
    state: string;
    room_slug: string | null;
  }[];
  teams: Team[];
  participants: Participant[];
  audit: {
    id: number;
    actor_id: number;
    action: string;
    detail: unknown;
    created_at: string;
  }[];
  standings: Standings;
  projector: Projector;
}
export interface DemoContentState {
  active: boolean;
  challenge_count: number;
  can_load: boolean;
  can_unload: boolean;
  reason: string | null;
}
export interface Challenge {
  id: number;
  name: string;
  description: string;
  files: string[];
  hints: { id: number; cost: number; content?: string }[];
  max_attempts?: number;
  attempts?: number;
  connection_info?: string;
}
export interface Allocation {
  groups: { name: string; user_ids: number[] }[];
}
declare global {
  interface Window {
    QUEST_INIT?: { csrfNonce?: string; viewer?: Viewer };
  }
}

export type OnboardingPhase = "check_in" | "closed" | "naming" | "finalized";
export interface Onboarding {
  phase: OnboardingPhase;
  team_size: number;
  ready_at: string | null;
  late: boolean;
  roster_released: boolean;
  team: {
    id: number;
    name: string;
    name_locked: boolean;
    members: { id: number; name: string; ready_at: string | null }[];
  } | null;
  can_ready: boolean;
  can_name: boolean;
}
export interface AttendanceState {
  phase: OnboardingPhase;
  team_size: number;
  ready_count: number;
  pending_count: number;
  unassigned_ready_count: number;
  unnamed_count: number;
  can_start: boolean;
  start_reason: string | null;
}
export interface AttendancePlan {
  fingerprint: string;
  groups: { team_id: number | null; name: string; user_ids: number[] }[];
  moves: { user_id: number; from_team_id: number | null; to_group: number }[];
  unassigned_user_ids: number[];
  warnings: string[];
}
