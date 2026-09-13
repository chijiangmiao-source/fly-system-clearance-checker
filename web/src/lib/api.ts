import type { CheckResult, EncounterResult } from './types';

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

async function postJson<T>(text: string, url: string): Promise<T> {
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
  return data as T;
}

/** 把用户输入的原文作为请求体真实提交给 API。 */
export function checkStage(text: string, url = '/api/check'): Promise<CheckResult> {
  return postJson<CheckResult>(text, url);
}

/** 双吊景交会检测：原文提交到独立的 /api/encounter。 */
export function checkEncounter(text: string, url = '/api/encounter'): Promise<EncounterResult> {
  return postJson<EncounterResult>(text, url);
}
