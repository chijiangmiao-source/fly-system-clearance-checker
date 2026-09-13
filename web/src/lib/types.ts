export interface CheckResult {
  collides: boolean;
  t: number | null;
  t_display: string | null;
  t_fraction?: string | null;
  zone_id: string | null;
  zone_index: number | null;
  edge_index: number | null;
  position: { x: number; y: number } | null;
  position_display: { x: string; y: string } | null;
}

export interface FlyZone {
  id: string;
  vertices: Array<{ x: number; y: number }>;
}

export interface StagePayload {
  stage: { width: number; height: number };
  fly: {
    width: number;
    height: number;
    start: { x: number; y: number };
    end: { x: number; y: number };
  };
  zones: FlyZone[];
}
