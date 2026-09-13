import { useState } from 'react';
import { StageView } from './components/StageView';
import { EncounterPanel } from './components/EncounterPanel';
import { ApiRequestError, checkStage } from './lib/api';
import { SAMPLE } from './lib/sample';
import type { CheckResult, StagePayload } from './lib/types';

interface ErrorState {
  path: string;
  message: string;
}

type Mode = 'single' | 'encounter';

export default function App() {
  const [mode, setMode] = useState<Mode>('single');

  return (
    <div className="app">
      <header>
        <h1>舞台吊景越界彩排检测</h1>
        <p>矩形吊景沿路线连续扫掠，判定首次擦碰位置（t∈[0,1]）；可在 waypoints 中填写中途停位组成折线</p>
        <nav className="mode-tabs" data-testid="mode-tabs">
          <button
            type="button"
            className={mode === 'single' ? 'tab active' : 'tab'}
            data-testid="tab-single"
            onClick={() => setMode('single')}
          >
            单吊景越界检测
          </button>
          <button
            type="button"
            className={mode === 'encounter' ? 'tab active' : 'tab'}
            data-testid="tab-encounter"
            onClick={() => setMode('encounter')}
          >
            双吊景交会分析
          </button>
        </nav>
      </header>
      {/* 两个面板各自保留独立的提交中/成功/失败状态，切换页签不清除 */}
      <main>
        <div className={mode === 'single' ? 'mode-panel' : 'mode-panel hidden'} data-testid="panel-single">
          <SinglePanel />
        </div>
        <div className={mode === 'encounter' ? 'mode-panel' : 'mode-panel hidden'} data-testid="panel-encounter">
          <EncounterPanel />
        </div>
      </main>
    </div>
  );
}

function SinglePanel() {
  const [text, setText] = useState(SAMPLE);
  const [result, setResult] = useState<CheckResult | null>(null);
  const [payload, setPayload] = useState<StagePayload | null>(null);
  const [error, setError] = useState<ErrorState | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit() {
    setBusy(true);
    // 先清除旧图与旧错误；失败时保留原文
    setError(null);
    setFileError(null);
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
    setFileError(null);
    const reader = new FileReader();
    reader.onload = () => {
      const buf = reader.result;
      if (!(buf instanceof ArrayBuffer)) {
        setFileError('文件读取失败，请重新选择');
        return;
      }
      // 致命模式解码：任何非法 UTF-8 字节序列都直接拒绝，
      // 不做 U+FFFD 替换，避免带着损坏内容继续检测
      let decoded: string;
      try {
        decoded = new TextDecoder('utf-8', { fatal: true }).decode(buf);
      } catch {
        setFileError('文件不是合法的 UTF-8 编码，请另存为 UTF-8 后重新上传');
        e.target.value = '';
        return;
      }
      setText(decoded);
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
        <label htmlFor="payload-input">上传 UTF-8 JSON（stage / fly / zones）</label>
        <textarea
          id="payload-input"
          data-testid="payload-input"
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
            data-testid="file-input"
            onChange={onFile}
          />
          <button data-testid="submit-btn" onClick={onSubmit} disabled={busy}>
            {busy ? '检测中…' : '执行检测'}
          </button>
        </div>

        {fileError && (
          <div className="error-banner" data-testid="file-error" role="alert">
            <div data-testid="file-error-message">{fileError}</div>
          </div>
        )}

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
    </>
  );
}
