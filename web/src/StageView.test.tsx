import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { createElement } from 'react';
import { StageView } from './components/StageView';
import type { CheckResult, StagePayload } from './lib/types';

const basePayload = (fly: StagePayload['fly']): StagePayload => ({
  stage: { width: 10000, height: 10000 },
  fly,
  zones: [
    {
      id: 'A',
      vertices: [
        { x: 7000, y: 2500 },
        { x: 9000, y: 2500 },
        { x: 9000, y: 3500 },
        { x: 7000, y: 3500 },
      ],
    },
  ],
});

const hit = (over: Partial<CheckResult>): CheckResult => ({
  collides: true,
  t: 0.625,
  t_display: '0.625000',
  t_fraction: '5/8',
  zone_id: 'A',
  zone_index: 0,
  edge_index: 2,
  segment_index: 1,
  segment_t_display: '0.250000',
  position: { x: 6000, y: 3000 },
  position_display: { x: '6000', y: '3000' },
  active_window: null,
  active_window_display: null,
  ...over,
});

const SAFE: CheckResult = {
  collides: false,
  t: null,
  t_display: null,
  zone_id: null,
  zone_index: null,
  edge_index: null,
  segment_index: null,
  segment_t_display: null,
  position: null,
  position_display: null,
  active_window: null,
  active_window_display: null,
};

describe('StageView 服务端渲染冒烟（无需浏览器）', () => {
  it('第二段命中：折线按命中点绿红分隔并绘制停位姿态', () => {
    const payload = basePayload({
      width: 1000,
      height: 1000,
      start: { x: 0, y: 3000 },
      waypoints: [{ x: 5000, y: 3000 }],
      end: { x: 9000, y: 3000 },
    });
    const html = renderToStaticMarkup(
      createElement(StageView, { payload, result: hit({}) }),
    );
    expect(html).toContain('points="0,7000 5000,7000 6000,7000"');
    expect(html).toContain('points="6000,7000 9000,7000"');
    expect(html).toContain('data-testid="path-safe"');
    expect(html).toContain('data-testid="path-danger"');
    expect(html).toContain('data-testid="waypoint-pose-0"');
    expect(html).toContain('停位 1 (5000, 3000) mm');
    expect(html).toContain('第 2 段');
    expect(html).toContain('0.250000');
  });

  it('折点命中归前段：绿路止于折点，红路自折点起', () => {
    const payload = basePayload({
      width: 1000,
      height: 1000,
      start: { x: 0, y: 0 },
      waypoints: [{ x: 4000, y: 4000 }],
      end: { x: 0, y: 8000 },
    });
    const result = hit({
      t: 0.5,
      t_display: '0.500000',
      segment_index: 0,
      segment_t_display: '1.000000',
      position: { x: 4000, y: 4000 },
      position_display: { x: '4000', y: '4000' },
      zone_id: 'A',
    });
    const html = renderToStaticMarkup(
      createElement(StageView, { payload, result }),
    );
    expect(html).toContain('points="0,10000 4000,6000"');
    expect(html).toContain('points="4000,6000 0,2000"');
    expect(html).toContain('data-testid="path-safe"');
    expect(html).toContain('data-testid="path-danger"');
    expect(html).toContain('第 1 段');
  });

  it('多段安全路线全绿：单条 polyline 覆盖完整折线', () => {
    const payload = basePayload({
      width: 1000,
      height: 1000,
      start: { x: 0, y: 8000 },
      waypoints: [{ x: 5000, y: 3000 }],
      end: { x: 9000, y: 8000 },
    });
    const html = renderToStaticMarkup(
      createElement(StageView, { payload, result: SAFE }),
    );
    expect(html).toContain('points="0,2000 5000,7000 9000,2000"');
    expect(html).toContain('data-testid="path-safe"');
    expect(html).not.toContain('data-testid="path-danger"');
    expect(html).toContain('data-testid="waypoint-pose-0"');
  });

  it('不含 waypoints 的单段请求：直线、无停位姿态、段号 1', () => {
    const payload = basePayload({
      width: 1000,
      height: 1000,
      start: { x: 0, y: 500 },
      end: { x: 9000, y: 500 },
    });
    const result = hit({
      t: 1 / 3,
      t_display: '0.333333',
      segment_index: 0,
      segment_t_display: '0.333333',
      position: { x: 3000, y: 500 },
      position_display: { x: '3000', y: '500' },
      edge_index: 3,
    });
    const html = renderToStaticMarkup(
      createElement(StageView, { payload, result }),
    );
    expect(html).toContain('points="0,9500 3000,9500"');
    expect(html).toContain('points="3000,9500 9000,9500"');
    expect(html).toContain('data-testid="path-safe"');
    expect(html).toContain('data-testid="path-danger"');
    expect(html).not.toContain('waypoint-pose-');
  });

  it('禁入区填写启用窗口：区旁标注生效区间；未填写则不标注', () => {
    const payload = basePayload({
      width: 1000,
      height: 1000,
      start: { x: 0, y: 3000 },
      waypoints: [{ x: 5000, y: 3000 }],
      end: { x: 9000, y: 3000 },
    });
    payload.zones[0].active_window = { start_tick: 600000, end_tick: 800000 };
    payload.zones.push({
      id: 'B',
      vertices: [
        { x: 1500, y: 2500 },
        { x: 2500, y: 2500 },
        { x: 2500, y: 3500 },
        { x: 1500, y: 3500 },
      ],
    });
    const html = renderToStaticMarkup(
      createElement(StageView, { payload, result: hit({}) }),
    );
    expect(html).toContain('data-testid="zone-window-A"');
    expect(html).toContain('生效 [0.600000, 0.800000]');
    expect(html).not.toContain('data-testid="zone-window-B"');
  });
});
