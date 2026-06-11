/** 
 * 聊天状态管理 - 管理跨页面的待发送问题
 * 
 * 工作流程：
 * 1. 用户在 /chat 页面输入问题并点击发送
 * 2. 前端生成 sessionId，将问题保存到 pendingQuestion
 * 3. 跳转到 /history?sessionId=xxx
 * 4. 历史页面 onMounted 时读取并自动发送 pendingQuestion
 * 5. 发送完成后清空 pendingQuestion
 */
import { defineStore } from "pinia";
import { ref } from "vue";

export const useChatStore = defineStore("chat", () => {
  /** 当前会话 ID，由新聊天页面创建后传入 */
  const sessionId = ref<string>("");

  /** 待发送的问题文本，跨页面传递用 */
  const pendingQuestion = ref<string>("");

  /**
   * 保存待发送问题（在新聊天页面点击发送时调用）
   * @param sid 新创建的会话 ID
   * @param question 用户输入的问题文本
   */
  function setPending(sid: string, question: string) {
    sessionId.value = sid;
    pendingQuestion.value = question;
  }

  /**
   * 消费待发送问题（在历史页面 onMounted 中调用）
   * 返回 { sessionId, question } 并清空 store
   */
  function consumePending(): { question: string } {
    const question = pendingQuestion.value;
    // 清空 pendingQuestion，但不清理 sessionId（历史页面可能需要保留）
    pendingQuestion.value = "";
    return { question };
  }

  /**
   * 完全重置 store 状态
   */
  function $reset() {
    sessionId.value = "";
    pendingQuestion.value = "";
  }

  return { $reset, consumePending, pendingQuestion, sessionId, setPending };
});
