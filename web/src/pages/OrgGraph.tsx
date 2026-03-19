import React, { useEffect, useCallback } from "react";
import {
  ReactFlow,
  Node,
  Edge,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { fetchOrg, reloadOrg, OrgData } from "../api/client";

function buildGraph(org: OrgData): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [];
  const edges: Edge[] = [];
  const channels = org.org?.knowledge_channels ?? {};
  const routes   = org.routes ?? [];
  const root     = org.org?.root_solution;
  const allNames = new Set<string>();

  if (root) allNames.add(root);
  Object.values(channels).forEach(({ producers, consumers }) => {
    producers.forEach((p) => allNames.add(p));
    consumers.forEach((c) => allNames.add(c));
  });
  routes.forEach(({ source, target }) => {
    allNames.add(source);
    allNames.add(target);
  });

  let i = 0;
  allNames.forEach((name) => {
    nodes.push({
      id: name,
      data: { label: name },
      position: { x: (i % 4) * 240, y: Math.floor(i / 4) * 130 },
      style: {
        background: name === root ? "#1e3a5f" : "#1e293b",
        color: "#e2e8f0",
        border: name === root ? "2px dashed #60a5fa" : "1px solid #475569",
        borderRadius: 8,
        padding: "8px 16px",
        fontWeight: name === root ? 700 : 400,
      },
    });
    i++;
  });

  // Blue edges — knowledge channels
  let ei = 0;
  Object.entries(channels).forEach(([chName, { producers, consumers }]) => {
    producers.forEach((producer) => {
      consumers.forEach((consumer) => {
        edges.push({
          id: `ch-${chName}-${ei++}`,
          source: producer,
          target: consumer,
          label: chName,
          style: { stroke: "#3b82f6" },
          labelStyle: { fill: "#93c5fd", fontSize: 10 },
          markerEnd: { type: MarkerType.ArrowClosed, color: "#3b82f6" },
          type: "smoothstep",
        });
      });
    });
  });

  // Orange edges — task routing links
  routes.forEach(({ source, target }, idx) => {
    edges.push({
      id: `route-${source}-${target}-${idx}`,
      source,
      target,
      label: "routes tasks",
      style: { stroke: "#f97316" },
      labelStyle: { fill: "#fdba74", fontSize: 10 },
      markerEnd: { type: MarkerType.ArrowClosed, color: "#f97316" },
      type: "smoothstep",
    });
  });

  return { nodes, edges };
}

export default function OrgGraph() {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [loading, setLoading]   = React.useState(true);
  const [orgData, setOrgData]   = React.useState<OrgData>({});
  const [error,   setError]     = React.useState<string | null>(null);

  const loadOrg = useCallback(async () => {
    try {
      setLoading(true);
      const data = await fetchOrg();
      setOrgData(data);
      const { nodes: n, edges: e } = buildGraph(data);
      setNodes(n);
      setEdges(e);
      setError(null);
    } catch {
      setError("Failed to load org configuration");
    } finally {
      setLoading(false);
    }
  }, [setNodes, setEdges]);

  useEffect(() => { loadOrg(); }, [loadOrg]);

  if (loading) return <div style={{ padding: 32, color: "#94a3b8" }}>Loading…</div>;
  if (error)   return <div style={{ padding: 32, color: "#f87171" }}>{error}</div>;

  const isEmpty = !orgData.org?.name;

  return (
    <div style={{ padding: "24px 32px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, color: "#f1f5f9", margin: 0 }}>
            Organization
          </h1>
          {orgData.org?.name && (
            <p style={{ color: "#64748b", margin: "4px 0 0" }}>{orgData.org.name}</p>
          )}
        </div>
        <button
          onClick={async () => { await reloadOrg(); await loadOrg(); }}
          style={{
            padding: "8px 16px", borderRadius: 6,
            background: "#1e293b", color: "#94a3b8",
            border: "1px solid #334155", cursor: "pointer",
          }}
        >
          Reload
        </button>
      </div>

      {isEmpty ? (
        <div style={{
          padding: 48, textAlign: "center", color: "#64748b",
          border: "1px dashed #334155", borderRadius: 12,
        }}>
          <p style={{ fontSize: 18, marginBottom: 8 }}>No org.yaml configured</p>
          <p style={{ fontSize: 14 }}>
            Create <code>org.yaml</code> in your SAGE_SOLUTIONS_DIR to define your organization.
          </p>
        </div>
      ) : (
        <>
          <div style={{ display: "flex", gap: 24, marginBottom: 16 }}>
            <Legend color="#3b82f6" label="Knowledge channel" />
            <Legend color="#f97316" label="Task routing link" />
            <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "#94a3b8" }}>
              <div style={{ width: 14, height: 14, border: "2px dashed #60a5fa", borderRadius: 2 }} />
              <span>Root solution</span>
            </div>
          </div>

          <div style={{ height: 520, background: "#0f172a", borderRadius: 12, border: "1px solid #1e293b" }}>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              fitView
            >
              <Background color="#1e293b" gap={24} />
              <Controls />
              <MiniMap nodeColor="#334155" maskColor="rgba(0,0,0,0.6)" />
            </ReactFlow>
          </div>

          <div style={{ marginTop: 24 }}>
            <h2 style={{ fontSize: 16, fontWeight: 600, color: "#f1f5f9", marginBottom: 12 }}>
              Knowledge Channels
            </h2>
            {Object.entries(orgData.org?.knowledge_channels ?? {}).map(([name, conf]) => (
              <div key={name} style={{
                padding: "12px 16px", marginBottom: 8,
                background: "#1e293b", borderRadius: 8, border: "1px solid #334155",
                display: "flex", justifyContent: "space-between",
              }}>
                <span style={{ color: "#60a5fa", fontWeight: 600 }}>{name}</span>
                <span style={{ color: "#64748b", fontSize: 13 }}>
                  {conf.producers.join(", ")} → {conf.consumers.join(", ")}
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "#94a3b8" }}>
      <div style={{ width: 32, height: 2, background: color }} />
      <span>{label}</span>
    </div>
  );
}
