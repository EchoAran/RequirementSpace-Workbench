/**
 * Version Control API Types.
 * 对应后端 version_control 模块的 HTTP 契约（Branch/Commit/Diff）。
 */

export interface BranchPermissions {
  can_write: boolean;
  can_delete: boolean;
  can_rename: boolean;
  is_protected: boolean;
}

export interface WorkspaceDirtySummary {
  is_dirty: boolean;
  modified_entities_count: number;
}

export interface BranchSummary {
  id: number;
  public_id: string;
  project_id: number;
  name: string;
  description?: string | null;
  head_commit_id?: number | null;
  head_commit_public_id?: string | null;
  source_commit_id?: number | null;
  source_commit_public_id?: string | null;
  is_protected: boolean;
  is_default: boolean;
  status: string;
  created_at: string;
  updated_at: string;
  permissions?: BranchPermissions | null;
  workspace_dirty?: WorkspaceDirtySummary | null;
}

export interface CommitSummary {
  id: number;
  public_id: string;
  short_id: string;
  message: string;
  state_hash: string;
  schema_version: string;
  summary?: Record<string, number> | null;
  author_user_id?: number | null;
  author_email?: string | null;
  created_at: string;
  parent_ids: number[];
  parent_public_ids: string[];
  is_merge: boolean;
  branch_public_ids: string[];
  branch_names: string[];
}

export interface CommitListResponse {
  commits: CommitSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface CommitDetail extends CommitSummary {
  state?: Record<string, unknown> | null;
}

export interface DiffRefInfo {
  kind: 'commit' | 'branch' | 'workspace';
  label: string;
  public_id?: string | null;
  branch_ref?: string | null;
  branch_name?: string | null;
  branch_is_protected: boolean;
}

export interface TextDiffBlock {
  kind: 'replace' | 'add' | 'remove';
  before_lines: string[];
  after_lines: string[];
}

export type DiffChangeType =
  | 'entity_added'
  | 'entity_removed'
  | 'entity_updated'
  | 'field_changed'
  | 'relation_added'
  | 'relation_removed'
  | 'ordered_item_moved';

export interface DiffEntry {
  change_type: DiffChangeType;
  entity_type: string;
  entity_uuid: string;
  entity_name: string;
  parent_uuid?: string | null;
  parent_type?: string | null;
  path: string;
  field?: string | null;
  before?: unknown;
  after?: unknown;
  text_blocks: TextDiffBlock[];
  relation_type?: string | null;
  related_entity_type?: string | null;
  related_entity_uuid?: string | null;
  related_entity_name?: string | null;
  before_position?: number | null;
  after_position?: number | null;
}

export interface DiffTypeSummary {
  added: number;
  removed: number;
  modified: number;
}

export interface DiffSummary {
  by_type: Record<string, DiffTypeSummary>;
  total_added: number;
  total_removed: number;
  total_modified: number;
}

export interface DiffResult {
  base?: DiffRefInfo | null;
  target?: DiffRefInfo | null;
  summary: DiffSummary;
  entries: DiffEntry[];
  total: number;
  limit: number;
  offset: number;
}

export interface EntityDiffResult {
  base?: DiffRefInfo | null;
  target?: DiffRefInfo | null;
  entity_uuid: string;
  entity_type: string;
  entity_name: string;
  base_value?: Record<string, unknown> | null;
  target_value?: Record<string, unknown> | null;
  entries: DiffEntry[];
}

export interface CommitCreateRequest {
  message: string;
  expected_head_commit_id?: number;
  expected_head_commit_public_id?: string;
}

// ==========================================
// Merge Request Types
// ==========================================

export interface MergeReviewResponse {
  id: number;
  reviewer_user_id?: number | null;
  reviewer_email?: string | null;
  decision: string;         // "approved" | "changes_requested"
  comment: string;
  status: string;            // "active" | "stale"
  stale_reason?: string | null;
  created_at: string;
  updated_at: string;
}

export interface MergeCommentResponse {
  id: number;
  author_user_id?: number | null;
  author_email?: string | null;
  entity_uuid?: string | null;
  field_path?: string | null;
  relation_key?: string | null;
  comment: string;
  required: boolean;
  status: string;
  effective_source_head_id?: number | null;
  expired_by_source_head_id?: number | null;
  created_at: string;
}

export interface MRDiffSummary {
  by_type: Record<string, DiffTypeSummary>;
  total_added: number;
  total_removed: number;
  total_modified: number;
}

export interface MergeRequestSummary {
  id: number;
  public_id: string;
  project_id: number;
  title: string;
  description?: string | null;
  source_branch_name: string;
  target_branch_name: string;
  source_branch_public_id?: string | null;
  target_branch_public_id?: string | null;
  status: string;            // "open" | "approved" | "changes_requested" | "mergeable" | "merged" | "closed"
  author_user_id?: number | null;
  author_email?: string | null;
  diff_summary?: MRDiffSummary | null;
  active_review_count: number;
  total_comments: number;
  source_head_short?: string | null;
  target_head_short?: string | null;
  created_at: string;
  updated_at: string;
}

export interface MergeRequestDetail extends MergeRequestSummary {
  source_head_commit_id?: number | null;
  source_head_public_id?: string | null;
  target_head_commit_id?: number | null;
  target_head_public_id?: string | null;
  merge_base_commit_id?: number | null;
  merge_base_public_id?: string | null;
  merged_commit_id?: number | null;
  merged_commit_public_id?: string | null;
  reviews: MergeReviewResponse[];
  comments: MergeCommentResponse[];
  can_approve: boolean;
  can_merge: boolean;
  blocking_reasons: string[];
}

export interface MergeRequestListResponse {
  items: MergeRequestSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface MergeRequestCreateRequest {
  source_branch_id?: number;
  source_branch_name?: string;
  source_branch_public_id?: string;
  target_branch_id?: number;
  target_branch_name?: string;
  target_branch_public_id?: string;
  title: string;
  description?: string;
}

export interface MergeReviewRequest {
  decision: string;
  comment?: string;
}

export interface MergeCommentCreateRequest {
  entity_uuid?: string;
  field_path?: string;
  relation_key?: string;
  comment: string;
  required?: boolean;
}

// ==========================================
// Phase 6: Three-Way Merge & Conflict Resolution Types
// ==========================================

export type ConflictType =
  | 'same_field_different_value'
  | 'delete_vs_modify'
  | 'opposite_relation_ops'
  | 'same_position_order'
  | 'object_identity_parent';

export type ConflictChoice = 'target' | 'source' | 'manual';

export interface ConflictItem {
  conflict_id: string;
  conflict_type: ConflictType;
  entity_type: string;
  entity_uuid: string;
  entity_name: string;
  path: string;
  parent_uuid?: string | null;
  parent_type?: string | null;
  base_value?: unknown;
  target_value?: unknown;
  source_value?: unknown;
  related_entity_type?: string | null;
  related_entity_uuid?: string | null;
  related_entity_name?: string | null;
  choices: string[];
  resolved: boolean;
}

export interface MergePreviewResponse {
  merge_base_public_id?: string | null;
  source_head_public_id?: string | null;
  target_head_public_id?: string | null;
  conflict_count: number;
  conflicts: ConflictItem[];
  auto_merged_summary: Record<string, number>;
}

export interface ConflictResolution {
  conflict_id: string;
  choice: ConflictChoice;
  manual_value?: unknown;
}

export interface MergeRequestPayload {
  resolutions: ConflictResolution[];
  merge_base_public_id?: string | null;
  source_head_public_id?: string | null;
  target_head_public_id?: string | null;
}

export interface MergeResponse {
  status: string;
  merged_commit_public_id?: string | null;
  target_head_public_id?: string | null;
}
