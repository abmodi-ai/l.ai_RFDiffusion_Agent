import { useEffect, useRef } from 'react';

/**
 * Mol* (Molstar) 3D molecular viewer component.
 *
 * Accepts PDB file contents as a Record<file_id, pdb_text> and renders
 * them using Molstar's plugin system.
 */

interface Props {
  pdbContents: Record<string, string>;
  style?: string;
  colorBy?: string;
  height?: number;
}

export function MolStarViewer({
  pdbContents,
  style: _style = 'cartoon',
  colorBy: _colorBy = 'chain',
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
        for (const [_fileId, pdbText] of entries) {
          const data = await plugin.builders.data.rawData({
            data: pdbText,
            label: _fileId,
          });
          const trajectory = await plugin.builders.structure.parseTrajectory(
            data,
            'pdb',
          );
          await plugin.builders.structure.hierarchy.applyPreset(
            trajectory,
            'default',
          );
        }

        // Auto-zoom to fit all structures
        plugin.managers.camera.focusLoci(
          plugin.managers.structure.hierarchy.current.structures.map(
            (s: { cell: { obj?: { data: unknown } } }) => {
              const obj = s.cell.obj;
              if (obj && 'data' in (obj as Record<string, unknown>)) {
                return { loci: { kind: 'whole-structure' as const } };
              }
              return undefined;
            },
          ).filter(Boolean),
        );
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
  }, [pdbContents]);

  return (
    <div
      ref={containerRef}
      style={{ width: '100%', height: `${height}px` }}
      className="bg-black rounded-lg"
    />
  );
}
