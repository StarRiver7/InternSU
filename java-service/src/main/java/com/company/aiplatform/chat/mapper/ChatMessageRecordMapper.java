package com.company.aiplatform.chat.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.company.aiplatform.chat.entity.ChatMessageRecord;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface ChatMessageRecordMapper extends BaseMapper<ChatMessageRecord> {
}