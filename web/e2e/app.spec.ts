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
