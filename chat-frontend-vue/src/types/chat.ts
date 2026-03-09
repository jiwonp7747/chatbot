export interface ChatRequest {
  prompt: string;
  model: string;
  chat_session_id?: number | null;
  rag_tags: string[] | null;
}

export interface HitlToolCallDetail {
  tool_name: string;
  description: string;
  args: string;
}

export interface HitlToolCall {
  name: string;
  args: Record<string, unknown>;
  detail?: HitlToolCallDetail;  // 도구별 상세 정보
}

export interface AvailableTool {
  name: string;
  description: string;
}

export interface ChatResponse {
  content: string;
  status: 'progress' | 'streaming' | 'done' | 'error' | 'confirm' | 'sub_progress';
  error: string | null;
  // HITL 필드 (confirm 시에만 사용)
  thread_id?: string;
  tool_calls?: HitlToolCall[];   // interrupt된 도구 목록
  tool_context?: string;         // 에이전트 판단 근거 (1회, 공통)
  available_tools?: AvailableTool[];  // 수정 가능 도구 목록
  // sub_progress 필드
  agent_name?: string;
  sub_tools?: string[];
  parallel?: boolean;
}

export interface EditedToolCall {
  name: string;
  args: Record<string, unknown>;
}

export interface JsonSchemaProperty {
  type?: string;
  format?: string;
  anyOf?: { type: string; format?: string }[];
  title?: string;
  default?: unknown;
  description?: string;
  enum?: string[];
  items?: { type?: string };
}

export interface JsonSchema {
  properties?: Record<string, JsonSchemaProperty>;
  required?: string[];
  title?: string;
  type?: string;
}

export interface ToolSchema {
  name: string;
  description: string;
  schema: JsonSchema;
  agent: string;
}

export interface ResumeRequest {
  thread_id: string;
  approved: boolean;
  chat_session_id?: number | null;
  model?: string;
  edit_message?: string;  // 거부 시 에이전트에게 전달할 메시지
  edited_tool_calls?: EditedToolCall[];  // EDIT decision용
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
}

export interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
  model: ModelType;
  createdAt: number;
  updatedAt: number;
}

export type ModelType = 'gpt-5-nano' | 'gpt-4' | 'claude-3' | 'gemini-pro';

// API 응답 타입
export interface SessionData {
  chat_session_id: number;
  session_title: string;
  created_at: string;
  updated_at: string;
}

export interface SessionsApiResponse {
  success: boolean;
  message: string;
  data: SessionData[];
  status_code: number;
}

export interface MessageData {
  chat_message_id: number;
  content: string;
  created_at: string;
  role: 'user' | 'system';
  chat_session_id: number;
}

export interface MessagesApiResponse {
  success: boolean;
  message: string;
  data: MessageData[];
  status_code: number;
}

export interface ApiResponse<T = unknown> {
  success: boolean;
  message: string;
  data: T;
  status_code: number;
}

export interface McpInputSchemaPreview {
  fields: string[];
  required: string[];
  has_schema: boolean;
}

export interface McpTool {
  id: string;
  tool_name: string;
  mcp_name: string;
  description: string;
  category: string;
  available: boolean;
  recent_score: number;
  input_schema: Record<string, unknown>;
  input_schema_preview: McpInputSchemaPreview;
}



export type McpToolsApiResponse = ApiResponse<McpTool[]>;

export interface TagTreeNode {
  id: number;
  name: string;
  parent_id: number | null;
  level: number;
  file_count: number;
  children: TagTreeNode[];
}

export type RagTagsApiResponse = ApiResponse<TagTreeNode[]>;
