/** 十进制 half-up 保留固定小数位（基于最短舍入十进制串，避免二进制浮点误差）。 */

function expandExponent(s: string): string {
  const m = /^(\d)(?:\.(\d+))?[eE]([+-]?\d+)$/.exec(s);
  if (!m) return s;
  const digits = m[1] + (m[2] ?? '');
  const exp = parseInt(m[3], 10);
  const point = 1 + exp;
  if (point <= 0) return '0.' + '0'.repeat(-point) + digits;
  if (point >= digits.length) return digits + '0'.repeat(point - digits.length);
  return digits.slice(0, point) + '.' + digits.slice(point);
}

export function roundHalfUp(value: number, decimals: number): string {
  if (!Number.isFinite(value)) return String(value);
  const neg = value < 0 || Object.is(value, -0);
  const expanded = expandExponent(Math.abs(value).toString());
  const [intPart, fracRaw = ''] = expanded.split('.');
  const frac = fracRaw.padEnd(decimals + 1, '0');
  const digits = (intPart + frac.slice(0, decimals)).split('').map(Number);
  if (Number(frac[decimals] ?? '0') >= 5) {
    let i = digits.length - 1;
    while (i >= 0) {
      if (digits[i] < 9) {
        digits[i] += 1;
        break;
      }
      digits[i] = 0;
      i -= 1;
    }
    if (i < 0) digits.unshift(1);
  }
  const ip = digits.slice(0, digits.length - decimals).join('');
  const fp = digits.slice(digits.length - decimals).join('');
  return (neg ? '-' : '') + ip + '.' + fp;
}

/** 最小 t 的展示格式：十进制 half-up 保留六位。 */
export function formatT(t: number): string {
  return roundHalfUp(t, 6);
}

/** 启用窗口刻度（全程百万分之一整数）的展示格式：换算到 t 轴保留六位。 */
export function formatTick(tick: number): string {
  return formatT(tick / 1_000_000);
}

/** 毫米坐标展示：half-up 保留三位并去掉多余尾零。 */
export function formatMm(v: number): string {
  const s = roundHalfUp(v, 3);
  return s.includes('.') ? s.replace(/\.?0+$/, '') : s;
}
