import { useState } from 'react';
import { ApiRequestError, checkEncounter } from '../lib/api';
import { ENCOUNTER_SAMPLE } from '../lib/encounterSample';
import { EncounterView } from './EncounterView';
import type { EncounterPayload, EncounterResult } from '../lib/types';

interface ErrorState {
  path: string;
  message: string;
}

/** 双吊景交会方案编辑与检测：提交中 / 成功 / 校验失败为独立状态。 */
export function EncounterPanel() {
  const [text, setText] = useState(ENCOUNTER_SAMPLE);
  const [result, setResult] = useState<EncounterResult | null>(null);
  const [payload, setPayload] = useState<EncounterPayload | null>(null);
  const [error, setError] = useState<ErrorState | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit() {
    setBusy(true);
    // 提交即清除旧结果与旧错误；校验失败时保留本次原文
    setError(null);
    setFileError(null);
    setResult(null);
    setPayload(null);
    try {
      const r = await checkEncounter(text);
      setResult(r);
      try {
        setPayload(JSON.parse(text) as EncounterPayload);
      } catch {
        setPayload(null);
      }
    } catch (e) {
      if (e instanceof ApiRequestError) {
        setError({ path: e.path, message: e.message });
      } else {
        setError({ path: '', message: String(e) });
      }
    } finally {
      setBusy(false);
    }
  }

  function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setFileError(null);
    const reader = new FileReader();
    reader.onload = () => {
      const buf = reader.result;
      if (!(buf instanceof ArrayBuffer)) {
        setFileError('文件读取失败，请重新选择');
        return;
      }
      // 致命模式解码：任何非法 UTF-8 字节序列都直接拒绝，不做 U+FFFD 替换
      try {
        const decoded = new TextDecoder('utf-8', { fatal: true }).decode(buf);
        setText(decoded);
      } catch {
        setFileError('文件不是合法的 UTF-8 编码，请另存为 UTF-8 后重新上传');
      }
      e.target.value = '';
    };
    reader.onerror = () => {
      setFileError('文件读取失败，请重新选择');
      e.target.value = '';
    };
    reader.readAsArrayBuffer(f);
  }

  return (
    <>
      <section className="panel">
        <label htmlFor="encounter-input">
          交会方案 UTF-8 JSON（stage / fly_a / fly_b；两套吊景各带 id 与路线，全程等时 t∈[0,1]）
        </label>
        <textarea
          id="encounter-input"
          data-testid="encounter-input"
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            setFileError(null);
          }}
          spellCheck={false}
          rows={18}
        />
        <div className="actions">
          <input
            type="file"
            accept=".json,application/json"
            data-testid="encounter-file-input"
            onChange={onFile}
          />
          <button data-testid="encounter-sample-btn" onClick={() => setText(ENCOUNTER_SAMPLE)}>
            载入示例
          </button>
          <button data-testid="encounter-submit-btn" onClick={onSubmit} disabled={busy}>
            {busy ? '检测中…' : '执行交会检测'}
          </button>
        </div>

        {fileError && (
          <div className="error-banner" data-testid="encounter-file-error" role="alert">
            <div data-testid="encounter-file-error-message">{fileError}</div>
          </div>
        )}

        {error && (
          <div className="error-banner" data-testid="encounter-error-banner" role="alert">
            <strong>校验失败</strong>（首个错误字段：
            <code data-testid="encounter-error-path">{error.path || '(root)'}</code>）
            <div data-testid="encounter-error-message">{error.message}</div>
          </div>
        )}

        {result && (
          <div
            className={result.collides ? 'result-panel hit' : 'result-panel safe'}
            data-testid="encounter-result-panel"
          >
            {result.collides && result.fly_a && result.fly_b ? (
              <>
                <div>
                  首次接触全程时刻 t ={' '}
                  <strong data-testid="encounter-t-value">{result.t_display}</strong>
                </div>
                <div>
                  吊景 A（{result.fly_a.id}）：第{' '}
                  <strong data-testid="encounter-a-segment">#{result.fly_a.segment_index}</strong>{' '}
                  段，段内 t ={' '}
                  <strong data-testid="encounter-a-segment-t">
                    {result.fly_a.segment_t_display}
                  </strong>
                  ，左下角{' '}
                  <strong data-testid="encounter-a-pos">
                    ({result.fly_a.position_display?.x}, {result.fly_a.position_display?.y}) mm
                  </strong>
                </div>
                <div>
                  吊景 B（{result.fly_b.id}）：第{' '}
                  <strong data-testid="encounter-b-segment">#{result.fly_b.segment_index}</strong>{' '}
                  段，段内 t ={' '}
                  <strong data-testid="encounter-b-segment-t">
                    {result.fly_b.segment_t_display}
                  </strong>
                  ，左下角{' '}
                  <strong data-testid="encounter-b-pos">
                    ({result.fly_b.position_display?.x}, {result.fly_b.position_display?.y}) mm
                  </strong>
                </div>
                <div>
                  接触位置：
                  <strong data-testid="encounter-contact-value">
                    ({result.contact_display?.x}, {result.contact_display?.y}) mm
                  </strong>
                </div>
              </>
            ) : (
              <div data-testid="encounter-safe-message">两套吊景全程无接触，换景安全 ✅</div>
            )}
          </div>
        )}
      </section>

      <section className="canvas-area">
        {result && payload ? (
          <EncounterView payload={payload} result={result} />
        ) : (
          <div className="placeholder" data-testid="encounter-view-placeholder">
            提交后在此同时绘制两套吊景路线、起终/停位姿态与首次接触姿态
          </div>
        )}
      </section>
    </>
  );
}
