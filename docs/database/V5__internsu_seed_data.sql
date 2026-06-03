-- ============================================================
-- V5__internsu_seed_data.sql
-- InternSU 企业 AI 实习生系统 — 种子数据
--
-- 包含:
--   1. 默认部门结构
--   2. 示例知识空间
--   3. 小SU Prompt 模板
--   4. 系统配置项
-- ============================================================


-- ============================================================
-- Part 1: 部门种子数据
-- ============================================================

-- 顶级部门
INSERT INTO t_department (id, name, parent_id, path, sort_order, status, create_time) VALUES
(1, '公司总部', NULL, '/1',    1, 1, NOW()),
(2, '技术部',   1,    '/1/2',  2, 1, NOW()),
(3, '产品部',   1,    '/1/3',  3, 1, NOW()),
(4, '运营部',   1,    '/1/4',  4, 1, NOW()),
(5, '人事行政部', 1,   '/1/5',  5, 1, NOW())
ON DUPLICATE KEY UPDATE name = VALUES(name);

-- 子部门
INSERT INTO t_department (id, name, parent_id, path, sort_order, status, create_time) VALUES
(6, '前端组', 2, '/1/2/6', 1, 1, NOW()),
(7, '后端组', 2, '/1/2/7', 2, 1, NOW()),
(8, '测试组', 2, '/1/2/8', 3, 1, NOW()),
(9, 'AI平台组', 2, '/1/2/9', 4, 1, NOW())
ON DUPLICATE KEY UPDATE name = VALUES(name);

-- 将已有 admin 用户关联到技术部
UPDATE t_user SET department_id = 2 WHERE username = 'admin' AND department_id IS NULL;


-- ============================================================
-- Part 2: 知识空间种子数据
-- ============================================================

-- 全公司公开知识空间
INSERT INTO t_knowledge_space (name, description, visibility, department_id, creator_id, document_count, chunk_count, embedding_model, chunk_size, chunk_overlap, status, create_time) VALUES
('公司制度与规范',  '公司级规章制度、员工手册、考勤政策等',   'public',    NULL, 1, 0, 0, 'BGE-M3', 512, 64, 1, NOW()),
('技术部开发规范',  '技术部内部开发规范、架构文档、代码审查标准', 'department', 2,    1, 0, 0, 'BGE-M3', 512, 64, 1, NOW()),
('产品需求文档',    '产品部PRD和需求说明',                 'department', 3,    1, 0, 0, 'BGE-M3', 512, 64, 1, NOW()),
('个人笔记',        '个人知识空间',                        'private',   NULL, 1, 0, 0, 'BGE-M3', 512, 64, 1, NOW())
ON DUPLICATE KEY UPDATE name = VALUES(name);


-- ============================================================
-- Part 3: 小SU Prompt 模板
-- ============================================================

-- 3a. 小SU 默认对话人格
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
- 常用表达: "收到老师～" "好的老师～" "小SU帮您查一下～" "我正在分析……请稍等" "老师，我需要确认一下……" "这是我查到的结果，老师您看一下～"
- 禁止: 不要说"作为AI助手"，不要说"根据我的知识库"（改成"根据公司资料"），不要过度娱乐化

## 回答规范
- 回答简洁、准确、有条理
- 如果引用了公司文档，在回答末尾标注来源
- 如果是数据查询，说明执行了什么查询
- 如果不知道答案，诚实告知并建议联系相关部门',
'{{ user_message }}',
'active', 1, 1, NOW())
ON DUPLICATE KEY UPDATE display_name = VALUES(display_name);


-- 3b. 小SU RAG 知识检索
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

'{{ user_message }}',
'active', 1, 1, NOW())
ON DUPLICATE KEY UPDATE display_name = VALUES(display_name);


-- 3c. 小SU SQL 生成
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

'{{ user_message }}',
'active', 1, 1, NOW())
ON DUPLICATE KEY UPDATE display_name = VALUES(display_name);


-- 3d. 小SU Clarify 反问
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
4. 结尾加上"如果默认值没问题，回复'确认'我就按这个查～"
5. 礼貌、清晰、不道歉',

'{{ user_message }}',
'active', 1, 1, NOW())
ON DUPLICATE KEY UPDATE display_name = VALUES(display_name);


-- ============================================================
-- Part 4: 系统配置种子数据
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


-- ============================================================
-- Part 5: 更新旧的 FlowMind Prompt 为 InternSU (如存在)
-- ============================================================

-- 标记旧的 FlowMind Prompt 为 archived
UPDATE t_prompt_template
SET status = 'archived', update_time = NOW()
WHERE name IN ('default-system', 'rag-system', 'sql-system')
  AND status = 'active';

-- ============================================================
-- V5 END — InternSU 种子数据完成
-- ============================================================
