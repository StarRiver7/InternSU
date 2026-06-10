/**
 * JWT Token 工具模块
 *
 * 提供 JWT 解码、过期检测等企业级 Token 管理能力。
 * 仅解析 payload，不验证签名（签名验证由后端完成）。
 */

/** 解码后的 JWT payload 结构 */
interface JwtPayload {
  /** 过期时间（Unix timestamp in seconds） */
  exp?: number;
  /** 签发时间 */
  iat?: number;
  /** 用户标识 */
  sub?: string;
  [key: string]: unknown;
}

/**
 * 解码 JWT Token 的 payload 部分（不验证签名）
 *
 * JWT 结构: header.payload.signature（Base64Url 编码，用 . 分隔）
 * 取第二部分 (payload) 进行 Base64Url 解码并解析为 JSON。
 *
 * @param token - JWT Token 字符串
 * @returns 解码后的 payload 对象，解码失败返回 null
 */
export function decodeJwt(token: string | null | undefined): JwtPayload | null {
  if (!token || typeof token !== 'string') {
    return null;
  }
  try {
    const parts = token.split('.');
    if (parts.length !== 3) {
      return null;
    }
    // Base64Url → Base64 转换，然后 atob 解码
    const payload = parts[1];
    if (!payload) {
      return null;
    }
    const base64 = payload.replace(/-/g, '+').replace(/_/g, '/');
    const jsonStr = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join(''),
    );
    return JSON.parse(jsonStr) as JwtPayload;
  } catch {
    return null;
  }
}

/**
 * 判断 Token 是否即将过期
 *
 * 根据 JWT payload 中的 exp 字段，计算距离过期还有多少秒。
 * 当剩余时间小于 thresholdSeconds 时，认为 Token 即将过期。
 *
 * @param token - JWT Token 字符串
 * @param thresholdSeconds - 提前阈值（秒），默认 300 秒（5 分钟）
 * @returns 即将过期返回 true，Token 无效或已过期也返回 true
 */
export function isTokenExpiring(
  token: string | null | undefined,
  thresholdSeconds = 300,
): boolean {
  if (!token) {
    return true;
  }
  const payload = decodeJwt(token);
  if (!payload || !payload.exp) {
    // 无法解析或无 exp 字段，保守处理：认为需要刷新
    return true;
  }
  const nowInSeconds = Math.floor(Date.now() / 1000);
  const remainingSeconds = payload.exp - nowInSeconds;
  return remainingSeconds < thresholdSeconds;
}

/**
 * 判断 Token 是否已过期
 *
 * @param token - JWT Token 字符串
 * @returns 已过期返回 true
 */
export function isTokenExpired(token: string | null | undefined): boolean {
  return isTokenExpiring(token, 0);
}
