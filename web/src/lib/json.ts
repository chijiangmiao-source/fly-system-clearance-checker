/**
 * 保留超大整数字面量的严格 JSON 解析。
 *
 * 直接 JSON.parse 会把 duration_weights 里超过 Number.MAX_SAFE_INTEGER 的
 * 正整数按二进制浮点舍入（16 位丢末位），超过 1.8e308 的字面量更变成
 * Infinity。这里实现完整 JSON 文法的递归下降解析：普通数值仍解析为 number，
 * 而超出安全整数范围的*整数字面量*原样保留为精确十进制字符串
 * （负数带 "-" 前缀），交由 bigInt 做字符串级运算与展示。
 * 带小数 / 指数的数值仍按 number 解析（坐标等取值本就有界）。
 */

import { isDecimalDigits, normalizeDecimalInt } from './bigInt';

class JsonScanner {
  private i = 0;

  constructor(private readonly src: string) {}

  parse(): unknown {
    this.ws();
    const v = this.value();
    this.ws();
    if (this.i !== this.src.length) {
      throw new SyntaxError(`unexpected character at position ${this.i}`);
    }
    return v;
  }

  private peek(): string {
    return this.src[this.i] ?? '';
  }

  private ws(): void {
    while (this.i < this.src.length && ' \t\n\r'.includes(this.src[this.i])) {
      this.i += 1;
    }
  }

  private value(): unknown {
    const c = this.peek();
    if (c === '{') return this.object();
    if (c === '[') return this.array();
    if (c === '"') return this.string();
    if (c === 't') return this.literal('true', true);
    if (c === 'f') return this.literal('false', false);
    if (c === 'n') return this.literal('null', null);
    if (c === '-' || (c >= '0' && c <= '9')) return this.number();
    throw new SyntaxError(`unexpected character at position ${this.i}`);
  }

  private literal(word: string, val: unknown): unknown {
    if (!this.src.startsWith(word, this.i)) {
      throw new SyntaxError(`invalid literal at position ${this.i}`);
    }
    this.i += word.length;
    return val;
  }

  private object(): Record<string, unknown> {
    this.i += 1; // {
    const obj: Record<string, unknown> = {};
    this.ws();
    if (this.peek() === '}') {
      this.i += 1;
      return obj;
    }
    for (;;) {
      this.ws();
      if (this.peek() !== '"') {
        throw new SyntaxError(`expected string key at position ${this.i}`);
      }
      const key = this.string();
      this.ws();
      if (this.src[this.i] !== ':') {
        throw new SyntaxError(`expected ':' at position ${this.i}`);
      }
      this.i += 1;
      this.ws();
      obj[key] = this.value();
      this.ws();
      const c = this.src[this.i];
      if (c === ',') {
        this.i += 1;
        continue;
      }
      if (c === '}') {
        this.i += 1;
        return obj;
      }
      throw new SyntaxError(`expected ',' or '}' at position ${this.i}`);
    }
  }

  private array(): unknown[] {
    this.i += 1; // [
    const arr: unknown[] = [];
    this.ws();
    if (this.peek() === ']') {
      this.i += 1;
      return arr;
    }
    for (;;) {
      this.ws();
      arr.push(this.value());
      this.ws();
      const c = this.src[this.i];
      if (c === ',') {
        this.i += 1;
        continue;
      }
      if (c === ']') {
        this.i += 1;
        return arr;
      }
      throw new SyntaxError(`expected ',' or ']' at position ${this.i}`);
    }
  }

  private string(): string {
    // 字符串仅需忠实还原：交给 JSON.parse 处理转义与代理对，扫描时跳过匹配的闭合引号
    const start = this.i;
    this.i += 1; // opening quote
    while (this.i < this.src.length) {
      const c = this.src[this.i];
      if (c === '\\') {
        this.i += 2;
        continue;
      }
      if (c === '"') {
        const raw = this.src.slice(start, this.i + 1);
        this.i += 1;
        return JSON.parse(raw) as string;
      }
      if (c.charCodeAt(0) < 0x20) {
        throw new SyntaxError(`unescaped control character at position ${this.i}`);
      }
      this.i += 1;
    }
    throw new SyntaxError('unterminated string');
  }

  private number(): unknown {
    const start = this.i;
    if (this.peek() === '-') this.i += 1;
    if (this.src[this.i] === '0') {
      this.i += 1;
    } else if (this.src[this.i] >= '1' && this.src[this.i] <= '9') {
      while (this.src[this.i] >= '0' && this.src[this.i] <= '9') this.i += 1;
    } else {
      throw new SyntaxError(`invalid number at position ${start}`);
    }

    let isInteger = true;
    if (this.src[this.i] === '.') {
      isInteger = false;
      this.i += 1;
      const fracStart = this.i;
      while (this.src[this.i] >= '0' && this.src[this.i] <= '9') this.i += 1;
      if (this.i === fracStart) {
        throw new SyntaxError(`invalid number at position ${start}`);
      }
    }
    if (this.src[this.i] === 'e' || this.src[this.i] === 'E') {
      isInteger = false;
      this.i += 1;
      if (this.src[this.i] === '+' || this.src[this.i] === '-') this.i += 1;
      const expStart = this.i;
      while (this.src[this.i] >= '0' && this.src[this.i] <= '9') this.i += 1;
      if (this.i === expStart) {
        throw new SyntaxError(`invalid number at position ${start}`);
      }
    }

    const token = this.src.slice(start, this.i);
    if (!isInteger) {
      return JSON.parse(token) as number;
    }
    // 整数字面量：数值恰为安全整数时与 JSON.parse 一致返回 number
    // （含 16 位但仍安全的整数，如 9007199254740991）；超出安全范围
    // （被浮点舍入或溢出为 Infinity）时保留精确十进制字符串。
    const n = Number(token);
    if (Number.isSafeInteger(n)) {
      return n;
    }
    const negative = token.startsWith('-');
    const digits = normalizeDecimalInt(token.slice(negative ? 1 : 0));
    return negative ? `-${digits}` : digits;
  }
}

/** 严格 JSON 解析；超大整数字面量保留为精确十进制字符串。 */
export function parseJsonPreservingBigInts(text: string): unknown {
  return new JsonScanner(text).parse();
}

/** 精确权重值：安全整数为 number，超出安全范围为精确十进制字符串。 */
export type IntValue = number | string;

/**
 * 把一个已解析的权重值归一化为精确正整数：
 * number 必须是安全范围内的正整数；string 必须是十进制正整数串
 * （允许前导零，归一化展示）。不合规返回 null，与服务端校验对齐
 * （非整数 / 非正 / 被浮点舍入的超大数均不应出现在成功响应的方案里）。
 */
export function asPositiveInt(v: unknown): IntValue | null {
  if (typeof v === 'number') {
    return Number.isSafeInteger(v) && v >= 1 ? v : null;
  }
  if (isDecimalDigits(v)) {
    const d = normalizeDecimalInt(v);
    if (d === '0') return null;
    if (d.length <= 15) {
      const n = Number(d);
      if (Number.isSafeInteger(n)) return n;
    }
    return d;
  }
  return null;
}
