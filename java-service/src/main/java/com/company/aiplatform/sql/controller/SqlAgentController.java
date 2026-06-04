package com.company.aiplatform.sql.controller;

import com.company.aiplatform.thirdparty.client.AIServiceClient;
import com.company.aiplatform.common.result.Result;
import com.company.aiplatform.sql.dto.SqlSchemaResponse;
import com.company.aiplatform.sql.dto.TableInfo;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * SQL Agent 管理控制器 —— 数据库 Schema 和表信息查询。
 *
 * <h2>v2 变更（统一入口）</h2>
 * SQL 自然语言查询能力已合并至 {@code POST /api/ai/chat}，
 * 由 Python LangGraph 的 intent_node 自动识别为 sql 意图并路由到 sql_node。
 * 本控制器仅保留数据库元数据查询接口。
 *
 * <h2>保留的端点</h2>
 * <ul>
 *   <li>{@code GET /api/sql/schema}  — 数据库 Schema 信息</li>
 *   <li>{@code GET /api/sql/tables}  — 可查询表列表</li>
 * </ul>
 *
 * <h2>已移除的端点（合并至 /api/ai/chat）</h2>
 * <ul>
 *   <li>{@code POST /api/sql/query}        — 自然语言 SQL 查询（非流式）</li>
 *   <li>{@code POST /api/sql/query/stream} — 自然语言 SQL 查询（流式）</li>
 * </ul>
 */

@Tag(name = "sql", description = "SQL Agent 管理控制器")
@Slf4j
@RestController
@RequestMapping("/api/sql")
@RequiredArgsConstructor
public class SqlAgentController {

    private final AIServiceClient aiServiceClient;

    /**
     * 获取数据库 Schema 信息。
     *
     * @return Schema 信息（表列表及其字段定义）
     */
    @Operation(summary = "获取数据库 Schema 信息")
    @GetMapping("/schema")
    public Result<SqlSchemaResponse> getSchema() {
        log.info("Get SQL schema request");
        return Result.success(aiServiceClient.getSqlSchema().block());
    }

    /**
     * 获取可查询的表列表。
     *
     * @return 表列表
     */
    @Operation(summary = "获取可查询的表列表")
    @GetMapping("/tables")
    public Result<List<TableInfo>> getTables() {
        log.info("Get SQL tables request");
        return Result.success(aiServiceClient.getSqlTables().block());
    }
}
