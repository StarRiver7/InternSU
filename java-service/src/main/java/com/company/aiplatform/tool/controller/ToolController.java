package com.company.aiplatform.tool.controller;

import com.company.aiplatform.common.result.Result;
import com.company.aiplatform.tool.entity.ToolDefinition;
import com.company.aiplatform.tool.service.ToolDefinitionService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@Tag(name = "工具管理", description = "工具定义查询")
@RestController
@RequestMapping("/api/v1/tools")
@RequiredArgsConstructor
public class ToolController {

    private final ToolDefinitionService toolDefinitionService;

    @Operation(summary = "查询所有已启用的工具列表")
    @GetMapping("/list")
    public Result<List<ToolDefinition>> listEnabledTools() {
        List<ToolDefinition> tools = toolDefinitionService.listEnabledTools();
        return Result.success(tools);
    }
}
