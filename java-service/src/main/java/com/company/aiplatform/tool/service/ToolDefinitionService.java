package com.company.aiplatform.tool.service;

import com.company.aiplatform.tool.entity.ToolDefinition;
import java.util.List;
import java.util.Optional;

/**
 * Tool definition service.
 *
 * <p>V3: Added CRUD operations for tool management.
 */
public interface ToolDefinitionService {

    /** Query all enabled tools */
    List<ToolDefinition> listEnabledTools();

    /** Query all tools (including disabled) */
    List<ToolDefinition> listAllTools();

    /** Find tool by name */
    Optional<ToolDefinition> findByName(String name);

    /** Enable or disable a tool by name */
    boolean setEnabled(String name, boolean enabled);

    /** Update tool config JSON */
    boolean updateConfig(String name, String configJson);
}
