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
