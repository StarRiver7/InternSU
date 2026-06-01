/** AI workspace types for internSU frontend */
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
  message: string;
  status: 'running' | 'completed' | 'failed';
  timestamp: number;
}

export interface ChatRequest {
  user_id: string;
  conversation_id: string;
  message: string;
  model?: string;
  stream?: boolean;
  use_rag?: boolean;
  use_tools?: boolean;
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
  parse_status: 'UPLOADED' | 'PARSING' | 'PARSED' | 'CHUNKING' | 'CHUNKED' | 'EMBEDDING' | 'INDEXING' | 'READY' | 'FAILED';
  embedding_status: string;
  chunk_count: number;
  token_count: number;
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
