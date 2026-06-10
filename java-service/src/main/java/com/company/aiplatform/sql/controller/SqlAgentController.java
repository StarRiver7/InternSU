package com.company.aiplatform.sql.controller;

import com.company.aiplatform.common.result.Result;
import com.company.aiplatform.sql.dto.SqlExecuteRequest;
import com.company.aiplatform.sql.dto.SqlExecuteResponse;
import com.company.aiplatform.sql.dto.SqlSchemaResponse;
import com.company.aiplatform.sql.dto.TableInfo;
import com.company.aiplatform.common.enums.ResultCode;
import com.company.aiplatform.common.exception.BusinessException;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;

import java.util.*;

/**
 * SQL Agent 控制器 —— 数据库 Schema、表信息查询与 SQL 执行（全部直连 MySQL）。
 *
 * <h2>v4 变更（全面直连）</h2>
 * Schema / Tables 接口不再代理到 Python，改为 Java 直接查询 internsu_business。
 *
 * <h2>端点清单</h2>
 * <ul>
 *   <li>{@code GET  /api/sql/schema}   — 数据库 Schema（直连 MySQL）</li>
 *   <li>{@code GET  /api/sql/tables}   — 表列表（直连 MySQL）</li>
 *   <li>{@code POST /api/sql/execute}  — 执行 SQL（Python → Java 内部调用）</li>
 * </ul>
 */
@Tag(name = "sql", description = "SQL Agent 控制器")
@Slf4j
@RestController
@RequestMapping("/api/sql")
@RequiredArgsConstructor
public class SqlAgentController {

    @Qualifier("businessJdbcTemplate")
    private final JdbcTemplate businessJdbcTemplate;

    @Value("${ai.backend.api-key}")
    private String apiKey;

    private static final int MAX_ROWS = 1000;
    private static final String BUSINESS_DB = "internsu_business";

    // ═══════════════════════════════════════════════════════════
    // Schema —— 获取数据库 Schema 信息
    // ═══════════════════════════════════════════════════════════

    @Operation(summary = "获取数据库 Schema 信息")
    @GetMapping("/schema")
    public Result<SqlSchemaResponse> getSchema() {
        log.info("将从此数据库获取信息： {}", BUSINESS_DB);

        String tableSql = "SELECT TABLE_NAME, TABLE_COMMENT FROM INFORMATION_SCHEMA.TABLES"
                + " WHERE TABLE_SCHEMA = '" + BUSINESS_DB + "' ORDER BY TABLE_NAME";
        List<Map<String, Object>> tableRows = businessJdbcTemplate.queryForList(tableSql);

        List<TableInfo> tables = new ArrayList<>();
        for (Map<String, Object> tr : tableRows) {
            String tableName = (String) tr.get("TABLE_NAME");
            String tableComment = (String) tr.get("TABLE_COMMENT");

            List<TableInfo.ColumnInfo> columns = loadColumns(tableName);

            tables.add(TableInfo.builder()
                    .tableName(tableName)
                    .tableComment(tableComment != null ? tableComment : "")
                    .columns(columns)
                    .build());
        }

        return Result.success(SqlSchemaResponse.builder()
                .databaseName(BUSINESS_DB)
                .tables(tables)
                .lastUpdated(System.currentTimeMillis() / 1000)
                .build());
    }

    // ═══════════════════════════════════════════════════════════
    // Tables —— 获取可查询的表列表
    // ═══════════════════════════════════════════════════════════

    @Operation(summary = "获取可查询的表列表")
    @GetMapping("/tables")
    public Result<List<TableInfo>> getTables(
            @RequestParam(defaultValue = "true") boolean simple) {
        log.info("将从此数据库获取信息： {}", BUSINESS_DB);

        String sql = "SELECT TABLE_NAME, TABLE_COMMENT FROM INFORMATION_SCHEMA.TABLES"
                + " WHERE TABLE_SCHEMA = '" + BUSINESS_DB + "' ORDER BY TABLE_NAME";
        List<Map<String, Object>> rows = businessJdbcTemplate.queryForList(sql);

        List<TableInfo> tables = new ArrayList<>();
        for (Map<String, Object> row : rows) {
            String tableName = (String) row.get("TABLE_NAME");
            String comment = (String) row.get("TABLE_COMMENT");

            TableInfo.TableInfoBuilder builder = TableInfo.builder()
                    .tableName(tableName)
                    .tableComment(comment != null ? comment : "");

            if (!simple) {
                builder.columns(loadColumns(tableName));
            }

            tables.add(builder.build());
        }

        return Result.success(tables);
    }

    // ═══════════════════════════════════════════════════════════
    // SQL 执行（内部服务调用：Python → Java）
    // ═══════════════════════════════════════════════════════════

    @Operation(summary = "执行 SQL 查询（内部接口）")
    @PostMapping("/execute")
    public Result<SqlExecuteResponse> executeSql(
            @RequestHeader(value = "X-Api-Key", required = false) String apiKeyHeader,
            @Valid @RequestBody SqlExecuteRequest request) {

        if (apiKeyHeader == null || !apiKeyHeader.equals(apiKey)) {
            log.warn("SQL 执行: X-Api-Key 无效或缺失");
            throw new BusinessException(ResultCode.FORBIDDEN, "Invalid API Key");
        }

        String sql = request.getSql().trim();
        log.info("SQL 执行: sql_preview={}", sql.length() > 200 ? sql.substring(0, 200) + "..." : sql);

        String upper = sql.toUpperCase().replaceAll("\\s+", " ").trim();
        if (!upper.startsWith("SELECT") && !upper.startsWith("SHOW")
                && !upper.startsWith("DESCRIBE") && !upper.startsWith("EXPLAIN")
                && !upper.startsWith("WITH")) {
            log.warn("SQL 执行被阻止: 非只读 SQL");
            throw new BusinessException(ResultCode.BAD_REQUEST, "仅允许只读查询（SELECT/SHOW/DESCRIBE/EXPLAIN）");
        }

        // 对于聚合查询（SELECT COUNT/SUM/AVG/MAX/MIN），不需要添加 LIMIT
        // 聚合函数只返回一行结果，加 LIMIT 没有意义
        if (!upper.contains("LIMIT")) {
            // 检查是否是聚合查询（SELECT 后紧跟 COUNT/SUM/AVG/MAX/MIN）
            boolean isAggregateQuery = upper.matches("SELECT\\s+(COUNT|SUM|AVG|MAX|MIN)\\s*\\(");
            if (!isAggregateQuery) {
                sql = sql.replaceAll(";+$", "").trim() + " LIMIT " + MAX_ROWS;
            }
        }

        try {
            List<Map<String, Object>> rows = businessJdbcTemplate.queryForList(sql);

            List<String> columns = rows.isEmpty()
                    ? Collections.emptyList()
                    : new ArrayList<>(rows.get(0).keySet());

            if (rows.size() > MAX_ROWS) {
                rows = rows.subList(0, MAX_ROWS);
            }

            return Result.success(SqlExecuteResponse.builder()
                    .columns(columns)
                    .rows(rows)
                    .rowCount(rows.size())
                    .build());

        } catch (Exception e) {
            log.error("SQL 执行失败: {}", e.getMessage());
            throw new BusinessException(ResultCode.INTERNAL_ERROR,
                    "SQL 执行失败: " + e.getMessage());
        }
    }

    // ═══════════════════════════════════════════════════════════
    // 内部方法
    // ═══════════════════════════════════════════════════════════

    private List<TableInfo.ColumnInfo> loadColumns(String tableName) {
        String sql = "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_KEY, COLUMN_COMMENT"
                + " FROM INFORMATION_SCHEMA.COLUMNS"
                + " WHERE TABLE_SCHEMA = '" + BUSINESS_DB + "'"
                + " AND TABLE_NAME = '" + tableName + "'"
                + " ORDER BY ORDINAL_POSITION";
        List<Map<String, Object>> rows = businessJdbcTemplate.queryForList(sql);

        List<TableInfo.ColumnInfo> columns = new ArrayList<>();
        for (Map<String, Object> row : rows) {
            columns.add(TableInfo.ColumnInfo.builder()
                    .columnName((String) row.get("COLUMN_NAME"))
                    .dataType((String) row.get("DATA_TYPE"))
                    .isNullable("YES".equals(row.get("IS_NULLABLE")))
                    .isPrimaryKey("PRI".equals(row.get("COLUMN_KEY")))
                    .columnComment(row.get("COLUMN_COMMENT") != null
                            ? (String) row.get("COLUMN_COMMENT") : "")
                    .build());
        }
        return columns;
    }
}