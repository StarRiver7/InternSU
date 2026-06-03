
package com.company.aiplatform.sql.controller;

import com.company.aiplatform.thirdparty.client.AIServiceClient;
import com.company.aiplatform.common.result.Result;
import com.company.aiplatform.sql.dto.SqlQueryRequest;
import com.company.aiplatform.sql.dto.SqlQueryResponse;
import com.company.aiplatform.sql.dto.SqlSchemaResponse;
import com.company.aiplatform.sql.dto.TableInfo;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.List;

/**
 * SQL Agent 控制器 —— 数据库自然语言查询接口。
 *
 * <h2>架构角色</h2>
 * 提供 SQL Agent 功能的 REST API 入口，支持：
 * <ul>
 *   <li>自然语言转 SQL 查询</li>
 *   <li>数据库 Schema 信息获取</li>
 *   <li>可查询表列表获取</li>
 * </ul>
 *
 * <h2>安全边界</h2>
 * SQL Agent 执行的 SQL 经过多重安全校验：
 * <ol>
 *   <li>只读限制：禁止 INSERT/UPDATE/DELETE/DROP/TRUNCATE</li>
 *   <li>危险操作拦截：禁止 EXECUTE/SET/SHOW 等敏感命令</li>
 *   <li>行数限制：查询结果最多返回 100 行</li>
 *   <li>超时限制：单查询最长执行 30 秒</li>
 * </ol>
 */
@Slf4j
@RestController
@RequestMapping("/api/sql")
@RequiredArgsConstructor
public class SqlAgentController {

    private final AIServiceClient aiServiceClient;

    /**
     * SQL 查询（非流式）。
     *
     * <p>将用户的自然语言问题转换为 SQL 并执行，返回查询结果的自然语言总结。
     *
     * @param request SQL 查询请求
     * @return 查询结果（包含执行的 SQL、原始数据、自然语言总结）
     */
    @PostMapping("/query")
    public Result<SqlQueryResponse> query(@Valid @RequestBody SqlQueryRequest request) {
        log.info("SQL query request: user={}, question={}",
                request.getUserId(), request.getQuestion());

        return Result.success(aiServiceClient.sqlQuery(
                request.getUserId(),
                request.getConversationId(),
                request.getQuestion()
        ).block());
    }

    /**
     * SQL 查询（SSE 流式）。
     *
     * <p>将用户的自然语言问题转换为 SQL 并执行，通过 SSE 流式返回执行过程和结果。
     *
     * @param request SQL 查询请求
     * @return SSE 事件流（包含执行步骤、中间结果、最终总结）
     */
    @PostMapping(value = "/query/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter queryStream(@Valid @RequestBody SqlQueryRequest request) {
        log.info("SQL query stream request: user={}, question={}",
                request.getUserId(), request.getQuestion());

        return aiServiceClient.sqlQueryStream(
                request.getUserId(),
                request.getConversationId(),
                request.getQuestion()
        );
    }

    /**
     * 获取数据库 Schema 信息。
     *
     * <p>返回当前可查询数据库的所有表结构信息，用于前端展示和用户提示。
     *
     * @return Schema 信息（表列表及其字段定义）
     */
    @GetMapping("/schema")
    public Result<SqlSchemaResponse> getSchema() {
        log.info("Get SQL schema request");
        return Result.success(aiServiceClient.getSqlSchema().block());
    }

    /**
     * 获取可查询的表列表。
     *
     * <p>返回当前用户有权限查询的所有表名称，用于前端下拉选择。
     *
     * @return 表列表
     */
    @GetMapping("/tables")
    public Result<List<TableInfo>> getTables() {
        log.info("Get SQL tables request");
        return Result.success(aiServiceClient.getSqlTables().block());
    }
}
