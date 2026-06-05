package com.company.aiplatform.tool.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.company.aiplatform.tool.entity.ToolCallLog;
import com.company.aiplatform.tool.mapper.ToolCallLogMapper;
import com.company.aiplatform.tool.service.ToolCallLogService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

/**
 * Tool call log service implementation.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ToolCallLogServiceImpl
        extends ServiceImpl<ToolCallLogMapper, ToolCallLog>
        implements ToolCallLogService {
}
