import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react';

const STAGE = 10000;

/** 舞台坐标 y 向上 → SVG y 向下。 */
export const stageY = (y: number) => STAGE - y;

interface ViewBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

const INITIAL_VIEW: ViewBox = { x: -600, y: -600, w: 11200, h: 11200 };

interface CanvasContextValue {
  view: ViewBox;
  Y: (y: number) => number;
}

const StageCanvasContext = createContext<CanvasContextValue | null>(null);

/** 供画布内部元素读取当前视图（缩放相关线宽 / 字号）与 y 翻转函数。 */
export function useStageCanvas(): CanvasContextValue {
  const ctx = useContext(StageCanvasContext);
  if (!ctx) throw new Error('useStageCanvas must be used inside <StageCanvas>');
  return ctx;
}

interface Props {
  children: ReactNode;
  testid?: string;
}

/** 可缩放（滚轮 / 按钮）、可拖拽平移的台口俯视图外壳；台口与场景由 children 绘制。 */
export function StageCanvas({ children, testid = 'stage-view' }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [view, setView] = useState<ViewBox>(INITIAL_VIEW);
  const drag = useRef<{ px: number; py: number } | null>(null);

  // 滚轮缩放需要非 passive 监听
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = svg.getBoundingClientRect();
      const fx = (e.clientX - rect.left) / rect.width;
      const fy = (e.clientY - rect.top) / rect.height;
      const scale = e.deltaY < 0 ? 0.8 : 1.25;
      setView((v) => {
        const w = Math.min(60000, Math.max(200, v.w * scale));
        const h = Math.min(60000, Math.max(200, v.h * scale));
        return { x: v.x + fx * (v.w - w), y: v.y + fy * (v.h - h), w, h };
      });
    };
    svg.addEventListener('wheel', onWheel, { passive: false });
    return () => svg.removeEventListener('wheel', onWheel);
  }, []);

  const zoomBy = (scale: number) =>
    setView((v) => {
      const w = Math.min(60000, Math.max(200, v.w * scale));
      const h = Math.min(60000, Math.max(200, v.h * scale));
      return { x: v.x + (v.w - w) / 2, y: v.y + (v.h - h) / 2, w, h };
    });

  return (
    <div className="stage-view-wrap">
      <div className="view-toolbar">
        <button data-testid="zoom-in" onClick={() => zoomBy(0.8)}>
          放大
        </button>
        <button data-testid="zoom-out" onClick={() => zoomBy(1.25)}>
          缩小
        </button>
        <button data-testid="zoom-reset" onClick={() => setView(INITIAL_VIEW)}>
          重置视图
        </button>
        <span className="hint">滚轮缩放 · 拖拽平移 · 坐标单位 mm</span>
      </div>
      <svg
        ref={svgRef}
        data-testid={testid}
        className="stage-view"
        viewBox={`${view.x} ${view.y} ${view.w} ${view.h}`}
        onPointerDown={(e) => {
          drag.current = { px: e.clientX, py: e.clientY };
          (e.target as Element).setPointerCapture?.(e.pointerId);
        }}
        onPointerMove={(e) => {
          if (!drag.current || !svgRef.current) return;
          const rect = svgRef.current.getBoundingClientRect();
          const dx = ((e.clientX - drag.current.px) / rect.width) * view.w;
          const dy = ((e.clientY - drag.current.py) / rect.height) * view.h;
          drag.current = { px: e.clientX, py: e.clientY };
          setView((v) => ({ ...v, x: v.x - dx, y: v.y - dy }));
        }}
        onPointerUp={() => (drag.current = null)}
        onPointerLeave={() => (drag.current = null)}
      >
        <StageCanvasContext.Provider value={{ view, Y: stageY }}>
          {/* 台口 */}
          <rect
            x={0}
            y={0}
            width={STAGE}
            height={STAGE}
            fill="#fbfcfe"
            stroke="#33475b"
            strokeWidth={view.w * 0.0012}
            data-testid="stage-boundary"
          />
          <text x={120} y={stageY(STAGE - 120)} fontSize={view.w * 0.016} fill="#33475b">
            台口 10000 × 10000 mm
          </text>
          {children}
        </StageCanvasContext.Provider>
      </svg>
    </div>
  );
}
