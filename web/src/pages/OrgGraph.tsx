import React, { useState, useEffect, useCallback } from "react";
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
import {
  fetchOrg, reloadOrg, OrgData,
  addOrgSolution, removeOrgSolution,
  addOrgChannel, removeOrgChannel,
  addOrgRoute, removeOrgRoute,
} from "../api/client";
import { Plus, Trash2, Network, RefreshCw, X } from "lucide-react";

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

// ---------------------------------------------------------------------------
// Inline form components
// ---------------------------------------------------------------------------
const inputStyle: React.CSSProperties = {
  background: "#111113", color: "#e4e4e7", border: "1px solid #2a2a2e",
  borderRadius: 6, padding: "6px 10px", fontSize: 12, outline: "none", width: "100%",
};

function AddSolutionForm({ onAdd, onCancel }: { onAdd: (name: string, path: string) => void; onCancel: () => void }) {
  const [name, setName] = useState("");
  const [path, setPath] = useState("");
  return (
    <div style={{ display: "flex", gap: 8, alignItems: "center", padding: "8px 0" }}>
      <input style={{ ...inputStyle, flex: 1 }} placeholder="Solution name" value={name} onChange={e => setName(e.target.value)} />
      <input style={{ ...inputStyle, flex: 2 }} placeholder="Path (e.g. solutions/my_app)" value={path} onChange={e => setPath(e.target.value)} />
      <button onClick={() => { if (name.trim() && path.trim()) onAdd(name.trim(), path.trim()) }} className="sage-btn sage-btn-primary" style={{ padding: "6px 12px", fontSize: 11 }}>
        Add
      </button>
      <button onClick={onCancel} style={{ background: "none", border: "none", color: "#71717a", cursor: "pointer" }}><X size={14} /></button>
    </div>
  );
}

function AddChannelForm({ onAdd, onCancel }: { onAdd: (name: string, solutions: string[]) => void; onCancel: () => void }) {
  const [name, setName] = useState("");
  const [sols, setSols] = useState("");
  return (
    <div style={{ display: "flex", gap: 8, alignItems: "center", padding: "8px 0" }}>
      <input style={{ ...inputStyle, flex: 1 }} placeholder="Channel name" value={name} onChange={e => setName(e.target.value)} />
      <input style={{ ...inputStyle, flex: 2 }} placeholder="Solutions (comma-separated)" value={sols} onChange={e => setSols(e.target.value)} />
      <button onClick={() => { if (name.trim() && sols.trim()) onAdd(name.trim(), sols.split(",").map(s => s.trim()).filter(Boolean)) }} className="sage-btn sage-btn-primary" style={{ padding: "6px 12px", fontSize: 11 }}>
        Add
      </button>
      <button onClick={onCancel} style={{ background: "none", border: "none", color: "#71717a", cursor: "pointer" }}><X size={14} /></button>
    </div>
  );
}

function AddRouteForm({ onAdd, onCancel }: { onAdd: (taskType: string, source: string, target: string) => void; onCancel: () => void }) {
  const [taskType, setTaskType] = useState("");
  const [source, setSource] = useState("");
  const [target, setTarget] = useState("");
  return (
    <div style={{ display: "flex", gap: 8, alignItems: "center", padding: "8px 0" }}>
      <input style={{ ...inputStyle, flex: 1 }} placeholder="Task type" value={taskType} onChange={e => setTaskType(e.target.value)} />
      <input style={{ ...inputStyle, flex: 1 }} placeholder="Source" value={source} onChange={e => setSource(e.target.value)} />
      <input style={{ ...inputStyle, flex: 1 }} placeholder="Target" value={target} onChange={e => setTarget(e.target.value)} />
      <button onClick={() => { if (taskType.trim() && source.trim() && target.trim()) onAdd(taskType.trim(), source.trim(), target.trim()) }} className="sage-btn sage-btn-primary" style={{ padding: "6px 12px", fontSize: 11 }}>
        Add
      </button>
      <button onClick={onCancel} style={{ background: "none", border: "none", color: "#71717a", cursor: "pointer" }}><X size={14} /></button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function OrgGraph() {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [loading, setLoading]   = React.useState(true);
  const [orgData, setOrgData]   = React.useState<OrgData>({});
  const [error,   setError]     = React.useState<string | null>(null);
  const [showAddSolution, setShowAddSolution] = useState(false);
  const [showAddChannel, setShowAddChannel]   = useState(false);
  const [showAddRoute, setShowAddRoute]       = useState(false);

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

  const handleAddSolution = async (name: string, path: string) => {
    try { await addOrgSolution(name, path); setShowAddSolution(false); await loadOrg(); }
    catch { setError("Failed to add solution"); }
  };
  const handleRemoveSolution = async (name: string) => {
    try { await removeOrgSolution(name); await loadOrg(); }
    catch { setError("Failed to remove solution"); }
  };
  const handleAddChannel = async (name: string, solutions: string[]) => {
    try { await addOrgChannel(name, solutions); setShowAddChannel(false); await loadOrg(); }
    catch { setError("Failed to add channel"); }
  };
  const handleRemoveChannel = async (name: string) => {
    try { await removeOrgChannel(name); await loadOrg(); }
    catch { setError("Failed to remove channel"); }
  };
  const handleAddRoute = async (taskType: string, source: string, target: string) => {
    try { await addOrgRoute(taskType, source, target); setShowAddRoute(false); await loadOrg(); }
    catch { setError("Failed to add route"); }
  };
  const handleRemoveRoute = async (taskType: string, source: string, target: string) => {
    try { await removeOrgRoute(taskType, source, target); await loadOrg(); }
    catch { setError("Failed to remove route"); }
  };

  if (loading) return <div style={{ padding: 32, color: "#94a3b8" }}>Loading…</div>;
  if (error)   return <div style={{ padding: 32, color: "#f87171" }}>{error}</div>;

  const isEmpty = !orgData.org;
  const channels = orgData.org?.knowledge_channels ?? {};
  const routes   = orgData.routes ?? [];
  const solutions = [...new Set([
    ...(orgData.org?.root_solution ? [orgData.org.root_solution] : []),
    ...Object.values(channels).flatMap(c => [...c.producers, ...c.consumers]),
    ...routes.flatMap(r => [r.source, r.target]),
  ])];

  return (
    <div style={{ padding: "24px 32px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: "#e4e4e7", margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
            <Network size={20} style={{ color: "#3b82f6" }} />
            Organization
          </h1>
          {orgData.org?.name && (
            <p style={{ color: "#71717a", margin: "4px 0 0", fontSize: 13 }}>{orgData.org.name}</p>
          )}
        </div>
        <button
          onClick={async () => {
            try { await reloadOrg(); await loadOrg(); }
            catch { setError("Failed to reload org configuration"); }
          }}
          className="sage-btn sage-btn-secondary"
        >
          <RefreshCw size={12} /> Reload
        </button>
      </div>

      {isEmpty ? (
        <div className="sage-empty" style={{ border: "1px dashed #2a2a2e", borderRadius: 12, padding: 48 }}>
          <Network size={32} />
          <p style={{ fontSize: 14 }}>No org.yaml configured</p>
          <p style={{ fontSize: 12, color: "#52525b" }}>
            Create <code>org.yaml</code> in your SAGE_SOLUTIONS_DIR to define your organization.
          </p>
        </div>
      ) : (
        <>
          {/* Legend */}
          <div style={{ display: "flex", gap: 24, marginBottom: 16 }}>
            <Legend color="#3b82f6" label="Knowledge channel" />
            <Legend color="#f97316" label="Task routing link" />
            <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "#94a3b8" }}>
              <div style={{ width: 14, height: 14, border: "2px dashed #60a5fa", borderRadius: 2 }} />
              <span>Root solution</span>
            </div>
          </div>

          {/* Graph */}
          <div style={{ height: 420, background: "#0f172a", borderRadius: 12, border: "1px solid #1e293b" }}>
            <ReactFlow nodes={nodes} edges={edges} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} fitView>
              <Background color="#1e293b" gap={24} />
              <Controls />
              <MiniMap nodeColor="#334155" maskColor="rgba(0,0,0,0.6)" />
            </ReactFlow>
          </div>

          {/* Management panels */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 24 }}>
            {/* Solutions */}
            <div className="sage-card" style={{ background: "#1c1c1e", borderColor: "#2a2a2e" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                <h2 style={{ fontSize: 14, fontWeight: 600, color: "#e4e4e7", margin: 0 }}>Solutions</h2>
                <button onClick={() => setShowAddSolution(true)} className="sage-btn sage-btn-secondary" style={{ padding: "4px 10px", fontSize: 11 }}>
                  <Plus size={11} /> Add
                </button>
              </div>
              {showAddSolution && <AddSolutionForm onAdd={handleAddSolution} onCancel={() => setShowAddSolution(false)} />}
              {solutions.length > 0 ? solutions.map(name => (
                <div key={name} style={{
                  display: "flex", justifyContent: "space-between", alignItems: "center",
                  padding: "8px 12px", marginBottom: 4, background: "#111113", borderRadius: 6,
                }}>
                  <span style={{ color: "#e4e4e7", fontSize: 13 }}>
                    {name}
                    {name === orgData.org?.root_solution && (
                      <span style={{ marginLeft: 8, fontSize: 10, color: "#60a5fa", background: "rgba(59,130,246,0.1)", padding: "2px 6px", borderRadius: 4 }}>root</span>
                    )}
                  </span>
                  <button onClick={() => handleRemoveSolution(name)} style={{ background: "none", border: "none", color: "#52525b", cursor: "pointer" }} title="Remove">
                    <Trash2 size={12} />
                  </button>
                </div>
              )) : <p style={{ color: "#52525b", fontSize: 12 }}>No solutions configured</p>}
            </div>

            {/* Channels */}
            <div className="sage-card" style={{ background: "#1c1c1e", borderColor: "#2a2a2e" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                <h2 style={{ fontSize: 14, fontWeight: 600, color: "#e4e4e7", margin: 0 }}>Knowledge Channels</h2>
                <button onClick={() => setShowAddChannel(true)} className="sage-btn sage-btn-secondary" style={{ padding: "4px 10px", fontSize: 11 }}>
                  <Plus size={11} /> Add
                </button>
              </div>
              {showAddChannel && <AddChannelForm onAdd={handleAddChannel} onCancel={() => setShowAddChannel(false)} />}
              {Object.entries(channels).map(([name, conf]) => (
                <div key={name} style={{
                  display: "flex", justifyContent: "space-between", alignItems: "center",
                  padding: "8px 12px", marginBottom: 4, background: "#111113", borderRadius: 6,
                }}>
                  <div>
                    <span style={{ color: "#60a5fa", fontWeight: 600, fontSize: 13 }}>{name}</span>
                    <span style={{ color: "#52525b", fontSize: 11, marginLeft: 8 }}>
                      {conf.producers.join(", ")} → {conf.consumers.join(", ")}
                    </span>
                  </div>
                  <button onClick={() => handleRemoveChannel(name)} style={{ background: "none", border: "none", color: "#52525b", cursor: "pointer" }} title="Remove">
                    <Trash2 size={12} />
                  </button>
                </div>
              ))}
              {Object.keys(channels).length === 0 && <p style={{ color: "#52525b", fontSize: 12 }}>No channels configured</p>}
            </div>
          </div>

          {/* Routes */}
          <div className="sage-card" style={{ background: "#1c1c1e", borderColor: "#2a2a2e", marginTop: 16 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <h2 style={{ fontSize: 14, fontWeight: 600, color: "#e4e4e7", margin: 0 }}>Task Routes</h2>
              <button onClick={() => setShowAddRoute(true)} className="sage-btn sage-btn-secondary" style={{ padding: "4px 10px", fontSize: 11 }}>
                <Plus size={11} /> Add
              </button>
            </div>
            {showAddRoute && <AddRouteForm onAdd={handleAddRoute} onCancel={() => setShowAddRoute(false)} />}
            {routes.length > 0 ? (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr auto", gap: "4px 12px", fontSize: 12 }}>
                <span style={{ color: "#52525b", fontWeight: 600, paddingBottom: 4 }}>Type</span>
                <span style={{ color: "#52525b", fontWeight: 600, paddingBottom: 4 }}>Source</span>
                <span style={{ color: "#52525b", fontWeight: 600, paddingBottom: 4 }}>Target</span>
                <span />
                {routes.map((r, idx) => (
                  <React.Fragment key={idx}>
                    <span style={{ color: "#f59e0b" }}>{(r as any).task_type ?? "—"}</span>
                    <span style={{ color: "#e4e4e7" }}>{r.source}</span>
                    <span style={{ color: "#e4e4e7" }}>{r.target}</span>
                    <button onClick={() => handleRemoveRoute((r as any).task_type ?? "", r.source, r.target)} style={{ background: "none", border: "none", color: "#52525b", cursor: "pointer" }}>
                      <Trash2 size={11} />
                    </button>
                  </React.Fragment>
                ))}
              </div>
            ) : <p style={{ color: "#52525b", fontSize: 12 }}>No routes configured</p>}
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
