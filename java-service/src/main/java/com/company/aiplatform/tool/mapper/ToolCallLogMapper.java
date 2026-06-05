package com.company.aiplatform.tool.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.company.aiplatform.tool.entity.ToolCallLog;
import org.apache.ibatis.annotations.Mapper;

/**
 * Tool call log mapper — basic CRUD via MyBatis-Plus BaseMapper.
 */
@Mapper
public interface ToolCallLogMapper extends BaseMapper<ToolCallLog> {
}
