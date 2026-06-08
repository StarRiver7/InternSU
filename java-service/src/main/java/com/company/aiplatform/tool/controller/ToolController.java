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
 * 工具管理控制器 — V3 完整 CRUD 版本.
 *
 * <p>提供功能:
 * <ul>
 *   <li>列出所有启用的工具（供 Python Agent 进行函数调用）</li>
 *   <li>列出所有工具（包含已禁用，管理员使用）</li>
 *   <li>运行时启用/禁用工具</li>
 *   <li>更新工具配置</li>
 * </ul>
 *
 * <p>使用流程:
 * <ol>
 *   <li>Python Agent 启动时调用 {@code GET /list} 发现可用工具</li>
 *   <li>Python Agent 从数据库注册工具到 ToolRegistry</li>
 *   <li>LLM 根据描述选择工具，ToolManager 执行</li>
 * </ol>
 */
@Tag(name = "工具管理", description = "工具定义查询与管理")
@RestController
@RequestMapping("/api/v1/tools")
@RequiredArgsConstructor
public class ToolController {

    private final ToolDefinitionService toolDefinitionService;

    // ======================== 查询 ========================

    /**
     * 列出所有启用的工具.
     *
     * <p>Python Agent 启动时调用此接口构建 ToolRegistry.
     * 仅返回 is_active=1 的工具.
     *
     * @return 启用的工具定义列表.
     */
    @Operation(summary = "列出所有启用的工具")
    @GetMapping("/list")
    public Result<List<ToolDefinition>> listEnabledTools() {
        List<ToolDefinition> tools = toolDefinitionService.listEnabledTools();
        return Result.success(tools);
    }

    /**
     * 列出所有工具（包含已禁用）.
     *
     * <p>用于管理员管理界面.
     *
     * @return 所有工具定义列表.
     */
    @Operation(summary = "列出所有工具（管理员）")
    @GetMapping("/admin/list")
    public Result<List<ToolDefinition>> listAllTools() {
        List<ToolDefinition> tools = toolDefinitionService.listAllTools();
        return Result.success(tools);
    }

    /**
     * 根据名称获取工具.
     *
     * @param name 工具名称（例如 'sql_query', 'feishu_summary'）.
     * @return 工具定义（如果找到）.
     */
    @Operation(summary = "根据名称获取工具")
    @GetMapping("/{name}")
    public Result<ToolDefinition> getTool(
            @Parameter(description = "工具名称") @PathVariable String name) {
        Optional<ToolDefinition> tool = toolDefinitionService.findByName(name);
        return tool.map(Result::success)
                .orElse(Result.fail(404, "未找到工具: " + name));
    }

    // ======================== 管理 ========================

    /**
     * 运行时启用或禁用工具.
     *
     * <p>禁用的工具不会由 /list 返回，也不可用于 LLM 函数调用.
     * 现有的 ToolRegistry 实例需要刷新才能获取变更.
     *
     * @param name 工具名称.
     * @param body 包含 "enabled": true/false 的请求体.
     * @return 成功指示.
     */
    @Operation(summary = "启用或禁用工具")
    @PutMapping("/{name}/enabled")
    public Result<Void> setEnabled(
            @Parameter(description = "工具名称") @PathVariable String name,
            @RequestBody Map<String, Boolean> body) {
        Boolean enabled = body.getOrDefault("enabled", true);
        boolean ok = toolDefinitionService.setEnabled(name, enabled);
        if (ok) {
            return Result.success(null);
        }
        return Result.fail(404, "未找到工具: " + name);
    }

    /**
     * 更新工具配置.
     *
     * <p>允许运行时配置更改而无需重启（例如模型名称、API 端点、阈值等）.
     *
     * @param name 工具名称.
     * @param body 包含 "config_json": "{...}" 的请求体.
     * @return 成功指示.
     */
    @Operation(summary = "更新工具配置")
    @PutMapping("/{name}/config")
    public Result<Void> updateConfig(
            @Parameter(description = "工具名称") @PathVariable String name,
            @RequestBody Map<String, String> body) {
        String configJson = body.getOrDefault("config_json", "{}");
        boolean ok = toolDefinitionService.updateConfig(name, configJson);
        if (ok) {
            return Result.success(null);
        }
        return Result.fail(404, "未找到工具: " + name);
    }
}
