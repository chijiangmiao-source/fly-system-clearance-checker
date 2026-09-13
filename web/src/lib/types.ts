export interface CheckResult {
  collides: boolean;
  t: number | null;
  t_display: string | null;
  t_fraction?: string | null;
  zone_id: string | null;
  zone_index: number | null;
  edge_index: number | null;
  /** 命中段序号（从 0 起）；单段请求恒为 0。无碰撞为 null。 */
  segment_index: number | null;
  /** 命中段内 t 的展示值（half-up 六位）；单段请求与 t_display 相同。 */
  segment_t_display: string | null;
  position: { x: number; y: number } | null;
  position_display: { x: string; y: string } | null;
}

export interface StagePoint {
  x: number;
  y: number;
}

export interface FlyZone {
  id: string;
  vertices: StagePoint[];
}

export interface StagePayload {
  stage: { width: number; height: number };
  fly: {
    width: number;
    height: number;
    start: StagePoint;
    end: StagePoint;
    /** 可选中途停位：路线按 start → 各停位 → end 组成折线；缺省为单段直线。 */
    waypoints?: StagePoint[];
  };
  zones: FlyZone[];
}
