package com.company.aiplatform.tool.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.company.aiplatform.tool.entity.ToolDefinition;
import com.company.aiplatform.tool.mapper.ToolDefinitionMapper;
import com.company.aiplatform.tool.service.ToolDefinitionService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Optional;

/**
 * Tool definition service implementation — V3 with full CRUD.
 */
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

    @Override
    public List<ToolDefinition> listAllTools() {
        return this.list(new LambdaQueryWrapper<ToolDefinition>()
                .orderByAsc(ToolDefinition::getType)
                .orderByAsc(ToolDefinition::getName));
    }

    @Override
    public Optional<ToolDefinition> findByName(String name) {
        ToolDefinition tool = this.getOne(new LambdaQueryWrapper<ToolDefinition>()
                .eq(ToolDefinition::getName, name));
        return Optional.ofNullable(tool);
    }

    @Override
    @Transactional
    public boolean setEnabled(String name, boolean enabled) {
        return this.update(new LambdaUpdateWrapper<ToolDefinition>()
                .eq(ToolDefinition::getName, name)
                .set(ToolDefinition::getIsActive, enabled ? 1 : 0));
    }

    @Override
    @Transactional
    public boolean updateConfig(String name, String configJson) {
        return this.update(new LambdaUpdateWrapper<ToolDefinition>()
                .eq(ToolDefinition::getName, name)
                .set(ToolDefinition::getConfigJson, configJson));
    }
}
