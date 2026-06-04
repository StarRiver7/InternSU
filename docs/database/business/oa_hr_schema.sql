-- ============================================================
-- InternSU OA & HR 业务模块数据库脚本
-- ============================================================
-- 包含 OA 办公模块和 HR 人力资源模块
-- 生成日期：2026-06-04
-- ============================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================
-- 【OA 模块】 - 办公自动化
-- ============================================================

-- ----------------------------
-- 表结构：oa_department（部门表）
-- ----------------------------
DROP TABLE IF EXISTS `oa_department`;
CREATE TABLE `oa_department` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '部门ID',
  `name` VARCHAR(100) NOT NULL COMMENT '部门名称',
  `parent_id` BIGINT DEFAULT NULL COMMENT '上级部门ID',
  `manager_id` BIGINT DEFAULT NULL COMMENT '部门负责人ID',
  `description` VARCHAR(500) DEFAULT NULL COMMENT '部门描述',
  `status` TINYINT DEFAULT 1 COMMENT '状态：1-启用 0-禁用',
  `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_parent_id` (`parent_id`),
  KEY `idx_status` (`status`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='部门表';

-- ----------------------------
-- 表结构：oa_employee（员工表）
-- ----------------------------
DROP TABLE IF EXISTS `oa_employee`;
CREATE TABLE `oa_employee` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '员工ID',
  `employee_no` VARCHAR(50) NOT NULL UNIQUE COMMENT '员工编号',
  `name` VARCHAR(50) NOT NULL COMMENT '员工姓名',
  `email` VARCHAR(100) NOT NULL UNIQUE COMMENT '邮箱',
  `phone` VARCHAR(20) DEFAULT NULL COMMENT '手机号',
  `department_id` BIGINT NOT NULL COMMENT '所属部门ID',
  `position` VARCHAR(50) DEFAULT NULL COMMENT '职位',
  `status` VARCHAR(20) NOT NULL DEFAULT '在职' COMMENT '状态：在职/离职/试用期',
  `hire_date` DATE NOT NULL COMMENT '入职日期',
  `leave_date` DATE DEFAULT NULL COMMENT '离职日期',
  `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_department_id` (`department_id`),
  KEY `idx_status` (`status`),
  KEY `idx_employee_no` (`employee_no`),
  CONSTRAINT `fk_oa_employee_department` FOREIGN KEY (`department_id`) REFERENCES `oa_department` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='员工表';

-- ----------------------------
-- 表结构：oa_project（项目表）
-- ----------------------------
DROP TABLE IF EXISTS `oa_project`;
CREATE TABLE `oa_project` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '项目ID',
  `name` VARCHAR(200) NOT NULL COMMENT '项目名称',
  `description` TEXT DEFAULT NULL COMMENT '项目描述',
  `manager_id` BIGINT NOT NULL COMMENT '项目负责人ID',
  `department_id` BIGINT NOT NULL COMMENT '所属部门ID',
  `status` VARCHAR(20) NOT NULL DEFAULT '进行中' COMMENT '状态：待启动/进行中/已完成/已终止',
  `start_date` DATE NOT NULL COMMENT '开始日期',
  `end_date` DATE DEFAULT NULL COMMENT '结束日期',
  `budget` DECIMAL(15,2) DEFAULT NULL COMMENT '预算金额',
  `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_manager_id` (`manager_id`),
  KEY `idx_department_id` (`department_id`),
  KEY `idx_status` (`status`),
  CONSTRAINT `fk_oa_project_manager` FOREIGN KEY (`manager_id`) REFERENCES `oa_employee` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_oa_project_department` FOREIGN KEY (`department_id`) REFERENCES `oa_department` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='项目表';

-- ----------------------------
-- 表结构：oa_task（任务表）
-- ----------------------------
DROP TABLE IF EXISTS `oa_task`;
CREATE TABLE `oa_task` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '任务ID',
  `title` VARCHAR(200) NOT NULL COMMENT '任务标题',
  `description` TEXT DEFAULT NULL COMMENT '任务描述',
  `project_id` BIGINT NOT NULL COMMENT '所属项目ID',
  `assignee_id` BIGINT NOT NULL COMMENT '指派员工ID',
  `priority` VARCHAR(20) NOT NULL DEFAULT '中' COMMENT '优先级：高/中/低',
  `status` VARCHAR(20) NOT NULL DEFAULT '待处理' COMMENT '状态：待处理/进行中/已完成/已取消',
  `due_date` DATE DEFAULT NULL COMMENT '截止日期',
  `progress` INT DEFAULT 0 COMMENT '进度：0-100',
  `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_project_id` (`project_id`),
  KEY `idx_assignee_id` (`assignee_id`),
  KEY `idx_status` (`status`),
  KEY `idx_priority` (`priority`),
  CONSTRAINT `fk_oa_task_project` FOREIGN KEY (`project_id`) REFERENCES `oa_project` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_oa_task_assignee` FOREIGN KEY (`assignee_id`) REFERENCES `oa_employee` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='任务表';

-- ----------------------------
-- 表结构：oa_attendance（考勤表）
-- ----------------------------
DROP TABLE IF EXISTS `oa_attendance`;
CREATE TABLE `oa_attendance` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '考勤ID',
  `employee_id` BIGINT NOT NULL COMMENT '员工ID',
  `date` DATE NOT NULL COMMENT '考勤日期',
  `check_in_time` TIME DEFAULT NULL COMMENT '上班打卡时间',
  `check_out_time` TIME DEFAULT NULL COMMENT '下班打卡时间',
  `status` VARCHAR(20) NOT NULL DEFAULT '正常' COMMENT '状态：正常/迟到/早退/旷工/请假',
  `leave_type` VARCHAR(20) DEFAULT NULL COMMENT '请假类型：事假/病假/年假/调休',
  `hours` DECIMAL(5,2) DEFAULT NULL COMMENT '请假时长（小时）',
  `remark` VARCHAR(200) DEFAULT NULL COMMENT '备注',
  `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_employee_date` (`employee_id`, `date`),
  KEY `idx_employee_id` (`employee_id`),
  KEY `idx_date` (`date`),
  KEY `idx_status` (`status`),
  CONSTRAINT `fk_oa_attendance_employee` FOREIGN KEY (`employee_id`) REFERENCES `oa_employee` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='考勤表';

-- ============================================================
-- 【HR 模块】 - 人力资源
-- ============================================================

-- ----------------------------
-- 表结构：hr_department（HR部门表）
-- ----------------------------
DROP TABLE IF EXISTS `hr_department`;
CREATE TABLE `hr_department` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '部门ID',
  `name` VARCHAR(100) NOT NULL COMMENT '部门名称',
  `parent_id` BIGINT DEFAULT NULL COMMENT '上级部门ID',
  `head_count` INT DEFAULT 0 COMMENT '编制人数',
  `current_count` INT DEFAULT 0 COMMENT '现有人数',
  `description` VARCHAR(500) DEFAULT NULL COMMENT '部门描述',
  `status` TINYINT DEFAULT 1 COMMENT '状态：1-启用 0-禁用',
  `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_parent_id` (`parent_id`),
  KEY `idx_status` (`status`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='HR部门表';

-- ----------------------------
-- 表结构：hr_position（岗位表）
-- ----------------------------
DROP TABLE IF EXISTS `hr_position`;
CREATE TABLE `hr_position` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '岗位ID',
  `name` VARCHAR(100) NOT NULL COMMENT '岗位名称',
  `department_id` BIGINT NOT NULL COMMENT '所属部门ID',
  `level` VARCHAR(20) DEFAULT NULL COMMENT '职级：初级/中级/高级/资深/管理',
  `salary_min` DECIMAL(10,2) DEFAULT NULL COMMENT '最低薪资',
  `salary_max` DECIMAL(10,2) DEFAULT NULL COMMENT '最高薪资',
  `requirements` TEXT DEFAULT NULL COMMENT '任职要求',
  `responsibilities` TEXT DEFAULT NULL COMMENT '岗位职责',
  `status` VARCHAR(20) NOT NULL DEFAULT '招聘中' COMMENT '状态：招聘中/暂停招聘/已关闭',
  `open_date` DATE NOT NULL COMMENT '发布日期',
  `close_date` DATE DEFAULT NULL COMMENT '关闭日期',
  `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_department_id` (`department_id`),
  KEY `idx_status` (`status`),
  CONSTRAINT `fk_hr_position_department` FOREIGN KEY (`department_id`) REFERENCES `hr_department` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='岗位表';

-- ----------------------------
-- 表结构：hr_candidate（候选人表）
-- ----------------------------
DROP TABLE IF EXISTS `hr_candidate`;
CREATE TABLE `hr_candidate` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '候选人ID',
  `name` VARCHAR(50) NOT NULL COMMENT '姓名',
  `phone` VARCHAR(20) NOT NULL COMMENT '手机号',
  `email` VARCHAR(100) NOT NULL COMMENT '邮箱',
  `position_id` BIGINT NOT NULL COMMENT '应聘岗位ID',
  `source` VARCHAR(50) DEFAULT NULL COMMENT '招聘渠道：BOSS直聘/智联招聘/拉勾/内推/猎头',
  `resume_url` VARCHAR(255) DEFAULT NULL COMMENT '简历链接',
  `skills` VARCHAR(500) DEFAULT NULL COMMENT '技能标签，逗号分隔',
  `education` VARCHAR(50) DEFAULT NULL COMMENT '学历：本科/硕士/博士/大专',
  `experience` INT DEFAULT 0 COMMENT '工作经验（年）',
  `status` VARCHAR(20) NOT NULL DEFAULT '待筛选' COMMENT '状态：待筛选/筛选通过/面试中/已录用/已拒绝',
  `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_position_id` (`position_id`),
  KEY `idx_status` (`status`),
  KEY `idx_source` (`source`),
  CONSTRAINT `fk_hr_candidate_position` FOREIGN KEY (`position_id`) REFERENCES `hr_position` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='候选人表';

-- ----------------------------
-- 表结构：hr_interview（面试表）
-- ----------------------------
DROP TABLE IF EXISTS `hr_interview`;
CREATE TABLE `hr_interview` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '面试ID',
  `candidate_id` BIGINT NOT NULL COMMENT '候选人ID',
  `position_id` BIGINT NOT NULL COMMENT '岗位ID',
  `interviewer_id` BIGINT DEFAULT NULL COMMENT '面试官ID',
  `round` INT NOT NULL DEFAULT 1 COMMENT '面试轮次：1-一面 2-二面 3-三面 4-终面',
  `type` VARCHAR(20) DEFAULT NULL COMMENT '面试类型：初试/复试/技术面/HR面/终面',
  `status` VARCHAR(20) NOT NULL DEFAULT '待面试' COMMENT '状态：待面试/已面试/通过/未通过',
  `interview_date` DATETIME DEFAULT NULL COMMENT '面试时间',
  `result` TEXT DEFAULT NULL COMMENT '面试结果评价',
  `score` INT DEFAULT NULL COMMENT '面试评分：0-100',
  `feedback` TEXT DEFAULT NULL COMMENT '面试反馈',
  `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_candidate_id` (`candidate_id`),
  KEY `idx_position_id` (`position_id`),
  KEY `idx_status` (`status`),
  KEY `idx_interview_date` (`interview_date`),
  CONSTRAINT `fk_hr_interview_candidate` FOREIGN KEY (`candidate_id`) REFERENCES `hr_candidate` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_hr_interview_position` FOREIGN KEY (`position_id`) REFERENCES `hr_position` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='面试表';

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================
-- 【OA 模块测试数据】
-- ============================================================

-- 插入部门数据
INSERT INTO `oa_department` (`id`, `name`, `parent_id`, `manager_id`, `description`, `status`) VALUES
(1, '技术部', NULL, 1, '负责公司技术研发', 1),
(2, '产品部', NULL, 2, '负责产品设计与规划', 1),
(3, '运营部', NULL, 3, '负责产品运营与推广', 1),
(4, '人力资源部', NULL, 4, '负责人力资源管理', 1),
(5, '财务部', NULL, 5, '负责财务核算与管理', 1),
(6, '前端开发组', 1, 6, '负责前端技术开发', 1),
(7, '后端开发组', 1, 7, '负责后端技术开发', 1),
(8, '测试组', 1, 8, '负责软件测试', 1),
(9, '运维组', 1, 9, '负责系统运维', 1),
(10, 'UI设计组', 2, 10, '负责用户界面设计', 1);

-- 插入员工数据
INSERT INTO `oa_employee` (`id`, `employee_no`, `name`, `email`, `phone`, `department_id`, `position`, `status`, `hire_date`) VALUES
(1, 'EMP001', '张建国', 'zhangjianguo@internsu.com', '13800138001', 1, '技术总监', '在职', '2020-01-15'),
(2, 'EMP002', '李思琪', 'lisqi@internsu.com', '13800138002', 2, '产品总监', '在职', '2020-03-20'),
(3, 'EMP003', '王浩然', 'wanghaoran@internsu.com', '13800138003', 3, '运营总监', '在职', '2020-05-10'),
(4, 'EMP004', '刘雨萱', 'liuyuxuan@internsu.com', '13800138004', 4, 'HR总监', '在职', '2021-02-18'),
(5, 'EMP005', '陈志强', 'chenzhiqiang@internsu.com', '13800138005', 5, '财务总监', '在职', '2021-04-01'),
(6, 'EMP006', '刘海龙', 'liuhailong@internsu.com', '13800138006', 6, '前端技术负责人', '在职', '2021-06-15'),
(7, 'EMP007', '赵雅婷', 'zhaoyating@internsu.com', '13800138007', 6, '高级前端工程师', '在职', '2022-01-10'),
(8, 'EMP008', '孙博文', 'sunbowen@internsu.com', '13800138008', 6, '前端工程师', '在职', '2022-03-25'),
(9, 'EMP009', '周俊杰', 'zhoujunjie@internsu.com', '13800138009', 7, '后端技术负责人', '在职', '2021-07-01'),
(10, 'EMP010', '吴天宇', 'wutianyu@internsu.com', '13800138010', 7, '高级后端工程师', '在职', '2022-02-20'),
(11, 'EMP011', '郑凯文', 'zhengkaiwen@internsu.com', '13800138011', 7, '后端工程师', '在职', '2022-05-15'),
(12, 'EMP012', '杨晨光', 'yangchenguang@internsu.com', '13800138012', 7, '后端工程师', '在职', '2023-01-10'),
(13, 'EMP013', '许明月', 'xumingyue@internsu.com', '13800138013', 8, '测试负责人', '在职', '2021-08-15'),
(14, 'EMP014', '何佳欣', 'hejiaxin@internsu.com', '13800138014', 8, '测试工程师', '在职', '2022-04-01'),
(15, 'EMP015', '曹子轩', 'caozixuan@internsu.com', '13800138015', 8, '测试工程师', '在职', '2022-07-20'),
(16, 'EMP016', '谢雨桐', 'xieyutong@internsu.com', '13800138016', 9, '运维负责人', '在职', '2021-09-01'),
(17, 'EMP017', '韩晓峰', 'hanxiaofeng@internsu.com', '13800138017', 9, '运维工程师', '在职', '2022-06-10'),
(18, 'EMP018', '唐文博', 'tangwenbo@internsu.com', '13800138018', 10, 'UI设计负责人', '在职', '2021-10-15'),
(19, 'EMP019', '冯雨晴', 'fengyuqing@internsu.com', '13800138019', 10, 'UI设计师', '在职', '2022-08-01'),
(20, 'EMP020', '杨晓东', 'yangxiaodong@internsu.com', '13800138020', 2, '产品经理', '在职', '2022-09-15'),
(21, 'EMP021', '朱文轩', 'zhuwenxuan@internsu.com', '13800138021', 2, '产品经理', '在职', '2023-01-20'),
(22, 'EMP022', '胡锦程', 'hujincheng@internsu.com', '13800138022', 3, '运营经理', '在职', '2022-03-01'),
(23, 'EMP023', '林雨涵', 'linyuhan@internsu.com', '13800138023', 3, '运营专员', '在职', '2022-06-15'),
(24, 'EMP024', '罗天翔', 'luotianxiang@internsu.com', '13800138024', 4, 'HR经理', '在职', '2022-04-10'),
(25, 'EMP025', '梁静怡', 'liangjingyi@internsu.com', '13800138025', 4, 'HR专员', '在职', '2022-08-25'),
(26, 'EMP026', '谢佳怡', 'xiejiayi@internsu.com', '13800138026', 5, '财务经理', '在职', '2022-05-01'),
(27, 'EMP027', '宋浩宇', 'songhaoyu@internsu.com', '13800138027', 6, '前端工程师', '在职', '2023-02-10'),
(28, 'EMP028', '邓子豪', 'dengzihao@internsu.com', '13800138028', 7, '后端工程师', '在职', '2023-03-15'),
(29, 'EMP029', '许博文', 'xubowen@internsu.com', '13800138029', 8, '测试工程师', '在职', '2023-04-01'),
(30, 'EMP030', '何志强', 'hezhiqiang@internsu.com', '13800138030', 9, '运维工程师', '在职', '2023-05-10'),
(31, 'EMP031', '孙梦瑶', 'sunmengyao@internsu.com', '13800138031', 6, '前端工程师', '在职', '2023-06-01'),
(32, 'EMP032', '马晓峰', 'maxiaofeng@internsu.com', '13800138032', 7, '后端工程师', '在职', '2023-07-15'),
(33, 'EMP033', '赵子涵', 'zhaozihan@internsu.com', '13800138033', 8, '测试工程师', '在职', '2023-08-01'),
(34, 'EMP034', '钱晓琳', 'qianxiaolin@internsu.com', '13800138034', 9, '运维工程师', '在职', '2023-09-10'),
(35, 'EMP035', '孙晓彤', 'sunxiaotong@internsu.com', '13800138035', 10, 'UI设计师', '在职', '2023-10-01'),
(36, 'EMP036', '李浩然', 'lihaoran@internsu.com', '13800138036', 2, '产品经理', '在职', '2023-11-15'),
(37, 'EMP037', '周雨婷', 'zhouyuting@internsu.com', '13800138037', 3, '运营专员', '在职', '2023-12-01'),
(38, 'EMP038', '吴佳怡', 'wujiayi@internsu.com', '13800138038', 4, 'HR专员', '在职', '2024-01-10'),
(39, 'EMP039', '郑雨萱', 'zhengyuxuan@internsu.com', '13800138039', 5, '财务专员', '在职', '2024-02-15'),
(40, 'EMP040', '王梓涵', 'wangzihan@internsu.com', '13800138040', 6, '前端工程师', '在职', '2024-03-01'),
(41, 'EMP041', '陈思涵', 'chensihan@internsu.com', '13800138041', 7, '后端工程师', '在职', '2024-04-15'),
(42, 'EMP042', '刘思远', 'liusiyuan@internsu.com', '13800138042', 8, '测试工程师', '在职', '2024-05-01'),
(43, 'EMP043', '赵浩宇', 'zhaohaoyu@internsu.com', '13800138043', 9, '运维工程师', '在职', '2024-06-10'),
(44, 'EMP044', '孙雅琪', 'sunyaqi@internsu.com', '13800138044', 10, 'UI设计师', '在职', '2024-07-15'),
(45, 'EMP045', '周子轩', 'zhouzixuan@internsu.com', '13800138045', 2, '产品经理', '在职', '2024-08-01'),
(46, 'EMP046', '吴明轩', 'wumingxuan@internsu.com', '13800138046', 3, '运营专员', '在职', '2024-09-10'),
(47, 'EMP047', '郑浩宇', 'zhenghaoyu@internsu.com', '13800138047', 4, 'HR专员', '在职', '2024-10-15'),
(48, 'EMP048', '杨佳琪', 'yangjiaqi@internsu.com', '13800138048', 5, '财务专员', '在职', '2024-11-01'),
(49, 'EMP049', '许乐瑶', 'xuleyao@internsu.com', '13800138049', 6, '前端工程师', '在职', '2024-12-10'),
(50, 'EMP050', '何欣怡', 'hexinyi@internsu.com', '13800138050', 7, '后端工程师', '在职', '2025-01-15'),
(51, 'EMP051', '曹佳欣', 'caojiaxin@internsu.com', '13800138051', 8, '测试工程师', '在职', '2025-02-01'),
(52, 'EMP052', '谢子墨', 'xiezimo@internsu.com', '13800138052', 9, '运维工程师', '在职', '2025-03-15'),
(53, 'EMP053', '韩雨辰', 'hanyuchen@internsu.com', '13800138053', 10, 'UI设计师', '在职', '2025-04-01'),
(54, 'EMP054', '唐子轩', 'tangzixuan@internsu.com', '13800138054', 2, '产品经理', '在职', '2025-05-10'),
(55, 'EMP055', '冯思远', 'fengsiyuan@internsu.com', '13800138055', 3, '运营专员', '在职', '2025-06-01'),
(56, 'EMP056', '杨雨萱', 'yangyuxuan@internsu.com', '13800138056', 4, 'HR专员', '在职', '2025-07-15'),
(57, 'EMP057', '朱浩宇', 'zhuhaoyu@internsu.com', '13800138057', 5, '财务专员', '在职', '2025-08-01'),
(58, 'EMP058', '胡锦轩', 'hujinxuan@internsu.com', '13800138058', 6, '前端工程师', '在职', '2025-09-10'),
(59, 'EMP059', '林浩宇', 'linhaoyu@internsu.com', '13800138059', 7, '后端工程师', '在职', '2025-10-15'),
(60, 'EMP060', '罗文博', 'luowenbo@internsu.com', '13800138060', 8, '测试工程师', '在职', '2025-11-01'),
(61, 'EMP061', '梁佳怡', 'liangjiayi@internsu.com', '13800138061', 9, '运维工程师', '在职', '2025-12-10'),
(62, 'EMP062', '谢欣怡', 'xiexinyi@internsu.com', '13800138062', 10, 'UI设计师', '在职', '2026-01-15'),
(63, 'EMP063', '宋浩然', 'songhaoran@internsu.com', '13800138063', 1, '技术经理', '在职', '2020-06-01'),
(64, 'EMP064', '邓博文', 'dengbowen@internsu.com', '13800138064', 2, '产品经理', '在职', '2021-03-15'),
(65, 'EMP065', '许子轩', 'xuzixuan@internsu.com', '13800138065', 3, '运营经理', '在职', '2021-09-01'),
(66, 'EMP066', '何博文', 'hebowen@internsu.com', '13800138066', 4, 'HR经理', '在职', '2022-01-10'),
(67, 'EMP067', '孙博文', 'sunbowen2@internsu.com', '13800138067', 5, '财务经理', '在职', '2022-07-15'),
(68, 'EMP068', '马博文', 'mabowen@internsu.com', '13800138068', 6, '高级前端工程师', '在职', '2023-01-01'),
(69, 'EMP069', '赵博文', 'zhaobowen@internsu.com', '13800138069', 7, '高级后端工程师', '在职', '2023-06-15'),
(70, 'EMP070', '钱博文', 'qianbowen@internsu.com', '13800138070', 8, '高级测试工程师', '在职', '2023-12-01'),
(71, 'EMP071', '孙雨萱', 'sunyuxuan@internsu.com', '13800138071', 9, '高级运维工程师', '在职', '2024-05-10'),
(72, 'EMP072', '李雨萱', 'liyuxuan@internsu.com', '13800138072', 10, '高级UI设计师', '在职', '2024-11-15'),
(73, 'EMP073', '周博文', 'zhoubowen@internsu.com', '13800138073', 1, '架构师', '在职', '2019-08-01'),
(74, 'EMP074', '吴博文', 'wubowen@internsu.com', '13800138074', 2, '高级产品经理', '在职', '2020-02-15'),
(75, 'EMP075', '郑博文', 'zhengbowen@internsu.com', '13800138075', 3, '高级运营经理', '在职', '2020-08-01'),
(76, 'EMP076', '王思远', 'wangsiyuan@internsu.com', '13800138076', 4, 'HR总监助理', '在职', '2021-04-10'),
(77, 'EMP077', '陈雨萱', 'chenyuxuan@internsu.com', '13800138077', 5, '财务总监助理', '在职', '2021-10-01'),
(78, 'EMP078', '刘博文', 'liubowen@internsu.com', '13800138078', 6, '前端工程师', '离职', '2022-03-15', '2024-06-30'),
(79, 'EMP079', '赵雨萱', 'zhaoyuxuan@internsu.com', '13800138079', 7, '后端工程师', '离职', '2022-08-01', '2024-12-15'),
(80, 'EMP080', '孙浩宇', 'sunhaoyu@internsu.com', '13800138080', 8, '测试工程师', '试用期', '2025-12-01'),
(81, 'EMP081', '周浩宇', 'zhouhaoyu@internsu.com', '13800138081', 9, '运维工程师', '试用期', '2026-01-15'),
(82, 'EMP082', '吴浩宇', 'wuhaoyu@internsu.com', '13800138082', 10, 'UI设计师', '试用期', '2026-02-01'),
(83, 'EMP083', '郑子轩', 'zhengzixuan@internsu.com', '13800138083', 1, '技术专员', '在职', '2025-07-10'),
(84, 'EMP084', '杨博文', 'yangbowen@internsu.com', '13800138084', 2, '产品专员', '在职', '2025-08-25'),
(85, 'EMP087', '曹博文', 'caobowen@internsu.com', '13800138087', 5, '财务专员', '在职', '2025-11-15'),
(86, 'EMP088', '谢博文', 'xiebowen@internsu.com', '13800138088', 6, '前端工程师', '在职', '2025-12-01'),
(87, 'EMP089', '韩博文', 'hanbowen@internsu.com', '13800138089', 7, '后端工程师', '在职', '2026-01-10'),
(88, 'EMP090', '唐博文', 'tangbowen@internsu.com', '13800138090', 8, '测试工程师', '在职', '2026-02-01'),
(89, 'EMP091', '冯博文', 'fengbowen@internsu.com', '13800138091', 9, '运维工程师', '在职', '2026-03-15'),
(90, 'EMP093', '朱博文', 'zhubowen@internsu.com', '13800138093', 1, '技术工程师', '在职', '2026-04-15'),
(91, 'EMP094', '胡博文', 'hubowen@internsu.com', '13800138094', 2, '产品工程师', '在职', '2026-05-01'),
(92, 'EMP095', '林博文', 'linbowen@internsu.com', '13800138095', 3, '运营工程师', '在职', '2026-05-15'),
(93, 'EMP096', '罗博文', 'luobowen@internsu.com', '13800138096', 4, 'HR工程师', '在职', '2026-05-20'),
(94, 'EMP097', '梁博文', 'liangbowen@internsu.com', '13800138097', 5, '财务工程师', '在职', '2026-05-25'),
(95, 'EMP099', '宋博文', 'songbowen@internsu.com', '13800138099', 7, '后端工程师', '在职', '2026-05-30'),

-- 插入项目数据
INSERT INTO `oa_project` (`id`, `name`, `description`, `manager_id`, `department_id`, `status`, `start_date`, `end_date`, `budget`) VALUES
(1, '企业级RAG知识库系统', '基于大语言模型的企业级知识库检索系统，支持文档上传、智能问答、多模态检索', 1, 1, '进行中', '2025-01-01', '2025-12-31', 5000000.00),
(2, '移动端OA办公App', '面向企业员工的移动办公应用，支持审批、考勤、消息推送等功能', 2, 2, '进行中', '2025-03-01', '2025-10-31', 3000000.00),
(3, '数据中台建设项目', '统一数据治理平台，实现企业数据资产化管理', 1, 1, '进行中', '2025-06-01', '2026-06-30', 8000000.00),
(4, '智能客服系统', '基于AI的智能客服平台，支持多渠道接入和智能问答', 3, 3, '已完成', '2024-01-01', '2024-12-31', 2000000.00),
(5, 'ERP系统升级', '企业资源规划系统全面升级，优化供应链管理流程', 5, 5, '进行中', '2025-07-01', '2026-03-31', 6000000.00),
(6, '员工培训平台', '在线学习管理系统，支持课程管理、学习跟踪、考试测评', 4, 4, '已完成', '2024-06-01', '2025-03-31', 1500000.00),
(7, '营销自动化平台', '全渠道营销自动化系统，支持客户画像、精准推送', 3, 3, '进行中', '2025-04-01', '2025-12-31', 4000000.00),
(8, '供应链管理系统', '优化企业供应链流程，实现供应商管理和库存优化', 2, 2, '待启动', '2025-10-01', NULL, 3500000.00),
(9, 'CRM客户管理系统', '客户关系管理系统升级，提升客户服务质量', 3, 3, '已完成', '2023-01-01', '2023-12-31', 2500000.00),
(10, '云基础设施升级', '企业云平台架构升级，提升系统稳定性和扩展性', 16, 9, '进行中', '2025-08-01', '2026-02-28', 4500000.00);

-- 插入任务数据
INSERT INTO `oa_task` (`id`, `title`, `description`, `project_id`, `assignee_id`, `priority`, `status`, `due_date`, `progress`) VALUES
(1, '设计RAG系统架构', '完成企业级RAG知识库系统的整体架构设计，包括数据流向、模块划分', 1, 73, '高', '已完成', '2025-02-15', 100),
(2, '实现文档上传模块', '开发文档上传功能，支持PDF、DOCX、TXT等格式', 1, 6, '高', '已完成', '2025-03-30', 100),
(3, '实现向量检索引擎', '集成Milvus向量数据库，实现文档向量化和检索功能', 1, 9, '高', '进行中', '2025-06-30', 75),
(4, '实现语义重排序', '集成BGE-Reranker模型，提升检索结果相关性', 1, 10, '中', '进行中', '2025-07-15', 50),
(5, '开发前端界面', '实现知识库系统的前端UI，包括文档管理和问答界面', 1, 7, '高', '进行中', '2025-08-30', 60),
(6, '编写API接口文档', '完成系统API接口文档编写，便于前后端协作', 1, 12, '中', '待处理', '2025-09-15', 0),
(7, '移动端UI设计', '完成OA App的UI设计稿，包括首页、审批、考勤等页面', 2, 18, '高', '已完成', '2025-04-15', 100),
(8, '移动端前端开发', '实现OA App的前端页面开发', 2, 8, '高', '进行中', '2025-07-30', 80),
(9, '移动端后端接口', '开发移动端所需的后端API接口', 2, 11, '高', '进行中', '2025-07-30', 70),
(10, '移动端测试', '完成移动端App的功能测试和兼容性测试', 2, 14, '中', '待处理', '2025-09-30', 0),
(11, '数据仓库设计', '设计数据中台的数据仓库架构', 3, 73, '高', '已完成', '2025-07-15', 100),
(12, 'ETL流程开发', '开发数据抽取、转换、加载流程', 3, 12, '高', '进行中', '2025-09-30', 40),
(13, '数据质量监控', '实现数据质量监控和告警功能', 3, 15, '中', '待处理', '2025-11-15', 0),
(14, '智能问答模型训练', '训练客服问答模型，优化回答准确率', 4, 10, '高', '已完成', '2024-09-30', 100),
(15, '多渠道接入开发', '实现微信、钉钉、Web等多渠道接入', 4, 8, '高', '已完成', '2024-11-30', 100),
(16, 'ERP需求分析', '完成ERP系统升级的需求分析和方案设计', 5, 2, '高', '已完成', '2025-08-15', 100),
(17, 'ERP模块开发', '开发ERP系统的核心模块', 5, 9, '高', '进行中', '2025-12-31', 30),
(18, '培训课程管理', '实现培训平台的课程管理功能', 6, 20, '高', '已完成', '2024-12-31', 100),
(19, '学习进度跟踪', '开发学习进度跟踪和统计功能', 6, 21, '中', '已完成', '2025-02-28', 100),
(20, '营销自动化引擎', '开发营销自动化核心引擎', 7, 22, '高', '进行中', '2025-10-31', 55),
(21, '客户画像分析', '实现客户画像和精准推荐功能', 7, 23, '中', '进行中', '2025-11-15', 40),
(22, '供应链需求调研', '完成供应链管理系统的需求调研', 8, 20, '高', '待处理', '2025-11-30', 0),
(23, 'CRM系统集成', '完成CRM系统与其他系统的集成', 9, 11, '高', '已完成', '2023-11-30', 100),
(24, '云平台架构设计', '完成云基础设施升级的架构设计', 10, 16, '高', '已完成', '2025-09-15', 100),
(25, '云资源迁移', '实现现有系统向新云平台的迁移', 10, 17, '高', '进行中', '2025-12-31', 25),
(26, '性能优化', '对系统进行性能优化，提升响应速度', 1, 9, '中', '待处理', '2025-10-31', 0),
(27, '安全审计', '完成系统安全审计和漏洞修复', 1, 16, '高', '待处理', '2025-12-15', 0),
(28, '用户手册编写', '编写系统用户操作手册', 1, 20, '低', '待处理', '2026-01-31', 0),
(29, '部署脚本编写', '编写系统部署和运维脚本', 1, 17, '中', '待处理', '2025-11-30', 0),
(30, '测试用例编写', '编写系统功能测试用例', 1, 14, '中', '进行中', '2025-08-30', 30);

-- 插入考勤数据（最近一年的考勤记录）
INSERT INTO `oa_attendance` (`id`, `employee_id`, `date`, `check_in_time`, `check_out_time`, `status`, `leave_type`, `hours`, `remark`) VALUES
(1, 1, '2025-06-01', '08:55:00', '18:30:00', '正常', NULL, NULL, NULL),
(2, 1, '2025-06-02', '09:05:00', '18:15:00', '迟到', NULL, NULL, '交通拥堵'),
(3, 1, '2025-06-03', '08:45:00', '17:30:00', '早退', NULL, NULL, '提前离开'),
(4, 1, '2025-06-04', '08:50:00', '18:45:00', '正常', NULL, NULL, NULL),
(5, 1, '2025-06-05', NULL, NULL, '请假', '事假', 8.00, '个人事务'),
(6, 2, '2025-06-01', '09:00:00', '18:20:00', '正常', NULL, NULL, NULL),
(7, 2, '2025-06-02', '08:58:00', '18:35:00', '正常', NULL, NULL, NULL),
(8, 2, '2025-06-03', '09:10:00', '18:00:00', '迟到', NULL, NULL, '送孩子上学'),
(9, 2, '2025-06-04', '08:40:00', '19:00:00', '正常', NULL, NULL, NULL),
(10, 2, '2025-06-05', NULL, NULL, '请假', '病假', 8.00, '身体不适'),
(11, 6, '2025-06-01', '09:02:00', '18:10:00', '迟到', NULL, NULL, NULL),
(12, 6, '2025-06-02', '08:55:00', '18:45:00', '正常', NULL, NULL, NULL),
(13, 6, '2025-06-03', '08:48:00', '18:30:00', '正常', NULL, NULL, NULL),
(14, 6, '2025-06-04', '09:08:00', '18:20:00', '迟到', NULL, NULL, NULL),
(15, 6, '2025-06-05', '08:52:00', '17:30:00', '早退', NULL, NULL, '接孩子'),
(16, 7, '2025-06-01', '08:50:00', '18:25:00', '正常', NULL, NULL, NULL),
(17, 7, '2025-06-02', '08:58:00', '18:40:00', '正常', NULL, NULL, NULL),
(18, 7, '2025-06-03', '09:03:00', '18:15:00', '迟到', NULL, NULL, NULL),
(19, 7, '2025-06-04', '08:45:00', '18:50:00', '正常', NULL, NULL, NULL),
(20, 7, '2025-06-05', NULL, NULL, '请假', '年假', 8.00, '年假休息'),
(21, 9, '2025-06-01', '08:30:00', '19:00:00', '正常', NULL, NULL, NULL),
(22, 9, '2025-06-02', '08:45:00', '18:30:00', '正常', NULL, NULL, NULL),
(23, 9, '2025-06-03', '09:00:00', '18:15:00', '正常', NULL, NULL, NULL),
(24, 9, '2025-06-04', '08:55:00', '18:40:00', '正常', NULL, NULL, NULL),
(25, 9, '2025-06-05', '08:58:00', '18:25:00', '正常', NULL, NULL, NULL),
(26, 10, '2025-06-01', '09:05:00', '18:30:00', '迟到', NULL, NULL, NULL),
(27, 10, '2025-06-02', '08:52:00', '18:45:00', '正常', NULL, NULL, NULL),
(28, 10, '2025-06-03', '08:48:00', '18:20:00', '正常', NULL, NULL, NULL),
(29, 10, '2025-06-04', '09:00:00', '18:35:00', '正常', NULL, NULL, NULL),
(30, 10, '2025-06-05', NULL, NULL, '旷工', NULL, NULL, '无故缺勤'),
(31, 13, '2025-06-01', '08:55:00', '18:00:00', '正常', NULL, NULL, NULL),
(32, 13, '2025-06-02', '09:00:00', '18:10:00', '正常', NULL, NULL, NULL),
(33, 13, '2025-06-03', '08:45:00', '17:30:00', '早退', NULL, NULL, '提前下班'),
(34, 13, '2025-06-04', '08:58:00', '18:25:00', '正常', NULL, NULL, NULL),
(35, 13, '2025-06-05', '08:50:00', '18:30:00', '正常', NULL, NULL, NULL),
(36, 16, '2025-06-01', '08:00:00', '18:30:00', '正常', NULL, NULL, NULL),
(37, 16, '2025-06-02', '07:55:00', '18:45:00', '正常', NULL, NULL, NULL),
(38, 16, '2025-06-03', '08:10:00', '18:20:00', '正常', NULL, NULL, NULL),
(39, 16, '2025-06-04', '07:45:00', '19:00:00', '正常', NULL, NULL, NULL),
(40, 16, '2025-06-05', '08:05:00', '18:15:00', '正常', NULL, NULL, NULL);

-- 继续插入更多考勤数据（覆盖更多员工）
INSERT INTO `oa_attendance` (`id`, `employee_id`, `date`, `check_in_time`, `check_out_time`, `status`, `leave_type`, `hours`, `remark`) VALUES
(41, 14, '2025-06-01', '08:52:00', '18:15:00', '正常', NULL, NULL, NULL),
(42, 14, '2025-06-02', '09:08:00', '18:30:00', '迟到', NULL, NULL, NULL),
(43, 14, '2025-06-03', '08:48:00', '18:20:00', '正常', NULL, NULL, NULL),
(44, 14, '2025-06-04', '08:55:00', '18:40:00', '正常', NULL, NULL, NULL),
(45, 14, '2025-06-05', NULL, NULL, '请假', '调休', 8.00, '调休'),
(46, 18, '2025-06-01', '09:00:00', '18:30:00', '正常', NULL, NULL, NULL),
(47, 18, '2025-06-02', '08:55:00', '18:15:00', '正常', NULL, NULL, NULL),
(48, 18, '2025-06-03', '09:12:00', '18:25:00', '迟到', NULL, NULL, NULL),
(49, 18, '2025-06-04', '08:45:00', '18:00:00', '早退', NULL, NULL, '早退'),
(50, 18, '2025-06-05', '08:58:00', '18:35:00', '正常', NULL, NULL, NULL),
(51, 20, '2025-06-01', '09:05:00', '18:45:00', '迟到', NULL, NULL, NULL),
(52, 20, '2025-06-02', '08:50:00', '18:20:00', '正常', NULL, NULL, NULL),
(53, 20, '2025-06-03', '08:55:00', '18:30:00', '正常', NULL, NULL, NULL),
(54, 20, '2025-06-04', '09:00:00', '18:15:00', '正常', NULL, NULL, NULL),
(55, 20, '2025-06-05', '08:48:00', '18:40:00', '正常', NULL, NULL, NULL),
(56, 22, '2025-06-01', '08:58:00', '18:25:00', '正常', NULL, NULL, NULL),
(57, 22, '2025-06-02', '09:02:00', '18:35:00', '迟到', NULL, NULL, NULL),
(58, 22, '2025-06-03', '08:45:00', '18:10:00', '正常', NULL, NULL, NULL),
(59, 22, '2025-06-04', '08:55:00', '18:45:00', '正常', NULL, NULL, NULL),
(60, 22, '2025-06-05', NULL, NULL, '请假', '事假', 4.00, '半天假'),
(61, 24, '2025-06-01', '09:00:00', '18:00:00', '正常', NULL, NULL, NULL),
(62, 24, '2025-06-02', '08:55:00', '18:10:00', '正常', NULL, NULL, NULL),
(63, 24, '2025-06-03', '09:08:00', '18:20:00', '迟到', NULL, NULL, NULL),
(64, 24, '2025-06-04', '08:50:00', '18:30:00', '正常', NULL, NULL, NULL),
(65, 24, '2025-06-05', '08:48:00', '18:15:00', '正常', NULL, NULL, NULL),
(66, 26, '2025-06-01', '08:52:00', '18:35:00', '正常', NULL, NULL, NULL),
(67, 26, '2025-06-02', '08:48:00', '18:20:00', '正常', NULL, NULL, NULL),
(68, 26, '2025-06-03', '09:00:00', '18:00:00', '正常', NULL, NULL, NULL),
(69, 26, '2025-06-04', '08:55:00', '18:40:00', '正常', NULL, NULL, NULL),
(70, 26, '2025-06-05', NULL, NULL, '请假', '病假', 8.00, '身体不适');

-- ============================================================
-- 【HR 模块测试数据】
-- ============================================================

-- 插入HR部门数据
INSERT INTO `hr_department` (`id`, `name`, `parent_id`, `head_count`, `current_count`, `description`, `status`) VALUES
(1, '技术研发中心', NULL, 50, 45, '负责公司核心技术研发', 1),
(2, '产品管理中心', NULL, 20, 18, '负责产品规划与设计', 1),
(3, '运营中心', NULL, 30, 27, '负责产品运营与市场推广', 1),
(4, '人力资源中心', NULL, 15, 12, '负责人力资源管理', 1),
(5, '财务管理中心', NULL, 10, 8, '负责财务核算与管理', 1),
(6, '前端开发部', 1, 20, 18, '负责前端技术开发', 1),
(7, '后端开发部', 1, 25, 22, '负责后端技术开发', 1),
(8, '测试运维部', 1, 15, 13, '负责测试与运维', 1);

-- 插入岗位数据
INSERT INTO `hr_position` (`id`, `name`, `department_id`, `level`, `salary_min`, `salary_max`, `requirements`, `responsibilities`, `status`, `open_date`) VALUES
(1, '高级前端工程师', 6, '高级', 20000.00, 35000.00, '本科及以上学历，5年以上前端开发经验，精通React/Vue/Angular', '负责前端架构设计和核心功能开发', '招聘中', '2025-01-15'),
(2, '中级前端工程师', 6, '中级', 12000.00, 20000.00, '本科及以上学历，3年以上前端开发经验，熟悉React/Vue', '负责前端业务功能开发', '招聘中', '2025-03-01'),
(3, '初级前端工程师', 6, '初级', 8000.00, 12000.00, '本科及以上学历，1-2年前端开发经验', '协助完成前端开发任务', '招聘中', '2025-05-01'),
(4, '高级后端工程师', 7, '高级', 25000.00, 40000.00, '本科及以上学历，5年以上后端开发经验，精通Java/Python', '负责后端架构设计和核心系统开发', '招聘中', '2025-02-01'),
(5, '中级后端工程师', 7, '中级', 15000.00, 25000.00, '本科及以上学历，3年以上后端开发经验，熟悉Java/Python', '负责后端业务模块开发', '招聘中', '2025-04-15'),
(6, '测试工程师', 8, '中级', 10000.00, 18000.00, '本科及以上学历，2年以上软件测试经验', '负责系统测试和质量保障', '招聘中', '2025-06-01'),
(7, '运维工程师', 8, '中级', 12000.00, 20000.00, '本科及以上学历，3年以上运维经验，熟悉Linux', '负责系统运维和监控', '暂停招聘', '2025-01-01'),
(8, '产品经理', 2, '高级', 20000.00, 35000.00, '本科及以上学历，5年以上产品经验，有互联网产品经验优先', '负责产品规划和需求分析', '招聘中', '2025-03-15'),
(9, '运营专员', 3, '初级', 6000.00, 10000.00, '本科及以上学历，1-2年运营经验', '协助完成日常运营工作', '招聘中', '2025-05-15'),
(10, 'HR专员', 4, '初级', 6000.00, 10000.00, '本科及以上学历，人力资源相关专业优先', '负责招聘和员工关系', '已关闭', '2024-06-01'),
(11, '财务专员', 5, '中级', 8000.00, 12000.00, '本科及以上学历，财务相关专业，有会计证书优先', '负责财务核算和报表', '招聘中', '2025-04-01'),
(12, '数据分析师', 1, '中级', 15000.00, 25000.00, '本科及以上学历，3年以上数据分析经验，熟悉SQL/Python', '负责数据挖掘和分析', '招聘中', '2025-06-15');

-- 插入候选人数据
INSERT INTO `hr_candidate` (`id`, `name`, `phone`, `email`, `position_id`, `source`, `resume_url`, `skills`, `education`, `experience`, `status`) VALUES
(1, '张明', '13900139001', 'zhangming@test.com', 1, 'BOSS直聘', 'https://resume.internsu.com/1.pdf', 'React,Vue,TypeScript,Webpack', '本科', 6, '面试中'),
(2, '李华', '13900139002', 'lihua@test.com', 1, '智联招聘', 'https://resume.internsu.com/2.pdf', 'React,Redux,JavaScript,CSS', '本科', 5, '待筛选'),
(3, '王芳', '13900139003', 'wangfang@test.com', 2, '拉勾', 'https://resume.internsu.com/3.pdf', 'Vue,ElementUI,JavaScript', '本科', 3, '筛选通过'),
(4, '陈伟', '13900139004', 'chenwei@test.com', 3, '内推', 'https://resume.internsu.com/4.pdf', 'HTML,CSS,JavaScript,Vue', '本科', 2, '待筛选'),
(5, '刘洋', '13900139005', 'liuyang@test.com', 4, 'BOSS直聘', 'https://resume.internsu.com/5.pdf', 'Java,SpringBoot,MySQL,Redis', '硕士', 7, '已录用'),
(6, '赵敏', '13900139006', 'zhaomin@test.com', 4, '猎头', 'https://resume.internsu.com/6.pdf', 'Java,Python,Docker,Kubernetes', '本科', 6, '面试中'),
(7, '孙鹏', '13900139007', 'sunpeng@test.com', 5, '智联招聘', 'https://resume.internsu.com/7.pdf', 'Python,Django,PostgreSQL', '本科', 4, '待筛选'),
(8, '周杰', '13900139008', 'zhoujie@test.com', 5, '拉勾', 'https://resume.internsu.com/8.pdf', 'Java,Spring,MySQL', '本科', 3, '筛选通过'),
(9, '吴涛', '13900139009', 'wutao@test.com', 6, '内推', 'https://resume.internsu.com/9.pdf', 'Selenium,JMeter,Python', '本科', 3, '已录用'),
(10, '郑浩', '13900139010', 'zhenghao@test.com', 6, 'BOSS直聘', 'https://resume.internsu.com/10.pdf', 'Appium,Postman,Java', '本科', 2, '待筛选'),
(11, '杨帆', '13900139011', 'yangfan@test.com', 7, '智联招聘', 'https://resume.internsu.com/11.pdf', 'Linux,Docker,Kubernetes,Prometheus', '本科', 4, '已拒绝'),
(12, '许静', '13900139012', 'xujing@test.com', 8, '拉勾', 'https://resume.internsu.com/12.pdf', '产品设计,需求分析,PRD', '本科', 5, '面试中'),
(13, '何欣', '13900139013', 'hexin@test.com', 8, '猎头', 'https://resume.internsu.com/13.pdf', '产品策略,数据分析,用户研究', '硕士', 6, '筛选通过'),
(14, '曹磊', '13900139014', 'caolei@test.com', 9, '内推', 'https://resume.internsu.com/14.pdf', '内容运营,活动策划,数据分析', '本科', 2, '待筛选'),
(15, '谢敏', '13900139015', 'xiemin@test.com', 10, 'BOSS直聘', 'https://resume.internsu.com/15.pdf', '招聘流程,员工关系,社保公积金', '本科', 3, '已录用'),
(16, '韩冰', '13900139016', 'hanbing@test.com', 11, '智联招聘', 'https://resume.internsu.com/16.pdf', '会计核算,财务报表,税务申报', '本科', 4, '面试中'),
(17, '唐亮', '13900139017', 'tangliang@test.com', 12, '拉勾', 'https://resume.internsu.com/17.pdf', 'SQL,Python,数据可视化', '硕士', 4, '筛选通过'),
(18, '冯丽', '13900139018', 'fengli@test.com', 1, 'BOSS直聘', 'https://resume.internsu.com/18.pdf', 'React,TypeScript,Next.js', '本科', 5, '待筛选'),
(19, '杨子', '13900139019', 'yangzi@test.com', 2, '内推', 'https://resume.internsu.com/19.pdf', 'Vue3,Vite,TailwindCSS', '本科', 3, '面试中'),
(20, '朱伟', '13900139020', 'zhuwei@test.com', 3, '智联招聘', 'https://resume.internsu.com/20.pdf', 'HTML,CSS,JavaScript', '大专', 2, '已拒绝'),
(21, '胡涛', '13900139021', 'hutao@test.com', 4, '猎头', 'https://resume.internsu.com/21.pdf', 'Java,SpringCloud,MongoDB', '本科', 8, '已录用'),
(22, '林静', '13900139022', 'linjing@test.com', 5, 'BOSS直聘', 'https://resume.internsu.com/22.pdf', 'Go,Gin,Redis', '本科', 3, '筛选通过'),
(23, '罗强', '13900139023', 'luoqiang@test.com', 6, '拉勾', 'https://resume.internsu.com/23.pdf', 'TestNG,Mockito,Python', '本科', 2, '待筛选'),
(24, '梁燕', '13900139024', 'liangyan@test.com', 7, '内推', 'https://resume.internsu.com/24.pdf', 'Linux,Ansible,GitLabCI', '本科', 3, '面试中'),
(25, '谢芳', '13900139025', 'xiefang@test.com', 8, '智联招聘', 'https://resume.internsu.com/25.pdf', '产品路线图,竞品分析,项目管理', '本科', 4, '已拒绝'),
(26, '宋涛', '13900139026', 'songtao@test.com', 9, 'BOSS直聘', 'https://resume.internsu.com/26.pdf', '用户运营,社群管理,活动运营', '本科', 2, '待筛选'),
(27, '邓华', '13900139027', 'denghua@test.com', 10, '拉勾', 'https://resume.internsu.com/27.pdf', 'HRIS,考勤管理,绩效评估', '本科', 3, '筛选通过'),
(28, '许磊', '13900139028', 'xulei@test.com', 11, '内推', 'https://resume.internsu.com/28.pdf', '成本核算,预算管理,财务分析', '硕士', 5, '面试中'),
(29, '何伟', '13900139029', 'hewei@test.com', 12, '猎头', 'https://resume.internsu.com/29.pdf', 'Python,Pandas,BI工具', '本科', 3, '已录用'),
(30, '孙丽', '13900139030', 'sunli@test.com', 1, 'BOSS直聘', 'https://resume.internsu.com/30.pdf', 'Angular,TypeScript,RxJS', '本科', 4, '待筛选');

-- 插入面试数据
INSERT INTO `hr_interview` (`id`, `candidate_id`, `position_id`, `interviewer_id`, `round`, `type`, `status`, `interview_date`, `result`, `score`, `feedback`) VALUES
(1, 1, 1, 6, 1, '技术面', '已面试', '2025-06-02 10:00:00', '候选人技术能力较强，对React有深入理解', 85, '建议进入二面'),
(2, 1, 1, 1, 2, '复试', '待面试', '2025-06-08 14:00:00', NULL, NULL, NULL),
(3, 5, 4, 9, 1, '技术面', '已面试', '2025-05-28 09:00:00', '候选人技术功底扎实，有大型项目经验', 92, '建议录用'),
(4, 5, 4, 1, 2, '终面', '已面试', '2025-06-01 15:00:00', '综合评估优秀，符合岗位要求', 90, '录用'),
(5, 9, 6, 13, 1, '技术面', '已面试', '2025-06-03 10:00:00', '测试知识全面，自动化测试经验丰富', 88, '建议录用'),
(6, 12, 8, 2, 1, 'HR面', '已面试', '2025-06-04 14:00:00', '沟通能力良好，对产品有热情', 80, '建议进入业务面'),
(7, 12, 8, 20, 2, '业务面', '待面试', '2025-06-10 10:00:00', NULL, NULL, NULL),
(8, 15, 10, 4, 1, 'HR面', '已面试', '2025-05-25 11:00:00', '人力资源专业知识扎实', 85, '录用'),
(9, 16, 11, 5, 1, '专业面', '已面试', '2025-06-05 09:00:00', '财务知识全面，有4年工作经验', 82, '建议进入复试'),
(10, 17, 12, 10, 1, '技术面', '已面试', '2025-06-06 14:00:00', '数据分析能力强，Python技能熟练', 88, '建议录用'),
(11, 21, 4, 9, 1, '技术面', '已面试', '2025-05-20 10:00:00', '架构设计能力优秀', 95, '建议进入终面'),
(12, 21, 4, 1, 2, '终面', '已面试', '2025-05-25 15:00:00', '综合能力突出', 92, '录用'),
(13, 29, 12, 10, 1, '技术面', '已面试', '2025-06-01 11:00:00', '数据敏感度高，分析能力强', 90, '建议录用'),
(14, 3, 2, 6, 1, '技术面', '待面试', '2025-06-09 10:00:00', NULL, NULL, NULL),
(15, 6, 4, 9, 1, '技术面', '已面试', '2025-06-04 09:00:00', '技术能力优秀，但薪资期望过高', 85, '待定'),
(16, 8, 5, 9, 1, '技术面', '待面试', '2025-06-11 14:00:00', NULL, NULL, NULL),
(17, 13, 8, 2, 1, 'HR面', '待面试', '2025-06-07 10:00:00', NULL, NULL, NULL),
(18, 19, 2, 6, 1, '技术面', '已面试', '2025-06-05 15:00:00', 'Vue3技能熟练，项目经验符合', 82, '建议进入复试'),
(19, 22, 5, 9, 1, '技术面', '待面试', '2025-06-12 09:00:00', NULL, NULL, NULL),
(20, 24, 7, 16, 1, '技术面', '已面试', '2025-06-03 14:00:00', '运维经验丰富，云平台知识扎实', 80, '建议进入复试');

-- ============================================================
-- 脚本结束
-- ============================================================
SELECT 'OA & HR 模块数据库脚本执行完成' AS result;