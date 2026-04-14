/** Mirrors FastAPI admin responses */

export type ProjectKeyRow = {
  id: number;
  name: string;
  active: boolean;
  used_tokens: number;
  created_at: string;
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
  key: string;
  name: string;
  active: boolean;
  message?: string;
};
