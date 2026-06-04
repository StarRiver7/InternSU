package com.company.aiplatform.sql.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * SQL 执行请求 DTO —— Python AI 服务通过 HTTP 调用 Java 执行 SQL。
 *
 * <p>该接口为服务间内部调用，由 Python 的 sql_node 生成 SQL 后通过
 * {@code POST /api/sql/execute} 发送到 Java 端执行。</p>
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SqlExecuteRequest {

    /** 经过安全校验的只读 SQL 语句 */
    @NotBlank(message = "SQL 不能为空")
    private String sql;
}