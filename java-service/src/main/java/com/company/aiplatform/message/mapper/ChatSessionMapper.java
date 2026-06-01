package com.company.aiplatform.message.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.company.aiplatform.message.entity.ChatSession;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface ChatSessionMapper extends BaseMapper<ChatSession> {
}
