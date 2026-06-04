package com.company.aiplatform.sql.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;
import java.util.Map;

/**
 * SQL 执行响应 DTO —— Java 执行 SQL 后返回给 Python。
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SqlExecuteResponse {

    /** 列名列表 */
    private List<String> columns;

    /** 数据行列表，每行为 Map(列名 → 值) */
    private List<Map<String, Object>> rows;

    /** 返回行数 */
    private int rowCount;
}