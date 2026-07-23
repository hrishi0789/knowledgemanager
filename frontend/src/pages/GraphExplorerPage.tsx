import React from 'react';
import { CytoscapeCanvas } from '../components/graph/CytoscapeCanvas';
import { GraphToolbar } from '../components/graph/GraphToolbar';
import { NodeInspector } from '../components/graph/NodeInspector';
import { useUiStore } from '../stores/uiStore';

// In a real implementation, we'd fetch actual graph data. For this page we'll fetch
// the overview but use a placeholder or initial query for the actual nodes/edges if
// a global graph fetch isn't available (the architecture spec suggests searching for graph data).
// For demonstration, we'll assume we want an empty graph initially or fetch a default query.
// Here we just render the shell with the canvas.

const GraphExplorerPage: React.FC = () => {
  const { setSelectedNodeKey } = useUiStore();
  
  // Note: graphApi.overview() only returns counts. The architecture says "CytoscapeCanvas: given a GraphOut fixture...".
  // The actual GraphOut comes from searchGraph or neighbors. We'll leave it empty to start, user must search or click.
  const nodes: any[] = []; 
  const edges: any[] = [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', position: 'relative' }}>
      <GraphToolbar />
      <div style={{ flex: 1, position: 'relative', backgroundColor: 'var(--color-bg)' }}>
        <CytoscapeCanvas 
          nodes={nodes} 
          edges={edges} 
          onSelectNode={setSelectedNodeKey} 
        />
        <NodeInspector />
      </div>
    </div>
  );
};

export default GraphExplorerPage;
