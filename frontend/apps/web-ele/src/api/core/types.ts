/** internSU 前端 AI 工作区类型定义 (v2 统一版). */
export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  sources?: CitationSource[];
  trace?: AgentTrace[];
}

export interface CitationSource {
  document_name: string;
  page_number?: number;
  relevance_score?: number;
  knowledge_base?: string;
  excerpt?: string;
  citation_id?: number;
}

export interface AgentTrace {
  node: string;
  step_type: string;
  step_name: string;
  message: string;
  status: 'running' | 'completed' | 'failed';
  duration_ms?: number;
  detail?: Record<string, any>;
  timestamp: number;
}

/** 统一聊天请求 — v2: 系统自动检测意图 */
export interface ChatRequest {
  user_id: string;
  conversation_id: string;
  message: string;
  model?: string;
  stream?: boolean;
  space_ids?: number[];
  doc_ids?: number[];
  /** @deprecated v2: 系统自动检测意图 */
  use_rag?: boolean;
  /** @deprecated v2: 系统自动检测意图 */
  use_tools?: boolean;
}

export interface RagSearchRequest {
  query: string;
  top_k?: number;
  doc_ids?: number[];
  space_id?: string;
}

export interface ChatResponse {
  answer: string;
  sources?: CitationSource[];
  traces?: AgentTrace[];
  conversation_id: string;
}

export interface Conversation {
  conversation_id: string;
  title: string;
  create_time?: string;
  updated_at?: string;
}

export interface Message {
  role: string;
  content: string;
  sources?: any[];
  trace?: any[];
}

export interface PageResult<T> {
  records: T[];
  total: number;
  pages: number;
  current: number;
}

export interface KnowledgeBase {
  id: number;
  name: string;
  description: string;
  visibility: 'private' | 'department' | 'public';
  department_id?: number;
  creator_id: number;
  document_count: number;
  chunk_count: number;
  embedding_model: string;
  status: number;
  create_time: string;
  update_time?: string;
}

export interface Document {
  id: number;
  knowledge_base_id: number;
  filename: string;
  file_type: string;
  file_size: number;
  upload_user: number;
  upload_time: string;
  parse_status: string;
  embedding_status: string;
  chunk_count: number;
  token_count: number;
}

export interface ModelConfig {
  id: number;
  name: string;
  provider: string;
  model_name: string;
  is_default: boolean;
  is_active: boolean;
  max_tokens: number;
  temperature: number;
}

export interface PromptTemplate {
  id: number;
  name: string;
  type: string;
  content: string;
  variables: string[];
  is_default: boolean;
  is_active: boolean;
}

export interface JavaUserInfo {
  id: number;
  username: string;
  nickname?: string;
  email?: string;
  avatarUrl?: string;
}

export interface LoginResult {
  accessToken: string;
  refreshToken?: string;
  userInfo: JavaUserInfo;
}
