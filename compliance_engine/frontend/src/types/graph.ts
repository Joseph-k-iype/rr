export interface GraphNode {
  id: string;
  type: string;
  data: {
    label?: string;
    rule_id?: string;
    priority?: number;
    odrl_type?: string;
    outcome?: string;
    countries?: string[];
    country_count?: number;
    has_pii_required?: boolean;
    permission_name?: string;
    prohibition_name?: string;
    expanded?: boolean;
    onExpand?: () => void;
    side?: 'origin' | 'receiving';
  };
  position: { x: number; y: number };
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  data?: {
    relationship: string;
  };
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  stats: {
    total_rules: number;
    total_groups: number;
    total_edges: number;
  };
}
