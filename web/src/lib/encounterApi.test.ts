import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiRequestError, checkEncounter } from './api';

const collisionBody = {
  collides: true,
  t: 8 / 19,
  t_display: '0.421053',
  t_fraction: '8/19',
  fly_a: {
    id: 'A',
    segment_index: 0,
    segment_t_display: '0.842105',
    position: { x: 4210.526316, y: 3000 },
    position_display: { x: '4210.526316', y: '3000' },
  },
  fly_b: {
    id: 'B',
    segment_index: 1,
    segment_t_display: '0.263158',
    position: { x: 5210.526316, y: 4000 },
    position_display: { x: '5210.526316', y: '4000' },
  },
  contact: { x: 5210.526316, y: 4000 },
  contact_display: { x: '5210.526316', y: '4000' },
};

const safeBody = {
  collides: false,
  t: null,
  t_display: null,
  t_fraction: null,
  fly_a: null,
  fly_b: null,
  contact: null,
  contact_display: null,
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('checkEncounter API 客户端', () => {
  it('成功时返回解析结果，原文提交到 /api/encounter', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(collisionBody), { status: 200 }),
    );
    vi.stubGlobal('fetch', fetchMock);
    const r = await checkEncounter('{"fly_a":1}');
    expect(r.collides).toBe(true);
    expect(r.t_fraction).toBe('8/19');
    expect(r.fly_a?.segment_index).toBe(0);
    expect(r.fly_b?.segment_index).toBe(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/encounter');
    expect(init.method).toBe('POST');
    expect(init.body).toBe('{"fly_a":1}');
  });

  it('安全方案：collides false 且双方姿态为 null', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(JSON.stringify(safeBody), { status: 200 })),
    );
    const r = await checkEncounter('{}');
    expect(r.collides).toBe(false);
    expect(r.fly_a).toBeNull();
    expect(r.contact).toBeNull();
  });

  it('第二套吊景越界：抛出携带 fly_b.* 路径的 ApiRequestError', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ error: { path: 'fly_b.start.x', message: 'fly must stay within the stage' } }),
          { status: 400 },
        ),
      ),
    );
    const err = await checkEncounter('{}').catch((e) => e);
    expect(err).toBeInstanceOf(ApiRequestError);
    expect(err.path).toBe('fly_b.start.x');
    expect(err.status).toBe(400);
  });

  it('网络失败时抛出连接错误', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('failed to fetch')));
    const err = await checkEncounter('{}').catch((e) => e);
    expect(err).toBeInstanceOf(ApiRequestError);
    expect(err.status).toBe(0);
  });
});
