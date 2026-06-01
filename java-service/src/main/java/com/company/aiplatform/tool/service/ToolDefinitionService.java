package com.company.aiplatform.tool.service;

import com.company.aiplatform.tool.entity.ToolDefinition;
import java.util.List;

public interface ToolDefinitionService {

    /** 查询所有已启用的工具列表 */
    List<ToolDefinition> listEnabledTools();
}
