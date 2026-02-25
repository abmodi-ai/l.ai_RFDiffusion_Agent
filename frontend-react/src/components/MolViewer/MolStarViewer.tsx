import { useEffect, useRef } from 'react';

/**
 * Mol* (Molstar) 3D molecular viewer component.
 *
 * Accepts PDB file contents as a Record<file_id, pdb_text> and renders
 * them using Molstar's plugin system with configurable visual styles.
 */

interface Props {
  pdbContents: Record<string, string>;
  style?: 'cartoon' | 'ball-and-stick' | 'surface' | 'spacefill';
  colorBy?: 'chain' | 'residue' | 'element' | 'uniform';
  height?: number;
}

export function MolStarViewer({
  pdbContents,
  style = 'cartoon',
  colorBy = 'chain',
  height = 400,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const pluginRef = useRef<unknown>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    let cancelled = false;

    async function init() {
      try {
        // Dynamic import to avoid bundling Molstar when not needed
        const { createPluginUI } = await import('molstar/lib/mol-plugin-ui');
        const { DefaultPluginUISpec } = await import('molstar/lib/mol-plugin-ui/spec');
        const { renderReact18 } = await import('molstar/lib/mol-plugin-ui/react18');
        if (cancelled || !containerRef.current) return;

        // Clean up previous plugin
        if (pluginRef.current) {
          try {
            (pluginRef.current as { dispose: () => void }).dispose();
          } catch {
            // Ignore cleanup errors
          }
        }

        const plugin = await createPluginUI({
          target: containerRef.current,
          render: renderReact18,
          spec: {
            ...DefaultPluginUISpec(),
            layout: {
              initial: {
                isExpanded: false,
                showControls: false,
              },
            },
          },
        });

        if (cancelled) {
          plugin.dispose();
          return;
        }

        pluginRef.current = plugin;

        // Load PDB structures
        const entries = Object.entries(pdbContents);
        for (const [fileId, pdbText] of entries) {
          const data = await plugin.builders.data.rawData({
            data: pdbText,
            label: fileId,
          });
          const trajectory = await plugin.builders.structure.parseTrajectory(
            data,
            'pdb',
          );

          // Use the default preset first to get the structure loaded
          await plugin.builders.structure.hierarchy.applyPreset(
            trajectory,
            'default',
          );
        }

        // Apply visual style after all structures are loaded
        await applyVisualStyle(plugin, style, colorBy);

        // Auto-zoom to fit all structures
        try {
          plugin.managers.camera.reset();
        } catch {
          // Fallback if camera reset fails
        }
      } catch (err) {
        console.error('Molstar initialization error:', err);

        // Fallback: render PDB text
        if (containerRef.current && !cancelled) {
          containerRef.current.innerHTML = `
            <div class="p-4 bg-gray-100 rounded-lg text-sm">
              <p class="text-gray-500 mb-2">3D viewer unavailable. PDB data loaded:</p>
              <pre class="text-xs overflow-auto max-h-60">${
                Object.entries(pdbContents)
                  .map(([id, text]) => `--- ${id} ---\n${text.slice(0, 500)}...`)
                  .join('\n\n')
              }</pre>
            </div>
          `;
        }
      }
    }

    init();

    return () => {
      cancelled = true;
      if (pluginRef.current) {
        try {
          (pluginRef.current as { dispose: () => void }).dispose();
        } catch {
          // Ignore
        }
        pluginRef.current = null;
      }
    };
  }, [pdbContents, style, colorBy]);

  return (
    <div
      ref={containerRef}
      style={{ width: '100%', height: `${height}px` }}
      className="bg-black rounded-lg"
    />
  );
}

/**
 * Apply visual representation and coloring to all loaded structures.
 * Uses Molstar's internal representation update mechanisms.
 */
async function applyVisualStyle(
  plugin: any,
  style: string,
  colorBy: string,
): Promise<void> {
  try {
    const structures = plugin.managers.structure.hierarchy.current.structures;
    if (!structures || structures.length === 0) return;

    for (const structureRef of structures) {
      const components = structureRef.components;
      if (!components || components.length === 0) continue;

      for (const component of components) {
        const representations = component.representations;
        if (!representations) continue;

        if (representations.length > 0) {
          const reprType = getRepresentationType(style);
          const colorTheme = getColorTheme(colorBy);

          try {
            await plugin.builders.structure.representation.addRepresentation(
              component.cell,
              {
                type: reprType,
                color: colorTheme,
              },
            );
          } catch {
            // If direct update fails, the default representation is fine
          }
        }
      }
    }
  } catch {
    // If style application fails entirely, the default look is used
    console.warn('Could not apply custom style, using default');
  }
}

function getRepresentationType(style: string): string {
  switch (style) {
    case 'cartoon': return 'cartoon';
    case 'ball-and-stick': return 'ball-and-stick';
    case 'surface': return 'gaussian-surface';
    case 'spacefill': return 'spacefill';
    default: return 'cartoon';
  }
}

function getColorTheme(colorBy: string): string {
  switch (colorBy) {
    case 'chain': return 'chain-id';
    case 'residue': return 'residue-name';
    case 'element': return 'element-symbol';
    case 'uniform': return 'uniform';
    default: return 'chain-id';
  }
}
