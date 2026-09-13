import { describe, expect, it } from 'vitest';
import { formatMm, formatT, roundHalfUp } from './format';

describe('formatT：十进制 half-up 保留六位', () => {
  it('整数与常规小数', () => {
    expect(formatT(0)).toBe('0.000000');
    expect(formatT(1)).toBe('1.000000');
    expect(formatT(0.5)).toBe('0.500000');
    expect(formatT(0.25)).toBe('0.250000');
  });

  it('循环小数临界舍入', () => {
    expect(formatT(1 / 3)).toBe('0.333333');
    expect(formatT(2 / 3)).toBe('0.666667');
    expect(formatT(1 / 6)).toBe('0.166667');
    expect(formatT(1 / 7)).toBe('0.142857');
  });

  it('第七位恰为 5 时 half-up 进位', () => {
    expect(formatT(0.0000005)).toBe('0.000001');
    expect(formatT(0.1234565)).toBe('0.123457');
    expect(formatT(0.9999995)).toBe('1.000000');
  });

  it('第七位小于 5 时舍去', () => {
    expect(formatT(0.0000004)).toBe('0.000000');
    expect(formatT(0.1234564)).toBe('0.123456');
  });

  it('级联进位', () => {
    expect(roundHalfUp(0.09999995, 6)).toBe('0.100000');
    expect(roundHalfUp(9.9999999, 6)).toBe('10.000000');
  });
});

describe('formatMm：毫米坐标', () => {
  it('整数不带小数点', () => {
    expect(formatMm(1250)).toBe('1250');
    expect(formatMm(0)).toBe('0');
  });

  it('最多三位小数并去尾零', () => {
    expect(formatMm(1250.5)).toBe('1250.5');
    expect(formatMm(1250.25)).toBe('1250.25');
    expect(formatMm(4000 / 3)).toBe('1333.333');
  });
});
