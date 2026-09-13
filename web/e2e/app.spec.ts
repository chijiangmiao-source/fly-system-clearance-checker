import { expect, test } from '@playwright/test';

const COLLISION = JSON.stringify({
  stage: { width: 10000, height: 10000 },
  fly: { width: 1000, height: 1000, start: { x: 0, y: 500 }, end: { x: 9000, y: 500 } },
  zones: [
    {
      id: 'A',
      vertices: [
        { x: 4000, y: 0 },
        { x: 6000, y: 0 },
        { x: 6000, y: 2000 },
        { x: 4000, y: 2000 },
      ],
    },
  ],
});

const SAFE = JSON.stringify({
  stage: { width: 10000, height: 10000 },
  fly: { width: 1000, height: 1000, start: { x: 0, y: 3000 }, end: { x: 9000, y: 3000 } },
  zones: [
    {
      id: 'A',
      vertices: [
        { x: 4000, y: 0 },
        { x: 6000, y: 0 },
        { x: 6000, y: 2000 },
        { x: 4000, y: 2000 },
      ],
    },
  ],
});

const MISSING_FIELD = JSON.stringify({
  stage: { width: 10000, height: 10000 },
  fly: { width: 1000, height: 1000, start: { y: 500 }, end: { x: 9000, y: 500 } },
  zones: [],
});

const SELF_INTERSECT = JSON.stringify({
  stage: { width: 10000, height: 10000 },
  fly: { width: 1000, height: 1000, start: { x: 0, y: 500 }, end: { x: 9000, y: 500 } },
  zones: [
    {
      id: 'BAD',
      vertices: [
        { x: 0, y: 0 },
        { x: 100, y: 100 },
        { x: 100, y: 0 },
        { x: 0, y: 100 },
      ],
    },
  ],
});

// 两段折线：第二段首次碰撞 —— 段内 t=1/4，全程 t=5/8，命中 (6000,3000)
const SEG2_COLLISION = JSON.stringify({
  stage: { width: 10000, height: 10000 },
  fly: {
    width: 1000,
    height: 1000,
    start: { x: 0, y: 3000 },
    waypoints: [{ x: 5000, y: 3000 }],
    end: { x: 9000, y: 3000 },
  },
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

// 折点两侧同时命中：矩形左上角在折点 (4000,4000) 触区顶点 (4000,5000)，归第 1 段
const VERTEX_COLLISION = JSON.stringify({
  stage: { width: 10000, height: 10000 },
  fly: {
    width: 1000,
    height: 1000,
    start: { x: 0, y: 0 },
    waypoints: [{ x: 4000, y: 4000 }],
    end: { x: 0, y: 8000 },
  },
  zones: [
    {
      id: 'B',
      vertices: [
        { x: 3000, y: 5000 },
        { x: 4000, y: 5000 },
        { x: 4000, y: 6000 },
        { x: 3000, y: 6000 },
      ],
    },
  ],
});

// 两段 V 形安全路线：全程不与区相交
const MULTI_SEG_SAFE = JSON.stringify({
  stage: { width: 10000, height: 10000 },
  fly: {
    width: 1000,
    height: 1000,
    start: { x: 0, y: 8000 },
    waypoints: [{ x: 5000, y: 3000 }],
    end: { x: 9000, y: 8000 },
  },
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

const WAYPOINT_OOB = JSON.stringify({
  stage: { width: 10000, height: 10000 },
  fly: {
    width: 1000,
    height: 1000,
    start: { x: 0, y: 0 },
    waypoints: [{ x: 9001, y: 0 }],
    end: { x: 9000, y: 9000 },
  },
  zones: [],
});

const WAYPOINT_DUP = JSON.stringify({
  stage: { width: 10000, height: 10000 },
  fly: {
    width: 1000,
    height: 1000,
    start: { x: 0, y: 0 },
    waypoints: [
      { x: 5000, y: 5000 },
      { x: 5000, y: 5000 },
    ],
    end: { x: 9000, y: 9000 },
  },
  zones: [],
});

// 启用窗口折线：第一段穿过未启用区 A（窗口仅覆盖后半程），第二段命中启用区 B
const WINDOW_ROUTE = JSON.stringify({
  stage: { width: 10000, height: 10000 },
  fly: {
    width: 1000,
    height: 1000,
    start: { x: 0, y: 3000 },
    waypoints: [{ x: 5000, y: 3000 }],
    end: { x: 9000, y: 3000 },
  },
  zones: [
    {
      id: 'A',
      vertices: [
        { x: 1500, y: 2500 },
        { x: 2500, y: 2500 },
        { x: 2500, y: 3500 },
        { x: 1500, y: 3500 },
      ],
      active_window: { start_tick: 500000, end_tick: 1000000 },
    },
    {
      id: 'B',
      vertices: [
        { x: 7000, y: 2500 },
        { x: 9000, y: 2500 },
        { x: 9000, y: 3500 },
        { x: 7000, y: 3500 },
      ],
      active_window: { start_tick: 600000, end_tick: 800000 },
    },
  ],
});

// 相同几何路线：A、B 窗口均错开接触区间 → 全程安全
const WINDOW_SAFE = JSON.stringify({
  stage: { width: 10000, height: 10000 },
  fly: {
    width: 1000,
    height: 1000,
    start: { x: 0, y: 3000 },
    waypoints: [{ x: 5000, y: 3000 }],
    end: { x: 9000, y: 3000 },
  },
  zones: [
    {
      id: 'A',
      vertices: [
        { x: 1500, y: 2500 },
        { x: 2500, y: 2500 },
        { x: 2500, y: 3500 },
        { x: 1500, y: 3500 },
      ],
      active_window: { start_tick: 500000, end_tick: 1000000 },
    },
    {
      id: 'B',
      vertices: [
        { x: 7000, y: 2500 },
        { x: 9000, y: 2500 },
        { x: 9000, y: 3500 },
        { x: 7000, y: 3500 },
      ],
      active_window: { start_tick: 0, end_tick: 600000 },
    },
  ],
});

// 窗口起点大于终点（顺序错误）
const WINDOW_BAD_ORDER = JSON.stringify({
  stage: { width: 10000, height: 10000 },
  fly: { width: 1000, height: 1000, start: { x: 0, y: 500 }, end: { x: 9000, y: 500 } },
  zones: [
    {
      id: 'A',
      vertices: [
        { x: 4000, y: 0 },
        { x: 6000, y: 0 },
        { x: 6000, y: 2000 },
        { x: 4000, y: 2000 },
      ],
      active_window: { start_tick: 700000, end_tick: 300000 },
    },
  ],
});

// 窗口刻度越界（end_tick > 1000000）
const WINDOW_BAD_RANGE = JSON.stringify({
  stage: { width: 10000, height: 10000 },
  fly: { width: 1000, height: 1000, start: { x: 0, y: 500 }, end: { x: 9000, y: 500 } },
  zones: [
    {
      id: 'A',
      vertices: [
        { x: 4000, y: 0 },
        { x: 6000, y: 0 },
        { x: 6000, y: 2000 },
        { x: 4000, y: 2000 },
      ],
      active_window: { start_tick: 0, end_tick: 1000001 },
    },
  ],
});

test('启用窗口：先穿过未启用区、随后命中启用区，区旁标注生效区间', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('payload-input').fill(WINDOW_ROUTE);
  await page.getByTestId('submit-btn').click();

  // 命中启用区 B（全程 t=5/8，第二段段内 t=1/4），结果补充命中窗口
  await expect(page.getByTestId('t-value')).toHaveText('0.625000');
  await expect(page.getByTestId('zone-value')).toHaveText('B');
  await expect(page.getByTestId('segment-value')).toHaveText('#1');
  await expect(page.getByTestId('window-value')).toHaveText('[0.600000, 0.800000]');
  await expect(page.getByTestId('pos-value')).toContainText('(6000, 3000) mm');

  // 禁入区旁标注生效区间
  await expect(page.getByTestId('zone-window-A')).toHaveText('生效 [0.500000, 1.000000]');
  await expect(page.getByTestId('zone-window-B')).toHaveText('生效 [0.600000, 0.800000]');

  // 命中点把折线切成绿/红两段
  await expect(page.getByTestId('path-safe')).toHaveCount(1);
  await expect(page.getByTestId('path-danger')).toHaveCount(1);
});

test('启用窗口：路线仅穿过未启用区域时仍显示全绿', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('payload-input').fill(WINDOW_SAFE);
  await page.getByTestId('submit-btn').click();

  await expect(page.getByTestId('safe-message')).toBeVisible();
  await expect(page.getByTestId('path-safe')).toHaveCount(1);
  await expect(page.getByTestId('path-danger')).toHaveCount(0);
  await expect(page.getByTestId('collision-pose')).toHaveCount(0);
  // 未启用区域仍绘制并标注生效区间
  await expect(page.getByTestId('zone-window-A')).toHaveText('生效 [0.500000, 1.000000]');
  await expect(page.getByTestId('zone-window-B')).toHaveText('生效 [0.000000, 0.600000]');
});

test('启用窗口顺序错误：定位到 zones 下标内字段，保留原文并清除旧图', async ({ page }) => {
  await page.goto('/');
  // 先成功绘制一次
  await page.getByTestId('payload-input').fill(COLLISION);
  await page.getByTestId('submit-btn').click();
  await expect(page.getByTestId('collision-pose')).toBeVisible();

  await page.getByTestId('payload-input').fill(WINDOW_BAD_ORDER);
  await page.getByTestId('submit-btn').click();
  await expect(page.getByTestId('error-banner')).toBeVisible();
  await expect(page.getByTestId('error-path')).toHaveText('zones.0.active_window.end_tick');
  await expect(page.getByTestId('payload-input')).toHaveValue(WINDOW_BAD_ORDER);
  await expect(page.getByTestId('stage-view')).toHaveCount(0);
  await expect(page.getByTestId('result-panel')).toHaveCount(0);
});

test('启用窗口刻度越界：定位到 zones 下标内字段', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('payload-input').fill(WINDOW_BAD_RANGE);
  await page.getByTestId('submit-btn').click();
  await expect(page.getByTestId('error-path')).toHaveText('zones.0.active_window.end_tick');
  await expect(page.getByTestId('payload-input')).toHaveValue(WINDOW_BAD_RANGE);
  await expect(page.getByTestId('stage-view')).toHaveCount(0);
});

// U 形（非凸）禁入区：吊景穿过中间空腔，窗口只在空腔时刻启用 → 不得误报
const U_SHAPE_CAVITY = JSON.stringify({
  stage: { width: 10000, height: 10000 },
  fly: { width: 1000, height: 1000, start: { x: 0, y: 3000 }, end: { x: 9000, y: 3000 } },
  zones: [
    {
      id: 'U',
      vertices: [
        { x: 3000, y: 1000 },
        { x: 7000, y: 1000 },
        { x: 7000, y: 5000 },
        { x: 6000, y: 5000 },
        { x: 6000, y: 2000 },
        { x: 4000, y: 2000 },
        { x: 4000, y: 5000 },
        { x: 3000, y: 5000 },
      ],
      active_window: { start_tick: 450000, end_tick: 550000 },
    },
  ],
});

test('U 形空腔：窗口只在空腔时刻启用时仍显示全绿，不误报碰撞', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('payload-input').fill(U_SHAPE_CAVITY);
  await page.getByTestId('submit-btn').click();

  await expect(page.getByTestId('safe-message')).toBeVisible();
  await expect(page.getByTestId('path-safe')).toHaveCount(1);
  await expect(page.getByTestId('path-danger')).toHaveCount(0);
  await expect(page.getByTestId('collision-pose')).toHaveCount(0);
  await expect(page.getByTestId('zone-window-U')).toHaveText('生效 [0.450000, 0.550000]');
});

test('碰撞场景：展示 t、责任区、责任边与碰撞姿态', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('payload-input').fill(COLLISION);
  await page.getByTestId('submit-btn').click();

  await expect(page.getByTestId('t-value')).toHaveText('0.333333');
  await expect(page.getByTestId('zone-value')).toHaveText('A');
  await expect(page.getByTestId('edge-value')).toHaveText('#3');
  await expect(page.getByTestId('pos-value')).toContainText('(3000, 500) mm');

  // 俯视图：碰撞姿态、责任边、红绿分段路径（line 元素包围盒退化，用计数断言）
  await expect(page.getByTestId('collision-pose')).toBeVisible();
  await expect(page.getByTestId('responsible-edge')).toBeVisible();
  await expect(page.getByTestId('path-safe')).toHaveCount(1);
  await expect(page.getByTestId('path-danger')).toHaveCount(1);
  await expect(page.getByTestId('start-pose')).toBeVisible();
  await expect(page.getByTestId('end-pose')).toBeVisible();
});

test('无碰撞场景：路径全绿并提示安全', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('payload-input').fill(SAFE);
  await page.getByTestId('submit-btn').click();

  await expect(page.getByTestId('safe-message')).toBeVisible();
  await expect(page.getByTestId('path-safe')).toHaveCount(1);
  await expect(page.getByTestId('path-danger')).toHaveCount(0);
  await expect(page.getByTestId('collision-pose')).toHaveCount(0);
  const stroke = await page.getByTestId('path-safe').getAttribute('stroke');
  expect(stroke).toBe('#27ae60');
});

test('缺字段：返回首个字段路径、保留原文、清除旧图', async ({ page }) => {
  await page.goto('/');
  // 先成功绘制一次
  await page.getByTestId('payload-input').fill(COLLISION);
  await page.getByTestId('submit-btn').click();
  await expect(page.getByTestId('collision-pose')).toBeVisible();

  // 再提交缺字段的载荷
  await page.getByTestId('payload-input').fill(MISSING_FIELD);
  await page.getByTestId('submit-btn').click();

  await expect(page.getByTestId('error-banner')).toBeVisible();
  await expect(page.getByTestId('error-path')).toHaveText('fly.start.x');
  // 保留本次原文
  await expect(page.getByTestId('payload-input')).toHaveValue(MISSING_FIELD);
  // 清除旧图
  await expect(page.getByTestId('stage-view')).toHaveCount(0);
  await expect(page.getByTestId('result-panel')).toHaveCount(0);
});

test('自交多边形：返回 zones.0.vertices 并清除旧图', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('payload-input').fill(SELF_INTERSECT);
  await page.getByTestId('submit-btn').click();

  await expect(page.getByTestId('error-path')).toHaveText('zones.0.vertices');
  await expect(page.getByTestId('payload-input')).toHaveValue(SELF_INTERSECT);
  await expect(page.getByTestId('stage-view')).toHaveCount(0);
});

test('视图可缩放：重置后 viewBox 复原', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('payload-input').fill(COLLISION);
  await page.getByTestId('submit-btn').click();
  const svg = page.getByTestId('stage-view');
  await expect(svg).toBeVisible();
  const before = await svg.getAttribute('viewBox');
  await page.getByTestId('zoom-in').click();
  const zoomed = await svg.getAttribute('viewBox');
  expect(zoomed).not.toBe(before);
  await page.getByTestId('zoom-reset').click();
  expect(await svg.getAttribute('viewBox')).toBe(before);
});

test('多段折线：第二段首次碰撞稳定定位到段号与段内 t，红绿分隔折线', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('payload-input').fill(SEG2_COLLISION);
  await page.getByTestId('submit-btn').click();

  await expect(page.getByTestId('t-value')).toHaveText('0.625000');
  await expect(page.getByTestId('segment-value')).toHaveText('#1');
  await expect(page.getByTestId('segment-t-value')).toHaveText('0.250000');
  await expect(page.getByTestId('zone-value')).toHaveText('A');
  await expect(page.getByTestId('pos-value')).toContainText('(6000, 3000) mm');

  // 完整折线经过停位；命中点把折线切成绿/红两段
  await expect(page.getByTestId('path-safe')).toHaveCount(1);
  await expect(page.getByTestId('path-danger')).toHaveCount(1);
  const safePts = await page.getByTestId('path-safe').getAttribute('points');
  const dangerPts = await page.getByTestId('path-danger').getAttribute('points');
  expect(safePts).toContain('0,7000'); // 起点 (0,3000)
  expect(safePts).toContain('5000,7000'); // 停位 (5000,3000)
  expect(safePts).toContain('6000,7000'); // 命中点 (6000,3000)
  expect(dangerPts).toContain('6000,7000'); // 命中点起
  expect(dangerPts).toContain('9000,7000'); // 终点 (9000,3000)

  // 停位姿态绘制
  await expect(page.getByTestId('waypoint-pose-0')).toBeVisible();
  // 命中姿态标注段号
  await expect(page.getByTestId('collision-pose')).toContainText('第 2 段');
});

test('多段折线：折点两侧同时命中归前段（segment #0，段内 t=1）', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('payload-input').fill(VERTEX_COLLISION);
  await page.getByTestId('submit-btn').click();

  await expect(page.getByTestId('t-value')).toHaveText('0.500000');
  await expect(page.getByTestId('segment-value')).toHaveText('#0');
  await expect(page.getByTestId('segment-t-value')).toHaveText('1.000000');
  await expect(page.getByTestId('pos-value')).toContainText('(4000, 4000) mm');

  const safePts = await page.getByTestId('path-safe').getAttribute('points');
  const dangerPts = await page.getByTestId('path-danger').getAttribute('points');
  // 命中点即折点：绿路止于折点，红路自折点起（y 翻转：4000 -> 6000）
  expect(safePts).toBe('0,10000 4000,6000');
  expect(dangerPts).toBe('4000,6000 0,2000');
});

test('多段折线：安全路线全绿且绘制停位', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('payload-input').fill(MULTI_SEG_SAFE);
  await page.getByTestId('submit-btn').click();

  await expect(page.getByTestId('safe-message')).toBeVisible();
  await expect(page.getByTestId('path-danger')).toHaveCount(0);
  await expect(page.getByTestId('collision-pose')).toHaveCount(0);
  await expect(page.getByTestId('waypoint-pose-0')).toBeVisible();
  const safePts = await page.getByTestId('path-safe').getAttribute('points');
  expect(safePts).toBe('0,2000 5000,7000 9000,2000');
});

test('停位越界：错误定位到 fly.waypoints 下标，保留原文并清空旧图', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('payload-input').fill(COLLISION);
  await page.getByTestId('submit-btn').click();
  await expect(page.getByTestId('collision-pose')).toBeVisible();

  await page.getByTestId('payload-input').fill(WAYPOINT_OOB);
  await page.getByTestId('submit-btn').click();
  await expect(page.getByTestId('error-path')).toHaveText('fly.waypoints.0.x');
  await expect(page.getByTestId('payload-input')).toHaveValue(WAYPOINT_OOB);
  await expect(page.getByTestId('stage-view')).toHaveCount(0);
  await expect(page.getByTestId('result-panel')).toHaveCount(0);
});

test('相邻停位重复：错误定位到具体下标与坐标，保留原文并清空旧图', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('payload-input').fill(WAYPOINT_DUP);
  await page.getByTestId('submit-btn').click();
  await expect(page.getByTestId('error-path')).toHaveText('fly.waypoints.1');
  await expect(page.getByTestId('error-message')).toContainText('(5000, 5000)');
  await expect(page.getByTestId('payload-input')).toHaveValue(WAYPOINT_DUP);
  await expect(page.getByTestId('stage-view')).toHaveCount(0);
});

test('不含 waypoints 的既有请求：画面与字段不回归', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('payload-input').fill(COLLISION);
  await page.getByTestId('submit-btn').click();

  await expect(page.getByTestId('t-value')).toHaveText('0.333333');
  await expect(page.getByTestId('segment-value')).toHaveText('#0');
  await expect(page.getByTestId('segment-t-value')).toHaveText('0.333333');
  await expect(page.getByTestId('waypoint-pose-0')).toHaveCount(0);
  const safePts = await page.getByTestId('path-safe').getAttribute('points');
  const dangerPts = await page.getByTestId('path-danger').getAttribute('points');
  expect(safePts).toBe('0,9500 3000,9500');
  expect(dangerPts).toBe('3000,9500 9000,9500');
});

test('终点与首个停位同时越界：按路线顺序先报首个停位横坐标', async ({ page }) => {
  const BOTH_OOB = JSON.stringify({
    stage: { width: 10000, height: 10000 },
    fly: {
      width: 1000,
      height: 1000,
      start: { x: 0, y: 0 },
      waypoints: [{ x: 9001, y: 0 }],
      end: { x: 9001, y: 9001 },
    },
    zones: [],
  });
  await page.goto('/');
  await page.getByTestId('payload-input').fill(BOTH_OOB);
  await page.getByTestId('submit-btn').click();
  await expect(page.getByTestId('error-path')).toHaveText('fly.waypoints.0.x');
});

test('起点越界且后续停位格式错误：先报起点横坐标，再轮不到后面的错误', async ({ page }) => {
  const START_OOB_LATER_BAD = JSON.stringify({
    stage: { width: 10000, height: 10000 },
    fly: {
      width: 1000,
      height: 1000,
      start: { x: -1, y: 0 },
      waypoints: [{ x: 'oops', y: 0 }],
      end: { x: 9000, y: 9000 },
    },
    zones: [],
  });
  await page.goto('/');
  await page.getByTestId('payload-input').fill(START_OOB_LATER_BAD);
  await page.getByTestId('submit-btn').click();
  await expect(page.getByTestId('error-path')).toHaveText('fly.start.x');
});

test('停位横坐标写成非标准数值常量 NaN：按 JSON 语法错误拒绝（字段路径为根）', async ({ page }) => {
  // 不用 JSON.stringify：NaN 不是合法 JSON，需要保留原文提交
  const NAN_BODY =
    '{"stage":{"width":10000,"height":10000},' +
    '"fly":{"width":1000,"height":1000,"start":{"x":0,"y":0},' +
    '"waypoints":[{"x":NaN,"y":0}],"end":{"x":1000,"y":0}},' +
    '"zones":[]}';
  await page.goto('/');
  await page.getByTestId('payload-input').fill(NAN_BODY);
  await page.getByTestId('submit-btn').click();
  await expect(page.getByTestId('error-banner')).toBeVisible();
  await expect(page.getByTestId('error-path')).toHaveText('(root)');
  await expect(page.getByTestId('error-message')).toContainText('JSON');
});

test('上传含非法 UTF-8 字节的文件：拒绝并提示，不替换字符、不继续检测', async ({ page }) => {
  // 禁入区 id 中夹带非法字节 0xFF 0xFE
  const invalid = Buffer.concat([
    Buffer.from(
      '{"stage":{"width":10000,"height":10000},' +
        '"fly":{"width":1000,"height":1000,"start":{"x":0,"y":500},"end":{"x":1000,"y":500}},' +
        '"zones":[{"id":"A',
      'utf-8',
    ),
    Buffer.from([0xff, 0xfe]),
    Buffer.from(
      '","vertices":[{"x":0,"y":0},{"x":100,"y":0},{"x":0,"y":100}]}]}',
      'utf-8',
    ),
  ]);
  await page.goto('/');
  const before = await page.getByTestId('payload-input').inputValue();
  await page.getByTestId('file-input').setInputFiles({
    name: 'bad-utf8.json',
    mimeType: 'application/json',
    buffer: invalid,
  });

  await expect(page.getByTestId('file-error')).toBeVisible();
  await expect(page.getByTestId('file-error-message')).toContainText('UTF-8');
  // 原文未被 U+FFFD 污染（文本框保持上传前内容）
  await expect(page.getByTestId('payload-input')).toHaveValue(before);
  // 未触发检测：无旧图清除以外的面板出现
  await expect(page.getByTestId('error-banner')).toHaveCount(0);
  await expect(page.getByTestId('result-panel')).toHaveCount(0);
});

test('上传合法 UTF-8 文件：正常载入文本且无文件错误提示', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('file-input').setInputFiles({
    name: 'route.json',
    mimeType: 'application/json',
    buffer: Buffer.from(COLLISION, 'utf-8'),
  });
  await expect(page.getByTestId('payload-input')).toHaveValue(COLLISION);
  await expect(page.getByTestId('file-error')).toHaveCount(0);
});
