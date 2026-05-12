/** Mirrors FastAPI admin responses */

export type ProjectKeyRow = {
  id: number;
  name: string;
  active: boolean;
  used_tokens: number;
  created_at: string;
  /** API may send JSON numbers or stringified decimals */
  budget_usd: string | number;
  spent_usd: string | number;
};

export type UsagePerProject = {
  project_key_id: number;
  project_name: string;
  total_tokens: number;
  total_cost: string;
  last_used: string | null;
};

export type AdminUsage = {
  per_project: UsagePerProject[];
  total_cost: string;
  total_tokens: number;
};

export type CreateKeyResponse = {
  id: number;
  name: string;
  active: boolean;
  reveal_token: string;
  reveal_expires_at: string;
  message?: string;
  /** Set client-side after create; full URL to share */
  revealUrl?: string;
};
