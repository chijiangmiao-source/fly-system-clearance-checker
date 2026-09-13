import { expect, test } from '@playwright/test';

// 场景 1：起始即接触（共边，t=0 也算冲突）
const START_TOUCH = JSON.stringify({
  stage: { width: 10000, height: 10000 },
  fly_a: {
    id: 'A', width: 1000, height: 1000,
    start: { x: 0, y: 0 }, end: { x: 4000, y: 0 },
  },
  fly_b: {
    id: 'B', width: 1000, height: 1000,
    start: { x: 1000, y: 0 }, end: { x: 5000, y: 0 },
  },
});

// 场景 2：A 两段、B 三段（分段数不同），t=8/19 中途首次角点相撞
const MID_COLLISION = JSON.stringify({
  stage: { width: 10000, height: 10000 },
  fly_a: {
    id: 'A', width: 1000, height: 1000,
    start: { x: 0, y: 3000 },
    waypoints: [{ x: 5000, y: 3000 }],
    end: { x: 9000, y: 3000 },
  },
  fly_b: {
    id: 'B', width: 1000, height: 1000,
    start: { x: 9000, y: 2000 },
    waypoints: [
      { x: 6000, y: 4000 },
      { x: 3000, y: 4000 },
    ],
    end: { x: 0, y: 2000 },
  },
});

// 场景 3：时间错开全程安全（B 先穿过走廊，A 后抵达）
const TIME_SAFE = JSON.stringify({
  stage: { width: 10000, height: 10000 },
  fly_a: {
    id: 'A', width: 1000, height: 1000,
    start: { x: 0, y: 4500 },
    waypoints: [{ x: 4500, y: 4500 }],
    end: { x: 9000, y: 4500 },
  },
  fly_b: {
    id: 'B', width: 1000, height: 1000,
    start: { x: 8000, y: 0 }, end: { x: 8000, y: 9000 },
  },
});

// 场景 4：第二套吊景 start.x 越界
const FLY_B_OOB = JSON.stringify({
  stage: { width: 10000, height: 10000 },
  fly_a: {
    id: 'A', width: 1000, height: 1000,
    start: { x: 0, y: 4500 }, end: { x: 9000, y: 4500 },
  },
  fly_b: {
    id: 'B', width: 1000, height: 1000,
    start: { x: 9001, y: 0 }, end: { x: 0, y: 0 },
  },
});

// 走廊方案：A 两段水平、B 单段竖直穿过 x∈[5000,6000] 走廊。
// 等时基线 t=4/9 相撞（A 第 0 段）；A 加权 [3,1] 错开为安全，加权 [1,3] 改在 A 第 1 段首触。
const corridor = (weights?: number[]) =>
  JSON.stringify({
    stage: { width: 10000, height: 10000 },
    fly_a: {
      id: 'A', width: 1000, height: 1000,
      start: { x: 0, y: 4500 },
      waypoints: [{ x: 4500, y: 4500 }],
      end: { x: 9000, y: 4500 },
      ...(weights ? { duration_weights: weights } : {}),
    },
    fly_b: {
      id: 'B', width: 1000, height: 1000,
      start: { x: 5000, y: 0 }, end: { x: 5000, y: 9000 },
    },
  });

const CORRIDOR_EQUAL = corridor();
const CORRIDOR_SAFE_WEIGHTED = corridor([3, 1]);
const CORRIDOR_HIT_WEIGHTED = corridor([1, 3]);
const CORRIDOR_BAD_LENGTH = corridor([1, 2, 3]);
const CORRIDOR_BAD_ZERO = corridor([1, 0]);

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('tab-encounter').click();
});

test('交会-场景1：起始即接触，t=0、双方段号 0，绘制冲突姿态', async ({ page }) => {
  await page.getByTestId('encounter-input').fill(START_TOUCH);
  await page.getByTestId('encounter-submit-btn').click();

  await expect(page.getByTestId('encounter-t-value')).toHaveText('0.000000');
  await expect(page.getByTestId('encounter-a-segment')).toHaveText('#0');
  await expect(page.getByTestId('encounter-a-segment-t')).toHaveText('0.000000');
  await expect(page.getByTestId('encounter-b-segment')).toHaveText('#0');
  await expect(page.getByTestId('encounter-contact-value')).toContainText('(1000, 500) mm');

  const view = page.getByTestId('encounter-view');
  await expect(view).toBeVisible();
  await expect(page.getByTestId('contact-marker')).toBeVisible();
  await expect(page.getByTestId('a-contact-pose')).toHaveCount(1);
  await expect(page.getByTestId('b-contact-pose')).toHaveCount(1);
});

test('交会-场景2：分段数不同中途相撞，定位全程 t 与双方各自段号，绘制两条路线', async ({ page }) => {
  await page.getByTestId('encounter-input').fill(MID_COLLISION);
  await page.getByTestId('encounter-submit-btn').click();

  await expect(page.getByTestId('encounter-t-value')).toHaveText('0.421053');
  await expect(page.getByTestId('encounter-a-segment')).toHaveText('#0');
  await expect(page.getByTestId('encounter-a-segment-t')).toHaveText('0.842105');
  await expect(page.getByTestId('encounter-b-segment')).toHaveText('#1');
  await expect(page.getByTestId('encounter-b-segment-t')).toHaveText('0.263158');
  await expect(page.getByTestId('encounter-a-pos')).toContainText('(4210.526316, 3000) mm');
  await expect(page.getByTestId('encounter-b-pos')).toContainText('(5210.526316, 4000) mm');
  await expect(page.getByTestId('encounter-contact-value')).toContainText('(5210.526316, 4000) mm');

  // 两条路线都绘制，并按各自接触点分成安全/危险两段
  await expect(page.getByTestId('path-a-safe')).toHaveCount(1);
  await expect(page.getByTestId('path-a-danger')).toHaveCount(1);
  await expect(page.getByTestId('path-b-safe')).toHaveCount(1);
  await expect(page.getByTestId('path-b-danger')).toHaveCount(1);
  await expect(page.getByTestId('a-waypoint-pose-0')).toBeVisible();
  await expect(page.getByTestId('b-waypoint-pose-0')).toBeVisible();
  await expect(page.getByTestId('b-waypoint-pose-1')).toBeVisible();
  await expect(page.getByTestId('contact-marker')).toBeVisible();

  // 俯视图仍可缩放
  const svg = page.getByTestId('encounter-view');
  const before = await svg.getAttribute('viewBox');
  await page.getByTestId('zoom-in').click();
  expect(await svg.getAttribute('viewBox')).not.toBe(before);
  await page.getByTestId('zoom-reset').click();
  expect(await svg.getAttribute('viewBox')).toBe(before);
});

test('交会-场景3：时间错开全程安全，两条路线全绿', async ({ page }) => {
  await page.getByTestId('encounter-input').fill(TIME_SAFE);
  await page.getByTestId('encounter-submit-btn').click();

  await expect(page.getByTestId('encounter-safe-message')).toBeVisible();
  await expect(page.getByTestId('encounter-view')).toBeVisible();
  await expect(page.getByTestId('path-a-safe')).toHaveCount(1);
  await expect(page.getByTestId('path-b-safe')).toHaveCount(1);
  await expect(page.getByTestId('path-a-danger')).toHaveCount(0);
  await expect(page.getByTestId('path-b-danger')).toHaveCount(0);
  await expect(page.getByTestId('contact-marker')).toHaveCount(0);
});

test('交会-场景4：第二套吊景越界，定位 fly_b 字段、保留原文并清除旧结果', async ({ page }) => {
  // 先成功一次
  await page.getByTestId('encounter-input').fill(MID_COLLISION);
  await page.getByTestId('encounter-submit-btn').click();
  await expect(page.getByTestId('contact-marker')).toBeVisible();

  // 再提交 fly_b 越界方案
  await page.getByTestId('encounter-input').fill(FLY_B_OOB);
  await page.getByTestId('encounter-submit-btn').click();

  await expect(page.getByTestId('encounter-error-banner')).toBeVisible();
  await expect(page.getByTestId('encounter-error-path')).toHaveText('fly_b.start.x');
  // 保留本次原文
  await expect(page.getByTestId('encounter-input')).toHaveValue(FLY_B_OOB);
  // 清除旧结果与旧图
  await expect(page.getByTestId('encounter-view')).toHaveCount(0);
  await expect(page.getByTestId('encounter-result-panel')).toHaveCount(0);
});

test('交会：提交期间为独立的检测中状态（按钮禁用并提示）', async ({ page }) => {
  // 延迟响应以稳定捕获提交中状态
  await page.route('**/api/encounter', async (route) => {
    await new Promise((r) => setTimeout(r, 600));
    const body = {
      collides: false, t: null, t_display: null, t_fraction: null,
      fly_a: null, fly_b: null, contact: null, contact_display: null,
    };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
  await page.getByTestId('encounter-input').fill(TIME_SAFE);
  await page.getByTestId('encounter-submit-btn').click();
  await expect(page.getByTestId('encounter-submit-btn')).toBeDisabled();
  await expect(page.getByTestId('encounter-submit-btn')).toHaveText('检测中…');
  await expect(page.getByTestId('encounter-safe-message')).toBeVisible();
});

test('交会与单吊景检测状态相互独立，切换页签互不清除', async ({ page }) => {
  // 交会页签成功一次
  await page.getByTestId('encounter-input').fill(TIME_SAFE);
  await page.getByTestId('encounter-submit-btn').click();
  await expect(page.getByTestId('encounter-safe-message')).toBeVisible();

  // 切回单吊景页签：仍是初始占位，不显示交会结果
  await page.getByTestId('tab-single').click();
  await expect(page.getByTestId('view-placeholder')).toBeVisible();
  await expect(page.getByTestId('result-panel')).toHaveCount(0);

  // 再切回交会页签：成功结果仍在
  await page.getByTestId('tab-encounter').click();
  await expect(page.getByTestId('encounter-safe-message')).toBeVisible();
  await expect(page.getByTestId('encounter-view')).toBeVisible();
});

test('交会-等时基线：走廊方案 t=4/9 在 A 第 0 段相撞，无耗时标注', async ({ page }) => {
  await page.getByTestId('encounter-input').fill(CORRIDOR_EQUAL);
  await page.getByTestId('encounter-submit-btn').click();

  await expect(page.getByTestId('encounter-t-value')).toHaveText('0.444444');
  await expect(page.getByTestId('encounter-a-segment')).toHaveText('#0');
  await expect(page.getByTestId('encounter-a-segment-t')).toHaveText('0.888889');
  await expect(page.getByTestId('encounter-b-segment')).toHaveText('#0');
  await expect(page.getByTestId('encounter-contact-value')).toContainText('(5000, 4750) mm');
  // 未提供 duration_weights：两条路线都不标注各段耗时
  await expect(page.getByTestId('a-seg-duration-0')).toHaveCount(0);
  await expect(page.getByTestId('b-seg-duration-0')).toHaveCount(0);
});

test('交会-加权错开：原本相撞的方案变为全程安全，各段旁标出相对耗时与占比', async ({ page }) => {
  await page.getByTestId('encounter-input').fill(CORRIDOR_SAFE_WEIGHTED);
  await page.getByTestId('encounter-submit-btn').click();

  await expect(page.getByTestId('encounter-safe-message')).toBeVisible();
  await expect(page.getByTestId('path-a-safe')).toHaveCount(1);
  await expect(page.getByTestId('path-b-safe')).toHaveCount(1);
  await expect(page.getByTestId('contact-marker')).toHaveCount(0);

  // A 两段旁标出相对耗时与占总时长比例；B 未加权不标注
  await expect(page.getByTestId('a-seg-duration-0')).toHaveText('段#0 耗时 3（占 3/4）');
  await expect(page.getByTestId('a-seg-duration-1')).toHaveText('段#1 耗时 1（占 1/4）');
  await expect(page.getByTestId('b-seg-duration-0')).toHaveCount(0);
});

test('交会-加权换段：首次接触改在 A 第 1 段，仍展示双方命中段与段内/全程时刻', async ({ page }) => {
  await page.getByTestId('encounter-input').fill(CORRIDOR_HIT_WEIGHTED);
  await page.getByTestId('encounter-submit-btn').click();

  await expect(page.getByTestId('encounter-t-value')).toHaveText('0.388889');
  await expect(page.getByTestId('encounter-a-segment')).toHaveText('#1');
  await expect(page.getByTestId('encounter-a-segment-t')).toHaveText('0.185185');
  await expect(page.getByTestId('encounter-b-segment')).toHaveText('#0');
  await expect(page.getByTestId('encounter-b-segment-t')).toHaveText('0.388889');
  await expect(page.getByTestId('encounter-a-pos')).toContainText('(5333.333333, 4500) mm');
  await expect(page.getByTestId('encounter-b-pos')).toContainText('(5000, 3500) mm');
  await expect(page.getByTestId('encounter-contact-value')).toContainText('(5666.666667, 4500) mm');

  await expect(page.getByTestId('contact-marker')).toBeVisible();
  await expect(page.getByTestId('a-seg-duration-0')).toHaveText('段#0 耗时 1（占 1/4）');
  await expect(page.getByTestId('a-seg-duration-1')).toHaveText('段#1 耗时 3（占 3/4）');
});

test('交会-权重长度不符：定位 fly_a.duration_weights，保留原文并清除旧结果', async ({ page }) => {
  // 先成功一次（加权安全方案）
  await page.getByTestId('encounter-input').fill(CORRIDOR_SAFE_WEIGHTED);
  await page.getByTestId('encounter-submit-btn').click();
  await expect(page.getByTestId('encounter-safe-message')).toBeVisible();

  await page.getByTestId('encounter-input').fill(CORRIDOR_BAD_LENGTH);
  await page.getByTestId('encounter-submit-btn').click();

  await expect(page.getByTestId('encounter-error-banner')).toBeVisible();
  await expect(page.getByTestId('encounter-error-path')).toHaveText('fly_a.duration_weights');
  await expect(page.getByTestId('encounter-input')).toHaveValue(CORRIDOR_BAD_LENGTH);
  await expect(page.getByTestId('encounter-view')).toHaveCount(0);
  await expect(page.getByTestId('encounter-result-panel')).toHaveCount(0);
});

test('交会-非正权重：定位到具体下标 fly_a.duration_weights.1', async ({ page }) => {
  await page.getByTestId('encounter-input').fill(CORRIDOR_BAD_ZERO);
  await page.getByTestId('encounter-submit-btn').click();

  await expect(page.getByTestId('encounter-error-banner')).toBeVisible();
  await expect(page.getByTestId('encounter-error-path')).toHaveText('fly_a.duration_weights.1');
  await expect(page.getByTestId('encounter-input')).toHaveValue(CORRIDOR_BAD_ZERO);
  await expect(page.getByTestId('encounter-view')).toHaveCount(0);
});
