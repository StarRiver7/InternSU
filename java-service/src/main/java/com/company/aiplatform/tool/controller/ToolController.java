package com.company.aiplatform.tool.controller;

import com.company.aiplatform.common.result.Result;
import com.company.aiplatform.tool.entity.ToolDefinition;
import com.company.aiplatform.tool.service.ToolDefinitionService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * Tool management controller — V3 with full CRUD.
 *
 * <p>Provides:
 * <ul>
 *   <li>List all enabled tools (used by Python Agent for function calling)</li>
 *   <li>List all tools including disabled (admin)</li>
 *   <li>Enable/disable tools at runtime</li>
 *   <li>Update tool configuration</li>
 * </ul>
 *
 * <p>Usage flow:
 * <ol>
 *   <li>Python Agent starts up, calls {@code GET /list} to discover tools</li>
 *   <li>Python Agent registers tools from DB into its ToolRegistry</li>
 *   <li>LLM selects tool based on descriptions, ToolManager executes</li>
 * </ol>
 */
@Tag(name = "Tool Management", description = "Tool definition query and management")
@RestController
@RequestMapping("/api/v1/tools")
@RequiredArgsConstructor
public class ToolController {

    private final ToolDefinitionService toolDefinitionService;

    // ======================== Query ========================

    /**
     * List all enabled tools.
     *
     * <p>Called by Python Agent on startup to build its ToolRegistry.
     * Only returns tools with is_active=1.
     *
     * @return List of enabled tool definitions.
     */
    @Operation(summary = "List all enabled tools")
    @GetMapping("/list")
    public Result<List<ToolDefinition>> listEnabledTools() {
        List<ToolDefinition> tools = toolDefinitionService.listEnabledTools();
        return Result.success(tools);
    }

    /**
     * List all tools (including disabled).
     *
     * <p>For admin management UI.
     *
     * @return List of all tool definitions.
     */
    @Operation(summary = "List all tools (admin)")
    @GetMapping("/admin/list")
    public Result<List<ToolDefinition>> listAllTools() {
        List<ToolDefinition> tools = toolDefinitionService.listAllTools();
        return Result.success(tools);
    }

    /**
     * Get tool by name.
     *
     * @param name Tool name (e.g. 'sql_query', 'feishu_summary').
     * @return Tool definition if found.
     */
    @Operation(summary = "Get tool by name")
    @GetMapping("/{name}")
    public Result<ToolDefinition> getTool(
            @Parameter(description = "Tool name") @PathVariable String name) {
        Optional<ToolDefinition> tool = toolDefinitionService.findByName(name);
        return tool.map(Result::success)
                .orElse(Result.fail(404, "Tool not found: " + name));
    }

    // ======================== Management ========================

    /**
     * Enable or disable a tool at runtime.
     *
     * <p>Disabled tools are not returned by /list and are not available
     * for LLM function calling. Existing ToolRegistry instances need to
     * refresh to pick up the change.
     *
     * @param name Tool name.
     * @param body Request body with "enabled": true/false.
     * @return Success indication.
     */
    @Operation(summary = "Enable or disable a tool")
    @PutMapping("/{name}/enabled")
    public Result<Void> setEnabled(
            @Parameter(description = "Tool name") @PathVariable String name,
            @RequestBody Map<String, Boolean> body) {
        Boolean enabled = body.getOrDefault("enabled", true);
        boolean ok = toolDefinitionService.setEnabled(name, enabled);
        if (ok) {
            return Result.success(null);
        }
        return Result.fail(404, "Tool not found: " + name);
    }

    /**
     * Update tool configuration.
     *
     * <p>Allows runtime config changes without restart (e.g. model name,
     * API endpoint, threshold values).
     *
     * @param name Tool name.
     * @param body Request body with "config_json": "{...}".
     * @return Success indication.
     */
    @Operation(summary = "Update tool configuration")
    @PutMapping("/{name}/config")
    public Result<Void> updateConfig(
            @Parameter(description = "Tool name") @PathVariable String name,
            @RequestBody Map<String, String> body) {
        String configJson = body.getOrDefault("config_json", "{}");
        boolean ok = toolDefinitionService.updateConfig(name, configJson);
        if (ok) {
            return Result.success(null);
        }
        return Result.fail(404, "Tool not found: " + name);
    }
}
