
package com.company.aiplatform.sql.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * SQL Schema 响应 DTO。
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SqlSchemaResponse {

    /**
     * 数据库名称
     */
    private String databaseName;

    /**
     * 表列表
     */
    private List<TableInfo> tables;

    /**
     * Schema 最后更新时间
     */
    private Long lastUpdated;
}
