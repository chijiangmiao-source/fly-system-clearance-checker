/**
 * 超大正整数的精确十进制支持。
 *
 * duration_weights 是正整数，但 JSON.parse 会把超过 Number.MAX_SAFE_INTEGER
 * 的整数舍入（16 位权重末位丢失），1e309 以上更直接变成 Infinity（整段标注
 * 消失、求和溢出）。因此权重一律保留为精确十进制字符串，并在此做字符串级
 * 归一化与求和，渲染时逐位展示、不经 Number。
 */

/** 是否为十进制非负整数串（仅数字、不含符号/小数点/指数）。 */
export function isDecimalDigits(s: unknown): s is string {
  return typeof s === 'string' && /^\d+$/.test(s);
}

/** 规范化十进制非负整数串：去掉多余前导零（"000" → "0"）。 */
export function normalizeDecimalInt(s: string): string {
  const t = s.replace(/^0+/, '');
  return t === '' ? '0' : t;
}

/** 两个非负整数十进制串的精确和（逐位进位，不经过 Number）。 */
export function addDecimalInts(a: string, b: string): string {
  let i = a.length - 1;
  let j = b.length - 1;
  let carry = 0;
  let out = '';
  while (i >= 0 || j >= 0 || carry > 0) {
    const da = i >= 0 ? a.charCodeAt(i) - 48 : 0;
    const db = j >= 0 ? b.charCodeAt(j) - 48 : 0;
    const sum = da + db + carry;
    out = String(sum % 10) + out;
    carry = sum >= 10 ? 1 : 0;
    i -= 1;
    j -= 1;
  }
  return out;
}
