package com.company.aiplatform.chat.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.company.aiplatform.chat.entity.MessageTrace;
import org.apache.ibatis.annotations.Mapper;

/**
 * t_message_trace 表 Mapper。
 */
@Mapper
public interface MessageTraceMapper extends BaseMapper<MessageTrace> {
}