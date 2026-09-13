import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiRequestError, checkStage } from './api';

const okBody = {
  collides: true,
  t: 1 / 3,
  t_display: '0.333333',
  t_fraction: '1/3',
  zone_id: 'A',
  zone_index: 0,
  edge_index: 3,
  position: { x: 3000, y: 500 },
  position_display: { x: '3000', y: '500' },
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('checkStage API 客户端', () => {
  it('成功时返回解析结果，且原文作为请求体提交', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(okBody), { status: 200 }),
    );
    vi.stubGlobal('fetch', fetchMock);
    const r = await checkStage('{"a":1}');
    expect(r.collides).toBe(true);
    expect(r.t_display).toBe('0.333333');
    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/check');
    expect(init.method).toBe('POST');
    expect(init.body).toBe('{"a":1}');
    expect(init.headers['Content-Type']).toContain('utf-8');
  });

  it('400 时抛出携带字段路径的 ApiRequestError', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ error: { path: 'fly.start.x', message: 'must be an integer' } }), {
          status: 400,
        }),
      ),
    );
    const err = await checkStage('{}').catch((e) => e);
    expect(err).toBeInstanceOf(ApiRequestError);
    expect(err.path).toBe('fly.start.x');
    expect(err.message).toBe('must be an integer');
    expect(err.status).toBe(400);
  });

  it('网络失败时抛出连接错误', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('failed to fetch')));
    const err = await checkStage('{}').catch((e) => e);
    expect(err).toBeInstanceOf(ApiRequestError);
    expect(err.status).toBe(0);
  });
});
