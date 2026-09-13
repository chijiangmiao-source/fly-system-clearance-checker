import type { CheckResult } from './types';

export class ApiRequestError extends Error {
  constructor(
    public path: string,
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = 'ApiRequestError';
  }
}

/** 把用户输入的原文作为请求体真实提交给 API。 */
export async function checkStage(text: string, url = '/api/check'): Promise<CheckResult> {
  let resp: Response;
  try {
    resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
      body: text,
    });
  } catch {
    throw new ApiRequestError('', '无法连接 API 服务', 0);
  }
  const data = await resp.json().catch(() => null);
  if (!resp.ok) {
    const err = data?.error;
    throw new ApiRequestError(err?.path ?? '', err?.message ?? `HTTP ${resp.status}`, resp.status);
  }
  return data as CheckResult;
}
