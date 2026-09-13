import { describe, expect, it } from 'vitest';
import { addDecimalInts, normalizeDecimalInt } from './bigInt';
import { asPositiveInt, parseJsonPreservingBigInts } from './json';

describe('parseJsonPreservingBigInts', () => {
  it('常规 JSON 与 JSON.parse 行为一致', () => {
    const text = `{
      "stage": {"width": 10000, "height": 10000},
      "ids": ["A", "B"],
      "ok": true, "no": false, "nil": null,
      "frac": 12.5, "exp": 1e3, "neg": -7
    }`;
    expect(parseJsonPreservingBigInts(text)).toEqual({
      stage: { width: 10000, height: 10000 },
      ids: ['A', 'B'],
      ok: true,
      no: false,
      nil: null,
      frac: 12.5,
      exp: 1000,
      neg: -7,
    });
  });

  it('支持字符串转义与 Unicode', () => {
    const p = parseJsonPreservingBigInts('{"s":"a\\nb\\t\\"c\\u4e2d"}');
    expect((p as { s: string }).s).toBe('a\nb\t"c中');
  });

  it('安全范围内的整数仍解析为 number', () => {
    const p = parseJsonPreservingBigInts('[1, 42, 9007199254740991]') as unknown[];
    expect(p).toEqual([1, 42, Number.MAX_SAFE_INTEGER]);
    expect(p.map((v) => typeof v)).toEqual(['number', 'number', 'number']);
  });

  it('16 位超界整数（2^53+1）保留精确十进制串，不被舍入', () => {
    const p = parseJsonPreservingBigInts('[9007199254740993]') as unknown[];
    expect(p[0]).toBe('9007199254740993');
    // 对照：JSON.parse 确实会舍入末位
    expect(JSON.parse('[9007199254740993]')[0]).toBe(9007199254740992);
  });

  it('310 位整数（>Number.MAX_VALUE）保留精确串而非 Infinity', () => {
    const huge = '1' + '0'.repeat(309);
    const p = parseJsonPreservingBigInts(`{"duration_weights":[${huge},1]}`) as {
      duration_weights: unknown[];
    };
    expect(p.duration_weights[0]).toBe(huge);
    expect(p.duration_weights[1]).toBe(1);
    expect(Number.isFinite(p.duration_weights[0] as number)).toBe(false); // 作为字符串保留
    expect(typeof p.duration_weights[0]).toBe('string');
  });

  it('前导零字面量属非法 JSON，仍按语法错误拒绝（服务端同样拒绝）', () => {
    expect(() => parseJsonPreservingBigInts('[000123]')).toThrow();
    expect(() => parseJsonPreservingBigInts('[01]')).toThrow();
  });

  it('非法 JSON 仍抛出（含非标准常量 NaN/Infinity、尾随逗号等）', () => {
    expect(() => parseJsonPreservingBigInts('{a:1}')).toThrow();
    expect(() => parseJsonPreservingBigInts('[1,]')).toThrow();
    expect(() => parseJsonPreservingBigInts('NaN')).toThrow();
    expect(() => parseJsonPreservingBigInts('Infinity')).toThrow();
    expect(() => parseJsonPreservingBigInts('{"a":}')).toThrow();
    expect(() => parseJsonPreservingBigInts('01')).toThrow();
    expect(() => parseJsonPreservingBigInts('1.')).toThrow();
    expect(() => parseJsonPreservingBigInts('"unterminated')).toThrow();
  });
});

describe('asPositiveInt', () => {
  it('安全范围内的正整数通过', () => {
    expect(asPositiveInt(1)).toBe(1);
    expect(asPositiveInt(Number.MAX_SAFE_INTEGER)).toBe(Number.MAX_SAFE_INTEGER);
  });

  it('非正、非安全整数、非整数 number 拒绝', () => {
    expect(asPositiveInt(0)).toBeNull();
    expect(asPositiveInt(-3)).toBeNull();
    expect(asPositiveInt(1.5)).toBeNull();
    expect(asPositiveInt(Number.MAX_SAFE_INTEGER + 2)).toBeNull();
    expect(asPositiveInt(Infinity)).toBeNull();
    expect(asPositiveInt(NaN)).toBeNull();
    expect(asPositiveInt(true)).toBeNull();
  });

  it('十进制正整数字符串通过（安全范围归一为 number，超界保留串）', () => {
    expect(asPositiveInt('0042')).toBe(42);
    expect(asPositiveInt('9007199254740993')).toBe('9007199254740993');
    expect(asPositiveInt('1' + '0'.repeat(309))).toBe('1' + '0'.repeat(309));
  });

  it('零串、负数串、非数字串拒绝', () => {
    expect(asPositiveInt('0')).toBeNull();
    expect(asPositiveInt('000')).toBeNull();
    expect(asPositiveInt('-5')).toBeNull();
    expect(asPositiveInt('1.5')).toBeNull();
    expect(asPositiveInt('1e3')).toBeNull();
    expect(asPositiveInt(null)).toBeNull();
  });
});

describe('十进制字符串运算', () => {
  it('normalizeDecimalInt 去前导零', () => {
    expect(normalizeDecimalInt('000123')).toBe('123');
    expect(normalizeDecimalInt('000')).toBe('0');
    expect(normalizeDecimalInt('100')).toBe('100');
  });

  it('addDecimalInts 精确逐位进位', () => {
    expect(addDecimalInts('0', '0')).toBe('0');
    expect(addDecimalInts('3', '1')).toBe('4');
    expect(addDecimalInts('999', '2')).toBe('1001');
    expect(addDecimalInts('123456789012345678901234567890', '987654321098765432109876543210'))
      .toBe('1111111110111111111011111111100');
  });

  it('三百一十位整数求和不溢出', () => {
    const a = '5' + '0'.repeat(308);
    expect(addDecimalInts(a, a)).toBe('1' + '0'.repeat(309));
  });
});
