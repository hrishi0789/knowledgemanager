import React, { useEffect, useRef } from 'react';
import cytoscape from 'cytoscape';
import coseBilkent from 'cytoscape-cose-bilkent';
import { useUiStore } from '../../stores/uiStore';
import { getCytoscapeStylesheet } from './style';
import type { GraphNode, GraphEdge } from '../../api/types';

cytoscape.use(coseBilkent);

interface CytoscapeCanvasProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  onSelectNode: (key: string | null) => void;
}

export const CytoscapeCanvas: React.FC<CytoscapeCanvasProps> = ({ nodes, edges, onSelectNode }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const { theme, graphLayoutName } = useUiStore();

  useEffect(() => {
    if (!containerRef.current) return;

    // Initialize Cytoscape
    if (!cyRef.current) {
      cyRef.current = cytoscape({
        container: containerRef.current,
        elements: [],
        style: getCytoscapeStylesheet(theme),
        layout: { name: 'preset' },
        minZoom: 0.1,
        maxZoom: 3,
        wheelSensitivity: 0.2,
      });

      // Events
      cyRef.current.on('tap', 'node', (evt) => {
        const node = evt.target;
        onSelectNode(node.id());
      });

      cyRef.current.on('tap', (evt) => {
        if (evt.target === cyRef.current) {
          onSelectNode(null);
        }
      });
    }

    const cy = cyRef.current;

    // Update stylesheet if theme changes
    cy.style().fromJson(getCytoscapeStylesheet(theme)).update();

    // Map data to cy elements
    const newEles = [
      ...nodes.map(n => ({
        data: { id: n.key, label: n.label, name: n.name, pagerank: n.pagerank }
      })),
      ...edges.map(e => ({
        data: { id: `${e.source}-${e.target}-${e.type}`, source: e.source, target: e.target, type: e.type, weight: e.weight }
      }))
    ];

    // Diff elements for performance instead of full re-init
    const existingIds = new Set(cy.elements().map(e => e.id()));
    const newIds = new Set(newEles.map(e => e.data.id));

    // Remove obsolete
    cy.elements().forEach(ele => {
      if (!newIds.has(ele.id())) {
        cy.remove(ele);
      }
    });

    // Add new
    const toAdd = newEles.filter(e => !existingIds.has(e.data.id));
    if (toAdd.length > 0) {
      cy.add(toAdd as cytoscape.ElementDefinition[]);
    }

    // Run Layout
    if (toAdd.length > 0) {
      cy.layout({ name: graphLayoutName, animate: true, animationDuration: 500 } as any).run();
    }

    return () => {
      // Cleanup on unmount (important to avoid memory leaks)
      // We don't destroy cy on every re-render, only when the component unmounts
      if (cyRef.current) {
        // cyRef.current.destroy(); // Keep it alive between renders, destroy handled by wrapping parent if needed
      }
    };
  }, [nodes, edges, theme, graphLayoutName, onSelectNode]);

  // Handle explicit cleanup on full unmount
  useEffect(() => {
    return () => {
      if (cyRef.current) {
        cyRef.current.destroy();
        cyRef.current = null;
      }
    };
  }, []);

  return <div ref={containerRef} style={{ width: '100%', height: '100%' }} />;
};
