package com.company.aiplatform.tool.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.company.aiplatform.tool.entity.ToolDefinition;
import com.company.aiplatform.tool.mapper.ToolDefinitionMapper;
import com.company.aiplatform.tool.service.ToolDefinitionService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
public class ToolDefinitionServiceImpl
        extends ServiceImpl<ToolDefinitionMapper, ToolDefinition>
        implements ToolDefinitionService {

    @Override
    public List<ToolDefinition> listEnabledTools() {
        return this.list(new LambdaQueryWrapper<ToolDefinition>()
                .eq(ToolDefinition::getIsActive, 1)
                .orderByAsc(ToolDefinition::getType)
                .orderByAsc(ToolDefinition::getName));
    }
}
