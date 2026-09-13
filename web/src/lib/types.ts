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

/** 双吊景交会方案中的单套吊景（带编号与各自折线路线）。 */
export interface EncounterFly {
  id: string;
  width: number;
  height: number;
  start: StagePoint;
  end: StagePoint;
  waypoints?: StagePoint[];
  /** 可选各路线段相对耗时（正整数数组，长度 = 段数）；缺省时各段等时。 */
  duration_weights?: number[];
}

export interface EncounterPayload {
  stage: { width: number; height: number };
  fly_a: EncounterFly;
  fly_b: EncounterFly;
}

/** 首次接触时某一套吊景的姿态与所在段。 */
export interface FlyPose {
  id: string;
  segment_index: number;
  segment_t_display: string;
  position: { x: number; y: number };
  position_display: { x: string; y: string };
}

export interface EncounterResult {
  collides: boolean;
  t: number | null;
  t_display: string | null;
  t_fraction?: string | null;
  fly_a: FlyPose | null;
  fly_b: FlyPose | null;
  contact: { x: number; y: number } | null;
  contact_display: { x: string; y: string } | null;
}
