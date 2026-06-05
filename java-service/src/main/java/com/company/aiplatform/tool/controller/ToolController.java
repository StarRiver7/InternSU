package com.company.aiplatform.tool.controller;

import com.company.aiplatform.common.result.Result;
import com.company.aiplatform.tool.entity.ToolDefinition;
import com.company.aiplatform.tool.service.ToolDefinitionService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 工具管理控制器
 *
 * <p>提供 Agent 可用工具的查询接口，供 Python Agent 查询可用的工具定义。
 * 工具定义包括：
 * <ul>
 *   <li>工具名称</li>
 *   <li>工具描述</li>
 *   <li>输入参数 Schema</li>
 *   <li>执行方式（本地执行 / 远程调用）</li>
 * </ul>
 *
 * <p>安全说明：
 * <ul>
 *   <li>只有启用状态（status=1）的工具才会被返回</li>
 *   <li>工具执行权限由 Python Agent 层做二次校验</li>
 * </ul>
 */
@Tag(name = "工具管理", description = "工具定义查询")
@RestController
@RequestMapping("/api/v1/tools")
@RequiredArgsConstructor
public class ToolController {

    private final ToolDefinitionService toolDefinitionService;

    /**
     * 查询所有已启用的工具列表
     *
     * <p>返回给 Python Agent，用于动态生成 Function Calling 可用工具列表。
     *
     * @return 已启用的工具定义列表
     */
    @Operation(summary = "查询所有已启用的工具列表")
    @GetMapping("/list")
    public Result<List<ToolDefinition>> listEnabledTools() {
        List<ToolDefinition> tools = toolDefinitionService.listEnabledTools();
        return Result.success(tools);
    }
}
