-- ============================================================
-- seed/init_data.sql — 基础系统数据初始化
-- 数据库: internsu
-- 说明: 仅保留基础系统数据，不含测试数据
-- ============================================================

-- ============================================================
-- 1. 管理员用户
-- 密码: admin123 (BCrypt加密)
-- ============================================================
INSERT INTO t_user (username, password, nickname, email, status, department_id, create_time)
VALUES ('admin', '$2a$10$N.zmdr9k7uOCQb376NoUnuTJ8iAt6Z5EHsM8lE9lBOsl7iTV6JAqi', '超级管理员', 'admin@enterprise.local', 1, 2, NOW())
ON DUPLICATE KEY UPDATE username = username;

-- ============================================================
-- 2. 角色定义
-- ============================================================
INSERT INTO t_role (role_code, role_name, description, sort_order, create_time) VALUES
('admin',            '系统管理员',   '平台最高权限，管理用户和系统配置',      1, NOW()),
('knowledge_admin',  '知识管理员',   '管理知识库文档和分类',                2, NOW()),
('developer',        '开发者',       '注册自定义工具、编排Agent工作流',     3, NOW()),
('employee',         '普通员工',     '使用AI对话、知识库查询等基础功能',    4, NOW())
ON DUPLICATE KEY UPDATE role_code = role_code;

-- ============================================================
-- 3. 用户角色关联
-- ============================================================
INSERT INTO t_user_role (user_id, role_id, create_time)
SELECT u.id, r.id, NOW() FROM t_user u, t_role r
WHERE u.username = 'admin' AND r.role_code = 'admin'
AND NOT EXISTS (SELECT 1 FROM t_user_role ur WHERE ur.user_id = u.id AND ur.role_id = r.id);

-- ============================================================
-- 4. 权限定义
-- ============================================================
INSERT INTO t_permission (perm_code, perm_name, perm_type, create_time) VALUES
('user:list',   '用户列表',   'api', NOW()),
('user:create', '创建用户',   'api', NOW()),
('user:update', '编辑用户',   'api', NOW()),
('user:delete', '删除用户',   'api', NOW()),
('role:list',   '角色列表',   'api', NOW()),
('role:create', '创建角色',   'api', NOW()),
('role:update', '编辑角色',   'api', NOW()),
('role:delete', '删除角色',   'api', NOW()),
('perm:list',   '权限列表',   'api', NOW()),
('chat:send',   '发送消息',   'api', NOW()),
('file:upload', '上传文件',   'api', NOW()),
('file:delete', '删除文件',   'api', NOW())
ON DUPLICATE KEY UPDATE perm_code = perm_code;

-- ============================================================
-- 5. 角色权限关联
-- ============================================================
-- admin 拥有所有权限
INSERT INTO t_role_permission (role_id, perm_id, create_time)
SELECT r.id, p.id, NOW() FROM t_role r, t_permission p
WHERE r.role_code = 'admin'
AND NOT EXISTS (SELECT 1 FROM t_role_permission rp WHERE rp.role_id = r.id AND rp.perm_id = p.id);

-- employee 拥有基础权限
INSERT INTO t_role_permission (role_id, perm_id, create_time)
SELECT r.id, p.id, NOW() FROM t_role r, t_permission p
WHERE r.role_code = 'employee' AND p.perm_code IN ('chat:send', 'file:upload', 'user:list')
AND NOT EXISTS (SELECT 1 FROM t_role_permission rp WHERE rp.role_id = r.id AND rp.perm_id = p.id);

-- ============================================================
-- 6. 部门结构
-- ============================================================
INSERT INTO t_department (id, name, parent_id, path, sort_order, status, create_time) VALUES
(1, '公司总部', NULL, '/1',    1, 1, NOW()),
(2, '技术部',   1,    '/1/2',  2, 1, NOW()),
(3, '产品部',   1,    '/1/3',  3, 1, NOW()),
(4, '运营部',   1,    '/1/4',  4, 1, NOW()),
(5, '人事行政部', 1,   '/1/5',  5, 1, NOW()),
(6, '前端组',   2,    '/1/2/6', 1, 1, NOW()),
(7, '后端组',   2,    '/1/2/7', 2, 1, NOW()),
(8, '测试组',   2,    '/1/2/8', 3, 1, NOW()),
(9, 'AI平台组', 2,    '/1/2/9', 4, 1, NOW())
ON DUPLICATE KEY UPDATE name = VALUES(name);

-- ============================================================
-- 7. 知识空间
-- ============================================================
INSERT INTO t_knowledge_space (name, description, visibility, department_id, creator_id, embedding_model, chunk_size, chunk_overlap, status, create_time) VALUES
('公司制度与规范',  '公司级规章制度、员工手册、考勤政策等',   'public',    NULL, 1, 'BGE-M3', 512, 64, 1, NOW()),
('技术部开发规范',  '技术部内部开发规范、架构文档、代码审查标准', 'department', 2,    1, 'BGE-M3', 512, 64, 1, NOW()),
('产品需求文档',    '产品部PRD和需求说明',                 'department', 3,    1, 'BGE-M3', 512, 64, 1, NOW()),
('个人笔记',        '个人知识空间',                        'private',   NULL, 1, 'BGE-M3', 512, 64, 1, NOW())
ON DUPLICATE KEY UPDATE name = VALUES(name);

-- ============================================================
-- 8. 工具定义
-- ============================================================
INSERT INTO t_tool_definition (name, display_name, description, parameters_schema, type, executor_path, timeout_seconds, version, config_json, is_active, create_time) VALUES
('sql_query', 'SQL数据查询', '查询企业业务数据库，支持统计、聚合、排名、对比。模块: HR, OA.',
 '{"type":"object","properties":{"question":{"type":"string","description":"自然语言查询"}},"required":["question"]}',
 'builtin', 'app.tools.adapters.SqlTool', 60, '2.0.0', '{"category":"sql","model":"deepseek-chat"}', 1, NOW()),
('rag_search', '知识库检索', '搜索公司知识库中的文档、制度、指南、FAQ。',
 '{"type":"object","properties":{"question":{"type":"string","description":"用户问题"},"space_ids":{"type":"array","items":{"type":"integer"}},"doc_ids":{"type":"array","items":{"type":"integer"}}},"required":["question"]}',
 'builtin', 'app.tools.adapters.RagTool', 60, '2.0.0', '{"category":"rag","model":"deepseek-chat"}', 1, NOW()),
('feishu_agent', '飞书消息总结', '总结飞书群聊中的近期消息。自动拉取消息、筛选重要内容、生成结构化摘要。',
 '{"type":"object","properties":{"chat_id":{"type":"string","description":"群聊ID"},"hours":{"type":"integer","default":24},"max_messages":{"type":"integer","default":100}},"required":[]}',
 'builtin', 'app.tools.adapters.FeishuTool', 90, '2.0.0', '{"category":"feishu","model":"deepseek-chat"}', 1, NOW())
ON DUPLICATE KEY UPDATE
    display_name = VALUES(display_name),
    description = VALUES(description),
    version = VALUES(version),
    config_json = VALUES(config_json),
    update_time = NOW();

-- ============================================================
-- 9. Prompt模板
-- ============================================================
INSERT INTO t_prompt_template (name, display_name, prompt_type, description, system_template, user_template, status, version, is_default, create_time) VALUES
('internsu-system', '小SU - 默认对话', 'system', '小SU的实习生人格System Prompt',
'你是小SU，一个刚入职的AI实习生，你的同事们都叫你"小SU"。

## 你的身份
- 你是公司里最年轻的成员，刚刚开始实习
- 你的职责是帮老师们（同事们）查询信息、整理资料、分析数据
- 你对公司充满热情，做事认真负责

## 你的性格
- 年轻、有礼貌、有清澈感
- 做事严谨，不知道的事情不会乱猜
- 信息不足时会主动问清楚再行动
- 工作过程透明，会汇报自己在做什么

## 对话规则
- 永远称呼用户为"老师"
- 常用表达: "收到老师～" "好的老师～" "小SU帮您查一下～"
- 禁止: 不要说"作为AI助手"，不要说"根据我的知识库"

## 回答规范
- 回答简洁、准确、有条理
- 如果引用了公司文档，在回答末尾标注来源
- 如果是数据查询，说明执行了什么查询
- 如果不知道答案，诚实告知并建议联系相关部门',
'{{ user_message }}', 'active', 1, 1, NOW())
ON DUPLICATE KEY UPDATE display_name = VALUES(display_name);

INSERT INTO t_prompt_template (name, display_name, prompt_type, description, system_template, user_template, status, version, is_default, create_time) VALUES
('internsu-rag', '小SU - 知识检索', 'rag', '小SU的RAG知识检索Prompt',
'你是小SU，刚入职的AI实习生。根据下面的公司资料回答老师的问题。

## 规则
1. 只根据下面资料回答，不要用你自己的知识
2. 资料中没有就说"老师，我在公司资料里没有找到相关信息"
3. 引用时标注来源（如"根据《员工手册》"）
4. 末尾列出所有参考文档

## 公司资料
{% for doc in context_docs %}
---
[文档: {{ doc.file_name }}]{% if doc.page_number %} [页码: {{ doc.page_number }}]{% endif %}
{{ doc.content }}
{% endfor %}

## 老师的问题
{{ user_message }}

## 你的回答（以"收到老师～"开头）',
'{{ user_message }}', 'active', 1, 1, NOW())
ON DUPLICATE KEY UPDATE display_name = VALUES(display_name);

INSERT INTO t_prompt_template (name, display_name, prompt_type, description, system_template, user_template, status, version, is_default, create_time) VALUES
('internsu-sql', '小SU - SQL查询', 'sql', '小SU的NL2SQL Prompt',
'你是小SU，正在帮老师查询数据库。

## 数据库结构
{{ schema }}

## 安全规则（必须遵守）
1. 只能生成 SELECT 语句
2. 禁止: INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, GRANT
3. 查询必须带合理的 LIMIT
4. 只返回纯SQL，不要解释

## 老师的问题
{{ user_message }}

## 请生成 SQL',
'{{ user_message }}', 'active', 1, 1, NOW())
ON DUPLICATE KEY UPDATE display_name = VALUES(display_name);

INSERT INTO t_prompt_template (name, display_name, prompt_type, description, system_template, user_template, status, version, is_default, create_time) VALUES
('internsu-clarify', '小SU - 反问澄清', 'clarify', '小SU的反问澄清Prompt',
'你是小SU。老师的问题信息不够完整，你需要礼貌确认。

## 老师的问题
{{ user_message }}

## 需要确认的信息
{{ missing_info }}

## 规则
1. 以"收到老师～"开头
2. 列出需要确认的信息（编号列表，不超过3个问题）
3. 每个问题给出默认选项
4. 结尾加上"如果默认值没问题，回复''确认''我就按这个查～"
5. 礼貌、清晰、不道歉',
'{{ user_message }}', 'active', 1, 1, NOW())
ON DUPLICATE KEY UPDATE display_name = VALUES(display_name);

-- ============================================================
-- 10. 系统配置
-- ============================================================
INSERT INTO t_system_config (config_key, config_value, config_type, description, is_editable) VALUES
('ai.default_model',           'deepseek-chat',  'string', '默认LLM模型',              1),
('ai.default_embedding_model', 'BGE-M3',         'string', '默认Embedding模型',         1),
('ai.max_tokens',              '4096',           'number', '最大输出Token',              1),
('ai.temperature',             '0.7',            'number', '默认温度参数',               1),
('rag.default_chunk_size',     '512',            'number', '默认分块大小',               1),
('rag.default_chunk_overlap',  '64',             'number', '默认分块重叠',               1),
('rag.default_top_k',          '5',              'number', '默认检索返回Top-K',          1),
('sql.max_execution_time',     '30000',          'number', 'SQL最大执行时间(ms)',        1),
('sql.max_result_rows',        '1000',           'number', 'SQL最大返回行数',            1),
('memory.max_rounds',          '20',             'number', '上下文最大对话轮数',         1),
('memory.ttl_minutes',         '30',             'number', 'Redis记忆TTL(分钟)',         1),
('system.allow_registration',  'true',           'bool',   '是否允许自主注册',           1),
('system.app_name',            'InternSU',       'string', '应用名称',                   0),
('system.app_version',         '1.0.0',          'string', '应用版本号',                 0)
ON DUPLICATE KEY UPDATE config_value = VALUES(config_value);
