
package com.company.aiplatform.sql.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * SQL 查询响应 DTO。
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SqlQueryResponse {

    /**
     * 最终的自然语言回答
     */
    private String answer;

    /**
     * 生成的 SQL 语句
     */
    private String executedSql;

    /**
     * 查询结果的原始数据
     */
    private QueryResultData resultData;

    /**
     * 执行耗时（毫秒）
     */
    private Long executionTimeMs;

    /**
     * 执行状态：success / failed / security_blocked
     */
    private String status;

    /**
     * 错误信息（如果执行失败）
     */
    private String errorMessage;

    /**
     * 执行步骤追踪（用于前端展示工作过程）
     */
    private List<TraceStep> traceSteps;

    /**
     * 查询结果数据结构
     */
    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class QueryResultData {
        /**
         * 列名列表
         */
        private List<String> columns;

        /**
         * 行数据（二维数组）
         */
        private List<List<Object>> rows;

        /**
         * 总行数
         */
        private Integer rowCount;
    }

    /**
     * 执行步骤追踪
     */
    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class TraceStep {
        /**
         * 步骤名称
         */
        private String name;

        /**
         * 步骤描述
         */
        private String description;

        /**
         * 耗时（毫秒）
         */
        private Long durationMs;
    }
}
