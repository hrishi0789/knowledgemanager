import cytoscape from 'cytoscape';

// Color map based on index.css palette
export const nodeColors: Record<string, string> = {
  Document: 'hsl(220, 20%, 96%)', // text-primary
  Chunk: 'hsl(220, 10%, 65%)', // text-secondary
  Concept: 'hsl(248, 84%, 67%)', // primary
  Technology: 'hsl(195, 84%, 58%)', // accent
  Project: 'hsl(142, 71%, 45%)', // success
  Person: 'hsl(37, 91%, 55%)', // warning
  default: 'hsl(220, 8%, 44%)', // text-muted
};

export const getCytoscapeStylesheet = (theme: 'dark' | 'light'): cytoscape.StylesheetStyle[] => [
  {
    selector: 'node',
    style: {
      'label': 'data(name)',
      'font-size': '10px',
      'font-family': 'Inter, sans-serif',
      'text-valign': 'bottom',
      'text-halign': 'center',
      'text-margin-y': 4,
      'color': theme === 'dark' ? 'hsl(220, 20%, 96%)' : 'hsl(230, 15%, 8%)',
      'text-outline-width': 2,
      'text-outline-color': theme === 'dark' ? 'hsl(230, 15%, 8%)' : 'hsl(220, 20%, 96%)',
      'background-color': (ele: cytoscape.NodeSingular) => {
        const label = ele.data('label');
        return nodeColors[label] || nodeColors.default;
      },
      // Size interpolation based on pagerank
      'width': (ele: cytoscape.NodeSingular) => {
        const pr = ele.data('pagerank') || 0;
        const minSize = 10;
        const maxSize = 40;
        // Assume pagerank is normalized 0-1, or we clamp it
        return Math.max(minSize, Math.min(maxSize, minSize + (pr * (maxSize - minSize))));
      },
      'height': (ele: cytoscape.NodeSingular) => {
        const pr = ele.data('pagerank') || 0;
        const minSize = 10;
        const maxSize = 40;
        return Math.max(minSize, Math.min(maxSize, minSize + (pr * (maxSize - minSize))));
      },
    }
  },
  {
    selector: 'edge',
    style: {
      'width': (ele: cytoscape.EdgeSingular) => {
        const weight = ele.data('weight') || 1;
        return Math.max(0.5, Math.min(3, weight * 2));
      },
      'line-color': 'hsl(230, 15%, 22%)', // border color
      'target-arrow-color': 'hsl(230, 15%, 22%)',
      'target-arrow-shape': 'triangle',
      'curve-style': 'bezier',
      'opacity': 0.6,
    }
  },
  {
    selector: 'node:selected',
    style: {
      'border-width': 3,
      'border-color': 'white',
      'overlay-opacity': 0.2,
      'overlay-color': 'white',
    }
  }
];
