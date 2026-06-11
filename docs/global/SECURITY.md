# Security Checklist — Enterprise AI Agent Platform

> 上线前必须逐项检查通过。标记: [ ] 未检 / [x] 已通过 / [-] 不适用

---

## 1. 依赖安全审计

- [ ] `mvn dependency-check:check` — Java OWASP依赖漏洞扫描（无HIGH/CRITICAL）
- [ ] `pip-audit` 或 `safety check` — Python依赖漏洞扫描
- [ ] Docker基础镜像锁定版本tag，禁止`:latest`
- [ ] 所有第三方库使用已知稳定版本，无SNAPSHOT依赖

## 2. 认证与授权

- [ ] JWT Secret 长度 >= 256 bits，存储于外部密钥文件/环境变量
- [ ] JWT Access Token 过期时间 <= 24h
- [ ] 所有 `/api/v1/*` 接口（除auth外）必须通过JWT认证
- [ ] `/api/v1/admin/*` 接口额外校验 admin 角色（@PreAuthorize）
- [ ] Python `/ai/*` 接口通过 `X-Api-Key` 头鉴权
- [ ] 密码使用 BCrypt 加密存储（cost >= 10）
- [ ] 登录失败不暴露具体原因（统一提示"用户名或密码错误"）

## 3. 数据安全

- [ ] 数据库连接使用SSL/TLS（生产环境强制）
- [ ] 敏感字段（密码）不在日志/API响应中输出
- [ ] SQL Agent三层安全防护：语法校验 + 危险拦截 + 只读从库
- [ ] 所有DELETE操作使用逻辑删除（is_deleted=1）
- [ ] 数据库备份策略就位（每日全量 + binlog增量）

## 4. 网络安全

- [ ] Python AI Service 端口(8000)不对外暴露，仅内网/容器网络可访问
- [ ] CORS配置：生产环境不允许 `*`，限定具体域名
- [ ] HTTPS 强制启用（生产环境配置TLS证书）
- [ ] API限流就位：用户级(20次/分钟) + 全局限流(Token日配额)

## 5. 容器安全

- [ ] 容器以非root用户运行（UID 1001）
- [ ] 镜像不含构建工具（gcc/make）— 多阶段构建已隔离
- [ ] HEALTHCHECK指令已配置，Docker Compose依赖条件已设置
- [ ] 敏感信息通过.env文件注入，不写入Dockerfile/镜像层
- [ ] 容器资源限制已配置（CPU/Memory limits）

## 6. 日志与审计

- [ ] 登录操作全量记录（成功/失败、IP、UA）
- [ ] Tool调用全量记录（参数、结果、耗时、用户）
- [ ] Workflow执行生命周期全量记录
- [ ] 日志中不包含明文密码/JWT Token
- [ ] 错误日志单独输出（ERROR_FILE appender）
- [ ] 生产环境日志轮转策略：30天保留，3GB上限

## 7. 接口安全

- [ ] 所有用户输入经过参数校验（@Valid / Pydantic）
- [ ] SQL注入防护：MyBatis Plus参数化查询 + SQL Agent安全拦截
- [ ] XSS防护：API响应Content-Type正确设置
- [ ] CSRF：无状态JWT架构，CSRF天然免疫
- [ ] 文件上传：类型白名单（pdf/docx/md/txt）+ 大小限制

## 8. 运维安全

- [ ] Actuator端点：生产环境仅暴露health/info，关闭env/configmappings
- [ ] 应用端口不与宿主机冲突
- [ ] 优雅关闭（Graceful Shutdown）已启用
- [ ] 健康检查端点独立于业务端口（可选）
- [ ] K8s部署：配置readinessProbe + livenessProbe

---

## 上线前最终检查

| # | 检查项 | 状态 |
|---|--------|------|
| 1 | 所有单元测试通过（Java + Python） | [ ] |
| 2 | 集成测试覆盖核心API端点 | [ ] |
| 3 | Docker Compose一键启动6个服务正常 | [ ] |
| 4 | 所有healthcheck返回200 | [ ] |
| 5 | JWT登录 -> Token校验 -> API调用闭环验证 | [ ] |
| 6 | 数据库迁移脚本（Flyway）在空库执行无报错 | [ ] |
| 7 | 日志文件正常产出，格式符合规范 | [ ] |
| 8 | Prometheus metrics端点可访问 | [ ] |
| 9 | 压力测试：100并发下P95 < 2s | [ ] |
| 10 | 安全扫描无HIGH/CRITICAL漏洞 | [ ] |
