
package com.company.aiplatform.sql.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * 表信息 DTO。
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class TableInfo {

    /**
     * 表名
     */
    private String tableName;

    /**
     * 表注释（中文说明）
     */
    private String tableComment;

    /**
     * 字段列表
     */
    private List<ColumnInfo> columns;

    /**
     * 字段信息
     */
    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class ColumnInfo {
        /**
         * 字段名
         */
        private String columnName;

        /**
         * 数据类型
         */
        private String dataType;

        /**
         * 字段注释（中文说明）
         */
        private String columnComment;

        /**
         * 是否为主键
         */
        private Boolean isPrimaryKey;

        /**
         * 是否可空
         */
        private Boolean isNullable;
    }
}
