import { useState } from 'react';
import { StageView } from './components/StageView';
import { ApiRequestError, checkStage } from './lib/api';
import { SAMPLE } from './lib/sample';
import type { CheckResult, StagePayload } from './lib/types';

interface ErrorState {
  path: string;
  message: string;
}

export default function App() {
  const [text, setText] = useState(SAMPLE);
  const [result, setResult] = useState<CheckResult | null>(null);
  const [payload, setPayload] = useState<StagePayload | null>(null);
  const [error, setError] = useState<ErrorState | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit() {
    setBusy(true);
    // 先清除旧图与旧错误；失败时保留原文
    setError(null);
    setResult(null);
    setPayload(null);
    try {
      const r = await checkStage(text);
      setResult(r);
      try {
        setPayload(JSON.parse(text) as StagePayload);
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
    const reader = new FileReader();
    reader.onload = () => setText(String(reader.result ?? ''));
    reader.readAsText(f, 'utf-8');
  }

  return (
    <div className="app">
      <header>
        <h1>舞台吊景越界彩排检测</h1>
        <p>矩形吊景沿路线连续扫掠，判定首次擦碰禁入区的位置（t∈[0,1]）；可在 fly.waypoints 中填写中途停位组成折线</p>
      </header>
      <main>
        <section className="panel">
          <label htmlFor="payload-input">上传 UTF-8 JSON（stage / fly / zones）</label>
          <textarea
            id="payload-input"
            data-testid="payload-input"
            value={text}
            onChange={(e) => setText(e.target.value)}
            spellCheck={false}
            rows={18}
          />
          <div className="actions">
            <input
              type="file"
              accept=".json,application/json"
              data-testid="file-input"
              onChange={onFile}
            />
            <button data-testid="submit-btn" onClick={onSubmit} disabled={busy}>
              {busy ? '检测中…' : '执行检测'}
            </button>
          </div>

          {error && (
            <div className="error-banner" data-testid="error-banner" role="alert">
              <strong>校验失败</strong>（首个错误字段：
              <code data-testid="error-path">{error.path || '(root)'}</code>）
              <div data-testid="error-message">{error.message}</div>
            </div>
          )}

          {result && (
            <div
              className={result.collides ? 'result-panel hit' : 'result-panel safe'}
              data-testid="result-panel"
            >
              {result.collides ? (
                <>
                  <div>
                    首次越界时刻 t ={' '}
                    <strong data-testid="t-value">{result.t_display}</strong>
                  </div>
                  <div>
                    命中段号：<strong data-testid="segment-value">#{result.segment_index}</strong>
                    （段内 t ={' '}
                    <strong data-testid="segment-t-value">{result.segment_t_display}</strong>）
                  </div>
                  <div>
                    责任禁入区：<strong data-testid="zone-value">{result.zone_id}</strong>
                  </div>
                  <div>
                    责任边（从 0 起）：<strong data-testid="edge-value">#{result.edge_index}</strong>
                  </div>
                  <div>
                    碰撞姿态左下角：
                    <strong data-testid="pos-value">
                      ({result.position_display?.x}, {result.position_display?.y}) mm
                    </strong>
                  </div>
                </>
              ) : (
                <div data-testid="safe-message">全程无碰撞，路径安全 ✅</div>
              )}
            </div>
          )}
        </section>

        <section className="canvas-area">
          {result && payload ? (
            <StageView payload={payload} result={result} />
          ) : (
            <div className="placeholder" data-testid="view-placeholder">
              提交后在此绘制可缩放俯视图（起终姿态 / 完整路径 / 首次碰撞姿态 / 责任边）
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
